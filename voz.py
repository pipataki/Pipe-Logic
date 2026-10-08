# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Reconocimiento de voz con Vosk, detras del WebSocket del editor.

Dos formas de recibir el audio (config.MICRO):
- el servidor abre el micro por ALSA, como VoiceController: el navegador
  solo manda "escuchar" y "parar";
- el navegador manda el audio: PCM de 16 bits a 16 kHz, mono.

Lo que sale hacia el navegador, en JSON:
    {"tipo": "modo", "micro": "servidor"|"navegador", "nombre": ...}  al conectar
    {"tipo": "nivel", "pico": 0..1}           unas cinco veces por segundo
    {"tipo": "parcial", "texto": ...}         mientras se habla
    {"tipo": "final", "texto": ..., "acciones": [...], "no_entendidas": [...]}
    {"tipo": "error", "texto": ...}
"""

import array
import json
import os
import queue
import tempfile
import threading
import time

import cesion_vc
import config
from rutas import ruta

FRECUENCIA_NAVEGADOR = 16000

_modelo = None
_cerrojo = threading.Lock()


CARPETA_MODELO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_vosk")


def carpeta_del_modelo():
    """El modelo de config.MODELO_VOSK con el silencio de fin de frase de
    config.SILENCIO_FIN_FRASE.

    No se copia nada (son 54 MB) ni se toca el de VC: enlaces a sus
    carpetas, y un conf/model.conf propio con las reglas de fin de frase
    cambiadas. Se rehace en cada arranque, así que basta con cambiar
    config.py.
    """
    origen = ruta(config.MODELO_VOSK)
    silencio = getattr(config, "SILENCIO_FIN_FRASE", None)
    if not silencio:
        return origen
    def enlazar(de, a):
        if os.path.islink(a):
            os.remove(a)
        os.symlink(de, a)

    os.makedirs(os.path.join(CARPETA_MODELO, "conf"), exist_ok=True)
    for nombre in os.listdir(origen):
        if nombre != "conf":
            enlazar(os.path.join(origen, nombre), os.path.join(CARPETA_MODELO, nombre))
    for nombre in os.listdir(os.path.join(origen, "conf")):
        if nombre != "model.conf":
            enlazar(os.path.join(origen, "conf", nombre),
                    os.path.join(CARPETA_MODELO, "conf", nombre))
    # rule2: tras algo bien reconocido; rule3: algo dudoso; rule4: lo que sea
    nuevas = {"rule2": silencio, "rule3": silencio + 0.5, "rule4": silencio + 1.5}
    lineas = []
    with open(os.path.join(origen, "conf", "model.conf")) as f:
        for linea in f:
            for regla, s in nuevas.items():
                if linea.startswith(f"--endpoint.{regla}.min-trailing-silence="):
                    linea = f"--endpoint.{regla}.min-trailing-silence={s}\n"
            lineas.append(linea)
    with open(os.path.join(CARPETA_MODELO, "conf", "model.conf"), "w") as f:
        f.writelines(lineas)
    return CARPETA_MODELO


def _modelo_cargado():
    global _modelo
    with _cerrojo:
        if _modelo is None:
            import vosk
            vosk.SetLogLevel(-2)   # -1 deja pasar los avisos de Kaldi
            _modelo = vosk.Model(carpeta_del_modelo())
        return _modelo


def _gramatica(traductor):
    if not getattr(config, "GRAMATICA", False):
        return None
    return json.dumps(traductor.palabras_para_vosk() + ["[unk]"], ensure_ascii=False)


def _reconocedor(traductor, frecuencia):
    import vosk
    gramatica = _gramatica(traductor)
    if gramatica:
        return vosk.KaldiRecognizer(_modelo_cargado(), frecuencia, gramatica)
    return vosk.KaldiRecognizer(_modelo_cargado(), frecuencia)


def palabras_que_no_conoce(traductor):
    """Las palabras de simbolos.json que el modelo no conoce.

    Vosk las descarta en silencio de la gramatica (solo lo dice por stderr,
    desde C): se recoge esa salida para poder decirlo claro. Con esas
    palabras no se puede dictar nada.
    """
    import vosk
    modelo = _modelo_cargado()
    vosk.SetLogLevel(0)
    with tempfile.TemporaryFile(mode="w+b") as f:
        guardado = os.dup(2)
        os.dup2(f.fileno(), 2)
        try:
            vosk.KaldiRecognizer(modelo, FRECUENCIA_NAVEGADOR, _gramatica(traductor))
        finally:
            os.dup2(guardado, 2)
            os.close(guardado)
            vosk.SetLogLevel(-2)
        f.seek(0)
        salida = f.read().decode("utf-8", "replace")
    fuera = []
    for linea in salida.splitlines():
        if "missing in vocabulary" in linea:
            fuera.append(linea.rsplit(":", 1)[1].strip().strip("'"))
    return fuera


def micro_del_servidor(releer=False):
    """(indice, nombre, frecuencia) del micro de config.MICRO, o None.

    Si lo tiene VoiceController, PortAudio no lo lista (un aparato ALSA
    ocupado no sale): entonces vale (None, nombre, None), y el indice y la
    frecuencia se buscan al escuchar, con el micro ya cedido (ver abrir()).
    releer: PortAudio guarda la lista del arranque; hay que reiniciarlo para
    ver un micro que se acaba de quedar libre."""
    nombre = getattr(config, "MICRO", None)
    if not nombre:
        return None
    import sounddevice as sd
    if releer:
        sd._terminate()
        sd._initialize()
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and nombre.lower() in d["name"].lower():
            return i, d["name"], int(d["default_samplerate"])
    if not releer and cesion_vc.vc_en_marcha():
        return None, nombre, None
    raise RuntimeError(f"no hay ningun micro cuyo nombre contenga '{nombre}' "
                       f"(config.MICRO)")


class _Sesion:
    """Una conexion: reconoce, mide y manda resultados."""

    def __init__(self, ws, traductor):
        self.ws = ws
        self.traductor = traductor
        self.rec = None
        self.ultimo_parcial = ""
        self.bytes = 0
        self.pico = 0            # el mayor de toda la conexion
        self.pico_tramo = 0      # el mayor desde el ultimo aviso de nivel
        self.ultimo_nivel = 0.0
        self.frases = 0
        self.parciales = 0
        self.frecuencia = FRECUENCIA_NAVEGADOR
        self.desde = time.monotonic()
        self.pendiente = []      # trozos de Vosk aún sin escribir
        self.ultima_voz = time.monotonic()

    def mandar(self, **d):
        self.ws.send(json.dumps(d, ensure_ascii=False))

    def preparar(self, frecuencia):
        self.frecuencia = frecuencia
        self.rec = _reconocedor(self.traductor, frecuencia)
        self.ultimo_parcial = ""

    def audio(self, dato):
        self.bytes += len(dato)
        muestras = array.array("h")
        muestras.frombytes(dato[:len(dato) // 2 * 2])
        if muestras:
            # Pico sin la media del bloque: el acp de esta maquina lleva un
            # desvio de continua de +0,28 (medido el 6-oct-2026), y sin
            # restarlo el medidor marcaria media barra en silencio. A Vosk
            # no le molesta (VC usa el mismo micro tal cual).
            media = sum(muestras) // len(muestras)
            p = max(max(muestras) - media, media - min(muestras))
            self.pico = max(self.pico, p)
            self.pico_tramo = max(self.pico_tramo, p)
        ahora = time.monotonic()
        if ahora - self.ultimo_nivel > 0.2:
            self.mandar(tipo="nivel", pico=round(self.pico_tramo / 32768, 3))
            self.pico_tramo = 0
            self.ultimo_nivel = ahora
        if self.rec.AcceptWaveform(dato):
            self.frases += 1
            self.juntar(self.rec.Result())
            self.ultimo_parcial = ""
        else:
            parcial = json.loads(self.rec.PartialResult()).get("partial", "")
            if parcial != self.ultimo_parcial:
                self.ultimo_parcial = parcial
                self.parciales += 1
                self.ultima_voz = time.monotonic()
                self.mandar(tipo="parcial", texto=" ".join(self.pendiente + [parcial]).strip())

    def juntar(self, resultado):
        """Un trozo cerrado por Vosk: se guarda, todavía no se escribe."""
        texto = json.loads(resultado).get("text", "").replace("[unk]", "").strip()
        if texto:
            self.pendiente.append(texto)
            self.mandar(tipo="parcial", texto=" ".join(self.pendiente))

    def revisar(self):
        """Si ya no se habla desde hace PAUSA_PARA_ESCRIBIR, se escribe todo
        lo juntado. La voz se mide por los parciales: mientras se habla,
        cambian; callado, no."""
        pausa = getattr(config, "PAUSA_PARA_ESCRIBIR", 0)
        if (self.pendiente and not self.ultimo_parcial
                and time.monotonic() - self.ultima_voz >= pausa):
            self.escribir()

    def cerrar_frase(self):
        """Al parar: lo que quede, se escribe ya."""
        if self.rec is not None:
            self.juntar(self.rec.FinalResult())
            self.ultimo_parcial = ""
        self.escribir()

    def escribir(self):
        texto = " ".join(self.pendiente).strip()
        self.pendiente = []
        if not texto:
            return
        acciones, no = self.traductor.traducir(texto)
        print(f"[voz] '{texto}' -> {acciones} "
              f"{('no entendidas: ' + str(no)) if no else ''}", flush=True)
        self.mandar(tipo="final", texto=texto, acciones=acciones, no_entendidas=no)

    def resumen(self):
        # Cuanto audio ha llegado y con que volumen: si la voz "no escribe",
        # esto dice si el audio llega (y si llega con algo dentro).
        seg = self.bytes / 2 / self.frecuencia
        print(f"[voz] conexion cerrada: {seg:.1f} s de audio en "
              f"{time.monotonic() - self.desde:.1f} s, pico {self.pico / 32768:.2f}, "
              f"{self.parciales} parciales, {self.frases} frases", flush=True)


def atender(ws, traductor, remoto=False):
    """Bucle de un WebSocket. remoto: la página está en otro aparato (el
    móvil), y entonces el micro es el de su navegador, no el del PC."""
    from simple_websocket import ConnectionClosed
    s = _Sesion(ws, traductor)
    print("[voz] conexion abierta", flush=True)
    try:
        try:
            micro = None if remoto else micro_del_servidor()
        except Exception as e:
            s.mandar(tipo="error", texto=str(e))
            return
        if micro:
            s.mandar(tipo="modo", micro="servidor", nombre=micro[1])
            _con_micro_del_servidor(s, micro)
        else:
            s.mandar(tipo="modo", micro="navegador")
            s.preparar(FRECUENCIA_NAVEGADOR)
            _con_micro_del_navegador(s)
    except (ConnectionClosed, ConnectionError, OSError) as e:
        # El navegador cierra la pestaña o corta el micro: no es un error.
        print(f"[voz] conexion cortada por el otro lado ({type(e).__name__})", flush=True)
    finally:
        s.resumen()


def _con_micro_del_navegador(s):
    while True:
        dato = s.ws.receive(timeout=0.05)
        s.revisar()
        if dato is None:
            continue
        if isinstance(dato, str):
            if dato == "fin":
                s.cerrar_frase()
            continue
        s.audio(dato)


def _con_micro_del_servidor(s, micro):
    import sounddevice as sd
    indice, nombre, frecuencia = micro
    cola = queue.Queue()
    flujo = None
    cesion = None

    def recoger(datos, _frames, _tiempo, _estado):
        cola.put(bytes(datos))

    def abrir():
        nonlocal flujo, cesion, indice, nombre, frecuencia
        # Si VoiceController tiene el micro, nos lo deja mientras se escucha
        # (ver cesion_vc.py). Antes de pedirlo no se veía: se busca ahora.
        cesion = cesion_vc.pedir()
        if cesion is not None or indice is None:
            try:
                indice, nombre, frecuencia = micro_del_servidor(releer=True)
            except Exception:
                cesion_vc.soltar(cesion)
                cesion = None
                raise
        s.preparar(frecuencia)
        # Como VoiceController: frecuencia propia del aparato, mono, int16;
        # Vosk se encarga de pasarlo a lo suyo.
        try:
            flujo = sd.RawInputStream(samplerate=frecuencia, blocksize=4096,
                                      device=indice, dtype="int16", channels=1,
                                      callback=recoger)
            flujo.start()
        except Exception:
            cesion_vc.soltar(cesion)
            cesion = None
            raise
        print(f"[voz] micro abierto: {nombre} a {frecuencia} Hz", flush=True)

    def cerrar():
        nonlocal flujo, cesion
        if flujo is not None:
            flujo.stop()
            flujo.close()
            flujo = None
            while not cola.empty():
                s.audio(cola.get())
            s.cerrar_frase()
            print("[voz] micro cerrado", flush=True)
        cesion_vc.soltar(cesion)
        cesion = None

    try:
        while True:
            orden = s.ws.receive(timeout=0.05)
            if orden == "escuchar" and flujo is None:
                try:
                    abrir()
                    s.mandar(tipo="escuchando", nombre=nombre)
                except Exception as e:
                    flujo = None
                    s.mandar(tipo="error", texto=(
                        f"No se puede abrir el micro {nombre}: {e}. "
                        "Por ALSA directo el micro es de uno solo: si lo "
                        "tiene otro programa (o un VoiceController sin "
                        "cesión de micro), no se puede abrir."))
            elif orden == "parar":
                cerrar()
                s.mandar(tipo="parado")
            while not cola.empty():
                s.audio(cola.get())
            s.revisar()
    finally:
        cerrar()

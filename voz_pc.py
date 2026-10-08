# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""La voz del PC: para decir en alto el código de emparejamiento.

Piper (la misma voz y velocidad que VoiceController) y, si no está,
espeak-ng. Suena por la salida de audio por defecto (aplay). Habla en un
hilo aparte: quien la llama no espera.
"""

import io
import shutil
import subprocess
import threading
import wave

import config
from rutas import ruta

_voz = None
_cerrojo = threading.Lock()


def _piper():
    global _voz
    with _cerrojo:
        if _voz is None:
            from piper import PiperVoice
            _voz = PiperVoice.load(ruta(config.VOZ_PIPER))
        return _voz


def a_wav(texto):
    """El texto dicho, como WAV en memoria (bytes). Con Piper."""
    from piper import SynthesisConfig
    voz = _piper()
    mapa = getattr(voz.config, "speaker_id_map", None) or {}
    hablante = mapa.get("F" if config.VOZ_FEMENINA else "M")
    ajustes = SynthesisConfig(speaker_id=hablante,
                              length_scale=1.0 / float(config.VOZ_VELOCIDAD))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voz.synthesize_wav(texto, w, syn_config=ajustes)
    return buf.getvalue()


def decir(texto):
    """Lo dice en alto, sin esperar. Devuelve qué motor se usa."""
    try:
        datos = a_wav(texto)
        motor = "piper"
    except Exception as e:
        print(f"[voz_pc] sin Piper ({e!r}): se usa espeak-ng", flush=True)
        datos, motor = None, "espeak-ng"

    def sonar():
        try:
            if datos is not None and shutil.which("aplay"):
                subprocess.run(["aplay", "-q", "-"], input=datos, timeout=60)
            elif shutil.which("espeak-ng"):
                subprocess.run(["espeak-ng", "-v", "es", "-s", "150", texto], timeout=60)
            else:
                print("[voz_pc] no hay con qué hablar (ni aplay ni espeak-ng)", flush=True)
        except Exception as e:
            print(f"[voz_pc] no se pudo hablar: {e!r}", flush=True)

    threading.Thread(target=sonar, daemon=True).start()
    return motor

# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Ajustes de Pipe-Logic. El puerto sale de aqui y de ningun otro sitio."""

# El 5000 es de la webapp de VoiceController; los dos deben poder
# estar encendidos a la vez.
PUERTO = 5050

# Solo esta maquina. Si algun dia se quiere usar desde el movil, se cambia
# a "0.0.0.0" sabiendo que entonces lo ve toda la red (y habria que anadir
# la IP a NOMBRES_CERTIFICADO y borrar la carpeta certificado/).
ANFITRION = "127.0.0.1"

# HTTPS con certificado autofirmado, generado una vez en certificado/.
# El navegador avisa la primera vez; se acepta y no vuelve a preguntar.
HTTPS = True
NOMBRES_CERTIFICADO = ["localhost", "127.0.0.1"]

# Voz. El modelo pequeño de español, el mismo que usa VoiceController: se
# apunta a el, no se copia (son 54 MB). El pequeño admite gramatica cerrada
# (solo las palabras de simbolos.json), el grande no.
# Relativo a la carpeta de Pipe-Logic; install.sh lo descarga ahí. En una
# máquina con VoiceController se puede apuntar al suyo en config_local.py.
MODELO_VOSK = "modelos/vosk-model-small-es-0.42"
GRAMATICA = True

# De donde sale el audio:
#   "acp"  -> el servidor abre por ALSA el micro cuyo nombre contiene "acp",
#             como VoiceController (su INPUT_DEVICE = 5 es ese mismo). Va por
#             NOMBRE porque los numeros cambian al enchufar algo USB.
#   None   -> el micro del navegador (pasa por PipeWire). En esta maquina
#             PipeWire no ve el acp y el navegador coge el USB, que da
#             silencio (medido el 6-oct-2026: pico 0.00).
# Ojo: por ALSA directo el micro es de uno solo; con VC escuchando, no abre.
MICRO = None        # en esta máquina, "acp": va en config_local.py

# Cuándo se escribe lo dictado: tras PAUSA_PARA_ESCRIBIR segundos sin
# hablar. Hasta entonces los trozos que da Vosk se JUNTAN y se traducen
# todos a la vez, como hace el Pre-Texto de VoiceController: así "treinta
# y" + "cinco" es 35 aunque Vosk lo parta, y "integral entre ... de ..."
# llega entera. Lo notó pipataki: con cada trozo por separado se rompían.
PAUSA_PARA_ESCRIBIR = 1.5

# Silencio con que Vosk cierra cada trozo. None = el del modelo (0,5 s), que
# ahora basta: los trozos se juntan después. Con un número, Pipe-Logic se
# hace su carpeta de modelo (enlaces al de VC + model.conf propio); pero se
# sumaría a la pausa de arriba (con 1,5 aquí, 3 s hasta escribir).
SILENCIO_FIN_FRASE = None


# La voz del PC (para decir el código de emparejamiento): Piper, y si no
# está, espeak-ng. Mismo hablante y velocidad que VoiceController.
VOZ_PIPER = "voces/es_ES-sharvard-medium.onnx"
VOZ_FEMENINA = True
VOZ_VELOCIDAD = 1.09

# Lo de ESTA máquina que no va a git (direcciones de la VPN, por ejemplo)
# va en config_local.py, que se lee al final y gana. Como en VoiceController.
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass

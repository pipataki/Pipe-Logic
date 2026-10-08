# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Pedirle el micro a VoiceController mientras se escucha.

Por ALSA directo el micro es de uno solo, y cuando coinciden manda
Pipe-Logic. VC atiende un socket Unix (su cesion_microfono.py): se le manda
"PIDO", contesta "LIBRE" cuando ya lo ha cerrado, y lo vuelve a abrir en
cuanto se cierra la conexión. Si Pipe-Logic se cae, el sistema cierra el
socket y VC lo recupera igual.

Sin VC en marcha no hay socket y no se pide nada: el micro ya está libre.
"""

import os
import socket
import tempfile

ESPERA = 5.0   # segundos que se espera el "LIBRE" de VC


def _ruta():
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return os.path.join(base, "voicecontroller", "microfono.sock")
    return os.path.join(tempfile.gettempdir(), f"voicecontroller-{os.getuid()}",
                        "microfono.sock")


def vc_en_marcha():
    """True si VoiceController atiende peticiones de micro."""
    return os.path.exists(_ruta())


def pedir():
    """Pide el micro a VC. Devuelve la conexión, que hay que pasar luego a
    soltar(); None si VC no está (o no contesta) y no hay nada que soltar."""
    ruta = _ruta()
    if not vc_en_marcha():
        return None
    conexion = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conexion.settimeout(ESPERA)
        conexion.connect(ruta)
        conexion.sendall(b"PIDO\n")
        if conexion.makefile("rb").readline(64) != b"LIBRE\n":
            raise OSError("VoiceController no ha contestado LIBRE")
        conexion.settimeout(None)
        print("[voz] VoiceController me deja el micro", flush=True)
        return conexion
    except OSError as e:
        conexion.close()
        print(f"[voz] no se pudo pedir el micro a VoiceController: {e!r}", flush=True)
        return None


def soltar(conexion):
    """Le devuelve el micro a VC."""
    if conexion is not None:
        conexion.close()
        print("[voz] micro devuelto a VoiceController", flush=True)

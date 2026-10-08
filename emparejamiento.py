# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Emparejar el móvil con este PC: un código que se dice en alto.

El código sale del certificado del servidor (doce cifras de su huella
SHA-256): no hay nada que generar ni que guardar, y mientras el
certificado no cambie es siempre el mismo. El móvil enseña el suyo, el PC
lo dice, y si coinciden el móvil guarda esa huella y desde entonces se fía.

Copiado de VoiceController (tools/codigo_emparejamiento.py y
command_router._decir_codigo_emparejamiento, LGPLv3). LA MISMA CUENTA está
en la app de Android (Emparejamiento.java): si se toca una, hay que tocar
la otra, o los números dejan de coincidir sin decir por qué.
"""

import hashlib
import ssl
import time

import certificado
import voz_pc

ESPERA_ENTRE_AVISOS = 20       # segundos: un móvil reintentando no lo repite sin fin
_ultimo_aviso = 0.0


def huella(pem=None):
    """SHA-256 del certificado en binario (DER): lo que ve el móvil por la red."""
    pem = pem or certificado.CERT
    der = ssl.PEM_cert_to_DER_cert(open(pem).read())
    return hashlib.sha256(der).hexdigest()


def codigo(huella_hex=None):
    """Doce cifras, de tres en tres: "123 456 789 012"."""
    h = huella_hex or huella()
    doce = str(int(h[:16], 16) % 10**12).zfill(12)
    return f"{doce[0:3]} {doce[3:6]} {doce[6:9]} {doce[9:12]}"


def frase(cod=None):
    """Cómo se dice: de tres en tres, con pausas, y repetido."""
    grupos = (cod or codigo()).split()
    dicho = ". ".join(" ".join(g) for g in grupos)
    return f"El código de emparejamiento es: {dicho}. Repito: {dicho}."


def anunciar(quien=""):
    """Un móvil sin emparejar está intentando entrar: se dice el código.
    No es un agujero: el código no da acceso a nada, solo sirve para que
    quien está delante del PC compruebe que el móvil habla con él."""
    global _ultimo_aviso
    ahora = time.monotonic()
    if ahora - _ultimo_aviso < ESPERA_ENTRE_AVISOS:
        return False
    _ultimo_aviso = ahora
    cod = codigo()
    print(f"[emparejar] {quien} se está emparejando: digo el código {cod}", flush=True)
    voz_pc.decir(frase(cod))
    return True

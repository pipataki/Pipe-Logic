# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Las rutas de config son relativas a la carpeta de Pipe-Logic (o absolutas)."""

import os

AQUI = os.path.dirname(os.path.abspath(__file__))


def ruta(r):
    return r if os.path.isabs(r) else os.path.join(AQUI, r)

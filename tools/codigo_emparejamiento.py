# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Dice (y escribe) el código de emparejamiento de este PC.

    ./venv/bin/python tools/codigo_emparejamiento.py          lo escribe
    ./venv/bin/python tools/codigo_emparejamiento.py --decir  y lo dice en alto
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import emparejamiento  # noqa: E402

if __name__ == "__main__":
    cod = emparejamiento.codigo()
    print(f"\n  Código de emparejamiento de este PC:\n\n      {cod}\n")
    print("  Compáralo con el que enseña el móvil la primera vez que conecta.")
    print(f"  (huella completa: {emparejamiento.huella()})\n")
    if "--decir" in sys.argv:
        import time
        emparejamiento.voz_pc.decir(emparejamiento.frase(cod))
        time.sleep(12)

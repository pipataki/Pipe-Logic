#!/usr/bin/env bash
# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.
# Borra una instalación de Pipe-Logic (la carpeta donde está este script),
# después de pararlo y de preguntar. No toca nada fuera de esa carpeta.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$AQUI/app.py" ] && [ -f "$AQUI/simbolos.json" ] || { echo "Esto no parece una instalación de Pipe-Logic."; exit 1; }
echo "Se borrará entera: $AQUI"
echo "(con tus ajustes, el certificado, los modelos y el registro)"
read -rp "¿Seguro? Escribe 'borrar' para seguir: " r
[ "$r" = "borrar" ] || { echo "No se ha borrado nada."; exit 0; }
"$AQUI/pipelogic.sh" --parar >/dev/null 2>&1
rm -rf "$AQUI" && echo "Pipe-Logic desinstalado. En el móvil, desinstala la app aparte."

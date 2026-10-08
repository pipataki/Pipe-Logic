#!/usr/bin/env bash
# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.
# ===========================================================================
#  Instala o actualiza Pipe-Logic (Linux)
# ===========================================================================
#  Adaptado del de VoiceController. El mismo script hace las dos cosas:
#
#    ./install.sh [carpeta]     desde el zip descomprimido; por defecto
#                               ~/Pipe-Logic (o la carpeta actual, si ya es
#                               una instalación)
#
#  - Lo del usuario NUNCA se pisa: config_local.py, el certificado, los
#    modelos, la voz, el registro y el venv. Y antes de copiar se guarda copia
#    de todo lo que va a cambiar, por si acaso (.update_backups/).
#  - No ejecuta sudo: si falta algo del sistema, dice el comando y se para.
#  - Descarga el modelo de voz pequeño de español (54 MB) y la voz del PC
#    (Piper, 63 MB) la primera vez.
# ===========================================================================
set -uo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

azul(){ printf "\033[1;34m%s\033[0m\n" "$*"; }
ok(){   printf "  \033[32m✓\033[0m %s\n" "$*"; }
avi(){  printf "  \033[33m!\033[0m %s\n" "$*"; }
err(){  printf "  \033[31m✗\033[0m %s\n" "$*"; }

MODELO="vosk-model-small-es-0.42"
URL_MODELO="https://alphacephei.com/vosk/models/$MODELO.zip"
VOZ="es_ES-sharvard-medium"
URL_VOZ="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/sharvard/medium/$VOZ.onnx"

# --- dónde --------------------------------------------------------------------
DESTINO="${1:-}"
if [ -z "$DESTINO" ]; then
  if [ -f "$PWD/app.py" ] && [ -f "$PWD/simbolos.json" ] && [ -f "$PWD/.instalado" ]; then
    DESTINO="$PWD"
  else
    read -rp "¿Dónde instalar Pipe-Logic? [$HOME/Pipe-Logic] " DESTINO
    DESTINO="${DESTINO:-$HOME/Pipe-Logic}"
  fi
fi
DESTINO="${DESTINO/#\~/$HOME}"
mkdir -p "$DESTINO" && DESTINO="$(cd "$DESTINO" && pwd)"

VER_NUEVA="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$PKG_DIR/version.py")"
VER_VIEJA="$(cat "$DESTINO/.instalado" 2>/dev/null)"
if [ -n "$VER_VIEJA" ]; then
  azul "== Pipe-Logic: actualizando de la $VER_VIEJA a la $VER_NUEVA en $DESTINO =="
  echo "   Tus ajustes (config_local.py), el certificado y los modelos se conservan."
else
  azul "== Pipe-Logic: instalación nueva de la $VER_NUEVA en $DESTINO =="
fi

# Lo del usuario: nunca se sobrescribe.
PERSONALES=(config_local.py certificado modelos voces registro venv modelo_vosk .instalado .update_backups)

# --- lo que tiene que haber en el sistema ----------------------------------------
azul "== Comprobando el sistema =="
FALTAN=()
command -v python3 >/dev/null || FALTAN+=(python3)
python3 -c "import venv, ensurepip" 2>/dev/null || FALTAN+=(python3-venv)
command -v rsync >/dev/null || FALTAN+=(rsync)
command -v curl  >/dev/null || FALTAN+=(curl)
command -v unzip >/dev/null || FALTAN+=(unzip)
command -v aplay >/dev/null || FALTAN+=(alsa-utils)
# Sin ldconfig: en Debian/Kali está en /usr/sbin, fuera del PATH de un
# usuario normal, y daba "falta" con la librería instalada.
python3 -c "import ctypes.util, sys; sys.exit(not ctypes.util.find_library('portaudio'))" \
  || FALTAN+=(libportaudio2)
if [ ${#FALTAN[@]} -gt 0 ]; then
  err "faltan paquetes del sistema. Instálalos y vuelve a ejecutar esto:"
  echo
  echo "      sudo apt install ${FALTAN[*]}"
  echo
  exit 1
fi
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { err "hace falta Python 3.10 o más (hay $PYV)"; exit 1; }
ok "Python $PYV, rsync, curl, unzip, aplay, portaudio"
command -v espeak-ng >/dev/null || avi "espeak-ng no está: solo se usaría si fallara Piper (opcional)"

# --- copiar el código ---------------------------------------------------------------
if [ "$PKG_DIR" != "$DESTINO" ]; then
  azul "== Copiando el código =="
  # Red de seguridad: copia de lo que va a cambiar, aunque PERSONALES se
  # quede corta algún día.
  COPIA="$DESTINO/.update_backups/$(date +%Y%m%d_%H%M%S)"
  N=0
  while IFS= read -r rel; do
    [ -f "$DESTINO/$rel" ] || continue
    cmp -s "$PKG_DIR/$rel" "$DESTINO/$rel" && continue
    mkdir -p "$COPIA/$(dirname "$rel")" && cp -p "$DESTINO/$rel" "$COPIA/$rel" && N=$((N + 1))
  done < <(cd "$PKG_DIR" && find . -type f -not -path "*/__pycache__/*" -printf "%P\n")
  [ "$N" -gt 0 ] && ok "copia de seguridad de $N ficheros que cambian: $COPIA"
  EXCL=(); for p in "${PERSONALES[@]}"; do EXCL+=(--exclude="/$p"); done
  rsync -a "${EXCL[@]}" --exclude='__pycache__' "$PKG_DIR"/ "$DESTINO"/ || { err "falló la copia"; exit 1; }
  ok "código copiado (sin tocar lo tuyo)"
fi
cd "$DESTINO" || exit 1

# --- entorno de Python -------------------------------------------------------------
azul "== Entorno de Python =="
[ -x venv/bin/python ] || python3 -m venv venv || { err "no se pudo crear el venv"; exit 1; }
venv/bin/pip install -q --upgrade pip >/dev/null 2>&1
venv/bin/pip install -q -r requirements.txt || { err "falló pip install -r requirements.txt"; exit 1; }
ok "dependencias instaladas"

# --- modelo de voz y voz del PC ------------------------------------------------------
azul "== Modelo de voz (reconocer) y voz del PC (hablar) =="
mkdir -p modelos voces
if [ ! -d "modelos/$MODELO" ]; then
  echo "   Descargando $MODELO (54 MB)..."
  curl -fSL --progress-bar -o "modelos/$MODELO.zip" "$URL_MODELO" \
    && unzip -q -o "modelos/$MODELO.zip" -d modelos && rm -f "modelos/$MODELO.zip" \
    || { err "no se pudo descargar el modelo: $URL_MODELO"; exit 1; }
fi
ok "modelo: modelos/$MODELO"
if [ ! -f "voces/$VOZ.onnx" ] || [ ! -f "voces/$VOZ.onnx.json" ]; then
  echo "   Descargando la voz $VOZ (63 MB)..."
  curl -fSL --progress-bar -o "voces/$VOZ.onnx" "$URL_VOZ" \
    && curl -fsSL -o "voces/$VOZ.onnx.json" "$URL_VOZ.json" \
    || { avi "no se pudo descargar la voz: el código se dirá con espeak-ng"; }
fi
[ -f "voces/$VOZ.onnx" ] && ok "voz del PC: voces/$VOZ.onnx"

# --- preguntas (solo la primera vez) --------------------------------------------------
if [ ! -f config_local.py ]; then
  azul "== Ajustes de este PC (se guardan en config_local.py) =="
  {
    echo '"""Ajustes de este PC. Lo escribió install.sh; no viaja en el zip ni se pisa al actualizar."""'
    echo
  } > config_local.py

  echo "   Micrófonos que ve el sistema por ALSA:"
  venv/bin/python - <<'PY'
import sounddevice as sd
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"      {i}: {d['name']}")
PY
  echo "   Si el navegador no oye tu micro (pasa si el sistema de sonido no lo"
  echo "   ve), elige aquí uno por su número y lo abrirá el propio Pipe-Logic."
  read -rp "   Número del micro [vacío = el del navegador]: " MIC
  if [ -n "$MIC" ]; then
    NOMBRE="$(venv/bin/python -c "import sounddevice as sd; print(sd.query_devices($MIC)['name'].split(':')[0].strip())" 2>/dev/null)"
    if [ -n "$NOMBRE" ]; then
      echo "MICRO = \"$NOMBRE\"" >> config_local.py && ok "micro: $NOMBRE"
    else
      avi "no hay micro $MIC: se usará el del navegador"
    fi
  fi

  echo
  echo "   Para usarlo desde el móvil, Pipe-Logic tiene que escuchar en una"
  echo "   dirección que el móvil alcance. Las de este PC:"
  ip -4 -br addr 2>/dev/null | awk '$1 != "lo" {print "      " $1 ": " $3}'
  read -rp "   Dirección para el móvil [vacío = solo este PC]: " IPM
  IPM="${IPM%%/*}"
  if [ -n "$IPM" ]; then
    {
      echo "ANFITRION = \"$IPM\""
      echo "NOMBRES_CERTIFICADO = [\"localhost\", \"127.0.0.1\", \"$IPM\"]"
    } >> config_local.py
    ok "escuchará en $IPM"
  fi
fi

echo "$VER_NUEVA" > .instalado
URL="$(venv/bin/python -c 'import config; print("https://%s:%d" % (config.ANFITRION, config.PUERTO))')"

azul "== Listo =="
cat <<FIN

   Arrancar y abrir:      ./pipelogic.sh --abrir
   Parar / estado:        ./pipelogic.sh --parar | --estado
   Dirección:             $URL

   La primera vez el navegador avisará del certificado. Para que no avise
   más, importa como AUTORIDAD (y marca "identificar sitios web"):
       $DESTINO/certificado/ca.pem
   (se crea al arrancar por primera vez).

   En el móvil: instala Pipe-Logic.apk, pon la dirección de arriba y, la
   primera vez, compara el código que enseña con el que dice el PC en alto
   (también: ./pipelogic.sh --codigo).

FIN

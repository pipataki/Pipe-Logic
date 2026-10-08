#!/usr/bin/env bash
# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

# ===========================================================================
#  Arranca, para y vigila Pipe-Logic en segundo plano
# ===========================================================================
#  Copia el estilo de silentRun.sh de VoiceController, y por lo mismo:
#
#   1. `setsid` lo separa de la terminal: cerrar Konsole no lo tumba.
#   2. La salida va a un registro, y con `python -u`, que si no Python la
#      guarda en un bufer y el registro sale vacio justo cuando hace falta.
#   3. El PID se guarda para pararlo limpio. Nada de `pkill -f`: el patron
#      casa con la linea de comando de quien lo lanza y se mata a si mismo
#      (paso al probar Pipe-Logic el 6-oct-2026).
#
#  Uso:
#     ./pipelogic.sh              arranca y espera a que responda
#     ./pipelogic.sh --parar      lo para
#     ./pipelogic.sh --reiniciar  lo para y lo arranca (tras tocar el codigo)
#     ./pipelogic.sh --estado     dice si corre, por donde, y si responde
#     ./pipelogic.sh --registro   sigue el registro en vivo (Ctrl+C para salir);
#                                 está en registro/, con los 5 arranques anteriores
#     ./pipelogic.sh --abrir      lo abre en el navegador (arrancandolo si hace falta)
#     ./pipelogic.sh --codigo     escribe y DICE EN ALTO el codigo de emparejamiento
# ===========================================================================
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"
AQUI="$(pwd)"

# En la carpeta de cada instalación: en /tmp lo compartían dos instalaciones.
PIDF="registro/pipe-logic.pid"
# En la carpeta del proyecto, no en /tmp: /tmp se vacía al reiniciar y las
# pruebas de pipataki se perdían (7-oct-2026). Se guardan los 5 últimos arranques.
mkdir -p registro
LOG="registro/pipe-logic.log"
ESPERA_MAX=20

ok(){  printf "  \033[32m✓\033[0m %s\n" "$*"; }
avi(){ printf "  \033[33m!\033[0m %s\n" "$*"; }
err(){ printf "  \033[31m✗\033[0m %s\n" "$*"; }

[ -x venv/bin/python3 ] || { err "no encuentro venv/bin/python3"; exit 1; }

# La direccion sale de config.py, que es la unica fuente del puerto.
URL="$(venv/bin/python3 -c 'import config; print(("https" if config.HTTPS else "http") + "://" + config.ANFITRION + ":" + str(config.PUERTO))')"
PUERTO="${URL##*:}"

# Es nuestro solo si el PID vive, ejecuta app.py y lo hace desde ESTA
# carpeta: "app.py" a secas lo tiene medio mundo (la webapp de VC tambien).
corriendo(){
  [ -f "$PIDF" ] || return 1
  local p; p="$(cat "$PIDF" 2>/dev/null)"
  [ -n "$p" ] && kill -0 "$p" 2>/dev/null \
    && grep -q "app.py" "/proc/$p/cmdline" 2>/dev/null \
    && [ "$(readlink -f "/proc/$p/cwd")" = "$AQUI" ]
}

responde(){ curl -sk -o /dev/null --max-time 2 "$URL/"; }

# Quien tiene el puerto, si no somos nosotros (otro Pipe-Logic lanzado a
# mano, por ejemplo). ss sin sudo no da el PID de procesos ajenos, pero de
# los del propio usuario si.
quien_tiene_el_puerto(){
  # Solo en NUESTRA dirección: otra instalación puede usar el mismo puerto
  # en otra (127.0.0.1 frente a la de la VPN).
  local dir="${URL#https://}"; dir="${dir#http://}"; dir="${dir%%:*}"
  ss -ltnpH "( sport = :$PUERTO ) and ( src $dir or src 0.0.0.0 )" 2>/dev/null \
    | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2
}

parar(){
  if corriendo; then
    local p; p="$(cat "$PIDF")"
    kill "$p" 2>/dev/null
    for _ in $(seq 1 10); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    kill -0 "$p" 2>/dev/null && { kill -9 "$p" 2>/dev/null; avi "hubo que forzarlo"; }
    rm -f "$PIDF"; ok "parado"
  else
    rm -f "$PIDF"
    avi "no estaba corriendo"
  fi
}

arrancar(){
  if corriendo; then
    avi "ya está corriendo (PID $(cat "$PIDF")) en $URL"
    return 0
  fi
  local otro; otro="$(quien_tiene_el_puerto)"
  if [ -n "$otro" ] || responde; then
    err "el puerto $PUERTO ya está ocupado${otro:+ (PID $otro)}, y no por este script."
    [ -n "$otro" ] && echo "     $(tr '\0' ' ' < "/proc/$otro/cmdline" 2>/dev/null)"
    echo "     Si es un Pipe-Logic lanzado a mano:  kill ${otro:-<PID>}"
    return 1
  fi
  for k in 4 3 2 1; do [ -f "$LOG.$k" ] && mv -f "$LOG.$k" "$LOG.$((k + 1))"; done
  [ -f "$LOG" ] && mv -f "$LOG" "$LOG.1"
  setsid nohup venv/bin/python3 -u app.py > "$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"
  for _ in $(seq 1 $((ESPERA_MAX * 2))); do
    sleep 0.5
    responde && break
    corriendo || { err "se cerró al arrancar. Últimas líneas:"; tail -8 "$LOG"; rm -f "$PIDF"; return 1; }
  done
  if responde; then
    ok "listo en $URL (PID $(cat "$PIDF"))"
  else
    avi "arrancado (PID $(cat "$PIDF")) pero no responde tras $ESPERA_MAX s. Mira: $LOG"
    return 1
  fi
}

case "${1:-}" in
  "")           arrancar || exit 1 ;;
  --parar)      parar ;;
  --reiniciar)  parar; arrancar || exit 1 ;;
  --estado)
      if corriendo; then
        p="$(cat "$PIDF")"
        ok "corriendo, PID $p, $(( $(awk '{print $2}' "/proc/$p/statm" 2>/dev/null || echo 0) * 4096 / 1048576 )) MB"
        if responde; then ok "responde en $URL"; else err "el proceso vive pero NO responde en $URL"; fi
        echo "    registro: $LOG"
      else
        avi "no está corriendo"
        otro="$(quien_tiene_el_puerto)"
        [ -n "$otro" ] && avi "pero el puerto $PUERTO lo tiene el PID $otro (lanzado sin este script)"
      fi
      exit 0 ;;
  --registro)   exec tail -f "$LOG" ;;
  --codigo)     exec venv/bin/python3 tools/codigo_emparejamiento.py --decir ;;
  --abrir)
      arrancar || exit 1
      xdg-open "$URL/" >/dev/null 2>&1 &
      ok "abriendo $URL en el navegador"
      echo "    la primera vez avisa del certificado autofirmado: se acepta y ya" ;;
  *) sed -n '2,23p' "$0"; exit 0 ;;
esac

if [ -z "${1:-}" ] || [ "${1:-}" = "--reiniciar" ]; then
  echo
  echo "     abrir:     $0 --abrir     (o $URL en el navegador)"
  echo "     estado:    $0 --estado"
  echo "     registro:  $0 --registro"
  echo "     reiniciar: $0 --reiniciar"
  echo "     parar:     $0 --parar"
fi

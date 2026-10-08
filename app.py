# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Pipe-Logic: editor de simbolos logicos y matematicos.

    ./venv/bin/python app.py        y abrir https://127.0.0.1:5050
"""

import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_sock import Sock

import config
import dictado
import emparejamiento
import herramientas
import voz

AQUI = Path(__file__).resolve().parent
SIMBOLOS = AQUI / "simbolos.json"

app = Flask(__name__)
sock = Sock(app)


def cargar_simbolos():
    # Se lee en cada peticion: si se toca simbolos.json, basta con recargar
    # la pagina.
    with open(SIMBOLOS, encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def portada():
    return render_template("index.html")


@app.get("/simbolos")
def simbolos():
    return jsonify(cargar_simbolos()["grupos"])


@app.get("/herramientas")
def lista_herramientas():
    return jsonify(cargar_simbolos()["herramientas"])


@app.post("/herramienta")
def usar_herramienta():
    pedido = request.get_json(force=True)
    return jsonify(herramientas.aplicar(pedido.get("id", ""), pedido.get("texto", "")))


@app.post("/emparejar/anuncio")
def anuncio_de_emparejamiento():
    # La app del móvil avisa de que está intentando emparejarse.
    dicho = emparejamiento.anunciar(request.remote_addr)
    return jsonify({"dicho": dicho})


@sock.route("/voz")
def voz_ws(ws):
    # El traductor se rehace en cada conexion: tocar simbolos.json y volver
    # a pulsar "Escuchar" basta, sin reiniciar el servidor.
    # Desde otro aparato (el móvil), el micro es el suyo: el del navegador.
    remoto = request.remote_addr not in ("127.0.0.1", "::1", config.ANFITRION) \
        or request.args.get("micro") == "navegador"
    voz.atender(ws, dictado.Traductor(cargar_simbolos()), remoto=remoto)


if __name__ == "__main__":
    contexto = None
    if config.HTTPS:
        import certificado
        contexto = certificado.el_certificado()
    esquema = "https" if contexto else "http"
    print(f"Pipe-Logic en {esquema}://{config.ANFITRION}:{config.PUERTO}", flush=True)
    if contexto:
        print(f"[emparejar] código de este PC: {emparejamiento.codigo()}", flush=True)
    fuera = voz.palabras_que_no_conoce(dictado.Traductor(cargar_simbolos()))
    if fuera:
        print(f"[voz] el modelo no conoce {len(fuera)} palabras de simbolos.json "
              f"(no se pueden dictar): {', '.join(fuera)}", flush=True)
    else:
        print("[voz] el modelo conoce todas las palabras de simbolos.json", flush=True)
    app.run(host=config.ANFITRION, port=config.PUERTO, debug=False,
            ssl_context=contexto)

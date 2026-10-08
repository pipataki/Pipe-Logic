# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Las herramientas de cálculo y lógica, y dónde va su resultado.

Cada herramienta recibe el texto de una línea (o lo seleccionado) y
devuelve qué escribir: detrás, en la misma línea, si cabe; si no cabe o
son varias líneas (una tabla, un árbol), en las líneas de debajo.

Qué herramientas hay, con su botón y sus frases para la voz, está en
simbolos.json ("herramientas"); aquí solo se dice qué función hace cada una.
"""

import multiprocessing
import re

import calculo
import logica

ANCHO_LINEA = 80       # más largo que esto, el resultado baja a la línea siguiente
TIEMPO_ALGEBRA = 10    # segundos; una integral difícil puede no acabar nunca

# El álgebra (sympy) va en un proceso aparte: si se pasa de tiempo, se mata
# el proceso y el servidor sigue. "forkserver" y no "fork": el servidor
# tiene hilos, y hacer fork de un proceso con hilos puede colgarse. El
# forkserver ya tiene sympy cargado, así que cada cálculo arranca al momento.
_contexto = None


def _ctx():
    global _contexto
    if _contexto is None:
        _contexto = multiprocessing.get_context("forkserver")
        _contexto.set_forkserver_preload(["algebra"])
    return _contexto


def _trabajo(nombre, texto, tubo):
    import algebra
    tubo.send(algebra.aplicar(nombre, texto))
    tubo.close()


def _algebra(nombre):
    def hacer(texto):
        padre, hijo = _ctx().Pipe(duplex=False)
        p = _ctx().Process(target=_trabajo, args=(nombre, texto, hijo), daemon=True)
        p.start()
        hijo.close()
        if padre.poll(TIEMPO_ALGEBRA):
            try:
                r = padre.recv()
            except EOFError:
                r = ("indeterminado (el cálculo falló sin decir por qué)", None)
            p.join()
            return r
        p.terminate()
        p.join()
        return f"indeterminado (tarda demasiado: más de {TIEMPO_ALGEBRA} s)", None
    return hacer


def _factorizar(texto):
    # con letras, factores algebraicos; con números, primos
    if re.search(r"[A-Za-z]", texto):
        return _algebra("factoriza_algebra")(texto)
    return calculo.factorizar(texto)

# id en simbolos.json -> (función, si su resultado en línea lleva "— " delante)
FUNCIONES = {
    "bien_formada": (logica.bien_formada, True),
    "tabla_verdad": (logica.tabla_de_verdad, True),
    "clasificar": (logica.clasificar, True),
    "equivalencia": (logica.equivalencia, True),
    "consecuencia": (logica.consecuencia, True),
    "analizar": (logica.analizar, True),
    "fnc": (logica.fnc, True),
    "fnd": (logica.fnd, True),
    "calcula": (calculo.calcular, False),
    "factoriza": (_factorizar, False),
    "resuelve": (_algebra("resuelve"), True),
    "simplifica": (_algebra("simplifica"), True),
    "desarrolla": (_algebra("desarrolla"), True),
    "deriva": (_algebra("deriva"), True),
    "integra": (_algebra("integra"), True),
}


def aplicar(herramienta, texto):
    """{"expresion": la línea sin el resultado anterior,
        "en_linea": lo que va detrás (o None), "debajo": lo de debajo (o None)}"""
    if herramienta not in FUNCIONES:
        return {"error": f"no hay ninguna herramienta «{herramienta}»"}
    funcion, con_raya = FUNCIONES[herramienta]
    if herramienta == "calcula":
        # Calcular es solo calcular (pipataki). "dos más tres igual calcula"
        # escribe "2 + 3 =": ese = marca dónde va el resultado. Pero un =
        # (o ≈) con algo detrás lo puso él a propósito, o ya está calculado:
        # no se comprueba ni se recalcula; la línea no se toca.
        expresion = texto.rstrip()
        if expresion.endswith("="):
            expresion = expresion[:-1].rstrip()
        if "=" in expresion or "≈" in expresion:
            return {"aviso": "Esta línea ya tiene «=» con algo detrás: no se toca. "
                             "Para calcular, deja solo la operación (o acabada en =)."}
        if re.search(r"(?<![A-Za-z])i(?![A-Za-z])", expresion) or "φ" in expresion:
            # con la unidad imaginaria, o con φ (para que φ² − φ dé 1 exacto
            # y no ≈ 1), calcula sympy
            funcion = _algebra("calcula")
    elif "\n" in texto:
        # un bloque (sistema de ecuaciones): fuera los resultados de antes,
        # los de detrás de cada línea y las líneas que empiezan por "—"
        lineas = [calculo.quitar_resultado(l).rstrip() for l in texto.splitlines()]
        expresion = "\n".join(l for l in lineas if l.strip() and not l.lstrip().startswith("—"))
    else:
        expresion = calculo.quitar_resultado(texto).rstrip()
    if not expresion.strip():
        return {"error": "no hay nada que calcular en esta línea"}
    en_linea, debajo = funcion(expresion.strip())
    if herramienta == "calcula" and en_linea and en_linea.startswith("≈"):
        # Ha salido algo irracional (√2, π, e...), y calculo.py lo lleva con
        # decimales desde ese momento: √2 · √2 daba "≈ 2". pipataki: nada de
        # acarrear aproximaciones. Se rehace exacto con sympy y la
        # aproximación se calcula solo al final, sobre el resultado.
        exacto, _ = _algebra("calcula")(expresion.strip())
        if not exacto.startswith("indeterminado"):
            en_linea = exacto
        # si sympy no lo entiende (mcd, conjuntos...), se queda el ≈
    if en_linea and con_raya and not en_linea.startswith(("=", "≈", "—")):
        en_linea = "— " + en_linea
    ultima = expresion.splitlines()[-1] if expresion else ""
    if en_linea and len(ultima) + 1 + len(en_linea) > ANCHO_LINEA:
        debajo = en_linea + ("\n" + debajo if debajo else "")
        en_linea = None
    return {"expresion": expresion, "en_linea": en_linea, "debajo": debajo}

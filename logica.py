# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Lógica de proposiciones, con las reglas del libro de LED (UNED).

- Alfabeto: letras (p, q, r..., p₁, p₂...), las constantes ⊤ y ⊥, las
  conectivas ¬ ∧ ∨ → ↔ y los paréntesis.
- Fórmula ESTRICTA: atómica, (¬X) o (X ∗ Y): cada conectiva con su par de
  paréntesis, también la negación.
- Con PRECEDENCIA: ¬ 1, ∧ 2, ∨ 3, → 4, ↔ 5; la de menor número va más
  adentro, y una misma binaria repetida se agrupa por la izquierda.
- Valores 1 y 0; las filas de la tabla, de todo unos a todo ceros.

Una fórmula es una tupla:
    ("atom", "p₁")   ("const", "⊤")   ("no", X)   ("bin", "∧", X, Y)
"""

import itertools
import re

NEGACION = "¬"
BINARIAS = {"∧": 2, "∨": 3, "→": 4, "↔": 5}      # orden de precedencia
CONSTANTES = {"⊤": 1, "⊥": 0}
# Lo que se acepta escrito de otra forma (otras notaciones, teclado).
EQUIVALENTES = {"~": "¬", "∼": "¬", "&": "∧", "|": "∨", "⇒": "→", "⇔": "↔"}

MAX_LETRAS_TABLA = 6      # 64 filas: más no cabe en el editor con sentido
MAX_LETRAS = 16           # para clasificar / equivalencia (65.536 filas)

SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_RE_ATOMO = re.compile(r"[A-Za-z][₀-₉0-9]*[′']*")


class NoEsFormula(Exception):
    def __init__(self, motivo, posicion=None):
        super().__init__(motivo)
        self.motivo = motivo
        self.posicion = posicion


# --- símbolos sueltos -----------------------------------------------------

def _simbolos(texto):
    """Lista de (símbolo, posición). Los átomos van enteros: p₁₂ es uno."""
    fuera, i = [], 0
    while i < len(texto):
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        c = EQUIVALENTES.get(c, c)
        m = _RE_ATOMO.match(texto, i)
        if m:
            fuera.append((m.group(), i))
            i = m.end()
        elif c in "()" or c == NEGACION or c in BINARIAS or c in CONSTANTES:
            fuera.append((c, i))
            i += 1
        else:
            raise NoEsFormula(f"«{texto[i]}» no está en el alfabeto proposicional", i)
    return fuera


def _es_atomo(s):
    return bool(_RE_ATOMO.fullmatch(s))


def _hoja(s):
    return ("const", s) if s in CONSTANTES else ("atom", s)


# --- lectura estricta ------------------------------------------------------

def leer_estricta(texto):
    simbolos = _simbolos(texto)
    if not simbolos:
        raise NoEsFormula("no hay nada que leer")
    pos = 0

    def ver():
        return simbolos[pos][0] if pos < len(simbolos) else None

    def donde():
        return simbolos[pos][1] if pos < len(simbolos) else len(texto)

    def formula():
        nonlocal pos
        s = ver()
        if s is None:
            raise NoEsFormula("falta una fórmula al final", donde())
        if _es_atomo(s) or s in CONSTANTES:
            pos += 1
            return _hoja(s)
        if s != "(":
            raise NoEsFormula(f"aquí se esperaba una fórmula y hay «{s}»", donde())
        pos += 1
        if ver() == NEGACION:
            pos += 1
            x = formula()
            if ver() != ")":
                raise NoEsFormula("a la negación le falta su paréntesis de cierre: (¬X)", donde())
            pos += 1
            return ("no", x)
        x = formula()
        op = ver()
        if op not in BINARIAS:
            if op == ")":
                raise NoEsFormula("sobran paréntesis: (X) no es una fórmula estricta", donde())
            raise NoEsFormula("aquí se esperaba una conectiva binaria", donde())
        pos += 1
        y = formula()
        if ver() != ")":
            raise NoEsFormula(f"falta el paréntesis de cierre de la «{op}»", donde())
        pos += 1
        return ("bin", op, x, y)

    f = formula()
    if pos != len(simbolos):
        raise NoEsFormula(f"sobra lo que hay desde «{ver()}»", donde())
    return f


# --- lectura con precedencia ----------------------------------------------

def leer(texto):
    """Lee con las reglas de precedencia del libro (acepta también la estricta)."""
    simbolos = _simbolos(texto)
    if not simbolos:
        raise NoEsFormula("no hay nada que leer")
    pos = 0

    def ver():
        return simbolos[pos][0] if pos < len(simbolos) else None

    def donde():
        return simbolos[pos][1] if pos < len(simbolos) else len(texto)

    def unaria():
        nonlocal pos
        s = ver()
        if s is None:
            raise NoEsFormula("falta una fórmula al final", donde())
        if s == NEGACION:
            pos += 1
            return ("no", unaria())
        if _es_atomo(s) or s in CONSTANTES:
            pos += 1
            return _hoja(s)
        if s == "(":
            pos += 1
            x = binaria(5)
            if ver() != ")":
                raise NoEsFormula("falta cerrar un paréntesis", donde())
            pos += 1
            return x
        raise NoEsFormula(f"aquí se esperaba una fórmula y hay «{s}»", donde())

    def binaria(nivel):
        nonlocal pos
        if nivel == 1:
            return unaria()
        x = binaria(nivel - 1)
        # Misma conectiva repetida: por la izquierda.
        while ver() in BINARIAS and BINARIAS[ver()] == nivel:
            op = ver()
            pos += 1
            x = ("bin", op, x, binaria(nivel - 1))
        return x

    f = binaria(5)
    if pos != len(simbolos):
        s = ver()
        if s == ")":
            raise NoEsFormula("sobra un paréntesis de cierre", donde())
        raise NoEsFormula(f"dos fórmulas seguidas sin conectiva entre ellas (en «{s}»)", donde())
    return f


# --- escribir --------------------------------------------------------------

def estricta(f):
    """Con todos los paréntesis, como la define el libro."""
    if f[0] in ("atom", "const"):
        return f[1]
    if f[0] == "no":
        return f"(¬{estricta(f[1])})"
    return f"({estricta(f[2])} {f[1]} {estricta(f[3])})"


def _nivel(f):
    if f[0] in ("atom", "const"):
        return 0
    if f[0] == "no":
        return 1
    return BINARIAS[f[1]]


def corta(f):
    """Con los paréntesis justos según la precedencia del libro."""
    if f[0] in ("atom", "const"):
        return f[1]
    if f[0] == "no":
        x = corta(f[1])
        return "¬" + (x if _nivel(f[1]) <= 1 else f"({x})")
    op, x, y = f[1], f[2], f[3]
    n = BINARIAS[op]
    a = corta(x)
    if _nivel(x) > n:                 # por la izquierda vale igual nivel
        a = f"({a})"
    b = corta(y)
    if _nivel(y) >= n:                # por la derecha, no
        b = f"({b})"
    return f"{a} {op} {b}"


# --- semántica -------------------------------------------------------------

def _orden_letra(nombre):
    base = nombre.rstrip("′'")
    letra, num = base[0], base[1:].translate(SUB)
    return (letra.lower(), letra, int(num) if num else -1, nombre)


def letras(*formulas):
    vistas = set()

    def recorrer(f):
        if f[0] == "atom":
            vistas.add(f[1])
        elif f[0] == "no":
            recorrer(f[1])
        elif f[0] == "bin":
            recorrer(f[2])
            recorrer(f[3])

    for f in formulas:
        recorrer(f)
    return sorted(vistas, key=_orden_letra)


def valor(f, asignacion):
    t = f[0]
    if t == "atom":
        return asignacion[f[1]]
    if t == "const":
        return CONSTANTES[f[1]]
    if t == "no":
        return 1 - valor(f[1], asignacion)
    a, b = valor(f[2], asignacion), valor(f[3], asignacion)
    op = f[1]
    if op == "∧":
        return min(a, b)
    if op == "∨":
        return max(a, b)
    if op == "→":
        return 0 if (a, b) == (1, 0) else 1
    return 1 if a == b else 0


def asignaciones(nombres):
    """De todo unos a todo ceros, como en el libro."""
    for valores in itertools.product((1, 0), repeat=len(nombres)):
        yield dict(zip(nombres, valores))


def _tupla(nombres, asignacion):
    if len(nombres) == 1:
        return f"{nombres[0]} = {asignacion[nombres[0]]}"
    return f"({', '.join(nombres)}) = ({', '.join(str(asignacion[n]) for n in nombres)})"


# --- estructura ------------------------------------------------------------

def subformulas(f):
    """Subf(X): sin repetidas, de las hojas a la raíz (por rango, y por
    orden de aparición dentro del mismo rango)."""
    vistas = []

    def recorrer(g):
        if g[0] == "no":
            recorrer(g[1])
        elif g[0] == "bin":
            recorrer(g[2])
            recorrer(g[3])
        if g not in vistas:
            vistas.append(g)

    recorrer(f)
    return sorted(vistas, key=lambda g: (rango(g), vistas.index(g)))


def nod(f):
    if f[0] in ("atom", "const"):
        return 1
    if f[0] == "no":
        return 1 + nod(f[1])
    return 1 + nod(f[2]) + nod(f[3])


def rango(f):
    if f[0] in ("atom", "const"):
        return 0
    if f[0] == "no":
        return rango(f[1]) + 1
    return max(rango(f[2]), rango(f[3])) + 1


def _arbol(f, prefijo="", ultimo=True, raiz=True):
    if f[0] in ("atom", "const"):
        etiqueta = f[1]
    elif f[0] == "no":
        etiqueta = f"¬   {estricta(f)}"
    else:
        etiqueta = f"{f[1]}   {estricta(f)}"
    if raiz:
        lineas = [etiqueta]
        hijo = ""
    else:
        lineas = [prefijo + ("└─ " if ultimo else "├─ ") + etiqueta]
        hijo = prefijo + ("   " if ultimo else "│  ")
    hijos = [f[1]] if f[0] == "no" else ([f[2], f[3]] if f[0] == "bin" else [])
    for k, h in enumerate(hijos):
        lineas += _arbol(h, hijo, k == len(hijos) - 1, False)
    return lineas


# --- formas normales --------------------------------------------------------

def _literal(nombre, positivo):
    return nombre if positivo else "¬" + nombre


def _implicantes_primos(nombres, unos):
    """Quine-McCluskey: términos como tuplas de 1/0/None (None = da igual)."""
    actuales = {tuple(fila) for fila in unos}
    primos = set()
    while actuales:
        usados, siguientes = set(), set()
        lista = sorted(actuales, key=lambda t: [(-1 if v is None else v) for v in t])
        for a, b in itertools.combinations(lista, 2):
            difs = [i for i in range(len(a)) if a[i] != b[i]]
            if len(difs) == 1 and a[difs[0]] is not None and b[difs[0]] is not None:
                t = list(a)
                t[difs[0]] = None
                siguientes.add(tuple(t))
                usados.update((a, b))
        primos |= actuales - usados
        actuales = siguientes
    return primos


def _cubre(termino, fila):
    return all(t is None or t == v for t, v in zip(termino, fila))


def _minima(nombres, unos):
    """Cobertura con implicantes primos: esenciales primero, luego el que
    más filas cubra. No garantiza la mínima absoluta, pero sí una corta."""
    primos = sorted(_implicantes_primos(nombres, unos),
                    key=lambda t: (sum(v is None for v in t) * -1, str(t)))
    pendientes = [tuple(f) for f in unos]
    elegidos = []
    for fila in list(pendientes):
        cubren = [p for p in primos if _cubre(p, fila)]
        if len(cubren) == 1 and cubren[0] not in elegidos:
            elegidos.append(cubren[0])
    pendientes = [f for f in pendientes if not any(_cubre(p, f) for p in elegidos)]
    while pendientes:
        mejor = max(primos, key=lambda p: sum(_cubre(p, f) for f in pendientes))
        elegidos.append(mejor)
        pendientes = [f for f in pendientes if not _cubre(mejor, f)]
    return elegidos


def _escribir_normal(nombres, terminos, dentro, fuera, vacio_dentro):
    """Une literales con `dentro` y términos con `fuera`."""
    partes = []
    for t in terminos:
        lits = [_literal(n, v == (1 if dentro == "∧" else 0))
                for n, v in zip(nombres, t) if v is not None]
        if not lits:
            return vacio_dentro
        partes.append(lits[0] if len(lits) == 1 else
                      (f"({f' {dentro} '.join(lits)})" if len(terminos) > 1 else f" {dentro} ".join(lits)))
    return f" {fuera} ".join(partes)


def formas_normales(f):
    """{"fnd": ..., "fnd_corta": ..., "fnc": ..., "fnc_corta": ...}"""
    nombres = letras(f)
    if len(nombres) > MAX_LETRAS_TABLA + 2:
        raise NoEsFormula(f"demasiadas letras ({len(nombres)}) para formas normales")
    if not nombres:
        v = valor(f, {})
        c = "⊤" if v else "⊥"
        return {"fnd": c, "fnd_corta": c, "fnc": c, "fnc_corta": c}
    unos, ceros = [], []
    for a in asignaciones(nombres):
        (unos if valor(f, a) else ceros).append([a[n] for n in nombres])
    r = {}
    if not unos:
        r["fnd"] = r["fnd_corta"] = "⊥"
    else:
        r["fnd"] = _escribir_normal(nombres, unos, "∧", "∨", "⊤")
        r["fnd_corta"] = _escribir_normal(nombres, _minima(nombres, unos), "∧", "∨", "⊤")
    if not ceros:
        r["fnc"] = r["fnc_corta"] = "⊤"
    else:
        r["fnc"] = _escribir_normal(nombres, ceros, "∨", "∧", "⊥")
        r["fnc_corta"] = _escribir_normal(nombres, _minima(nombres, ceros), "∨", "∧", "⊥")
    return r


# --- las herramientas: texto -> resultado ------------------------------------
#
# Cada una devuelve (en_linea, debajo): lo que va detrás de la expresión en
# la misma línea, y lo que va en las líneas de debajo (o None).

def _formula_o_indeterminado(texto):
    try:
        return leer(texto), None
    except NoEsFormula as e:
        return None, f"indeterminado: no es una fórmula ({e.motivo})"


def bien_formada(texto):
    try:
        leer_estricta(texto)
        return "es una fórmula (estricta, con todos sus paréntesis)", None
    except NoEsFormula as estr:
        try:
            f = leer(texto)
        except NoEsFormula as e:
            return f"no es una fórmula: {e.motivo}", None
        return (f"no es estricta ({estr.motivo}); con la precedencia del libro "
                f"es la fórmula {estricta(f)}"), None


def tabla_de_verdad(texto):
    f, mal = _formula_o_indeterminado(texto)
    if mal:
        return mal, None
    nombres = letras(f)
    if len(nombres) > MAX_LETRAS_TABLA:
        return (f"indeterminado: {len(nombres)} letras son {2 ** len(nombres)} filas; "
                f"la tabla se hace hasta {MAX_LETRAS_TABLA} letras"), None
    columnas = nombres + [corta(g) for g in subformulas(f) if g[0] in ("no", "bin")]
    formulas = [g for g in subformulas(f) if g[0] in ("no", "bin")]
    if f[0] == "const" or (f[0] == "atom" and not formulas):
        columnas = nombres + ([] if f[0] == "atom" else [f[1]])
        formulas = [] if f[0] == "atom" else [f]
    anchos = [len(c) for c in columnas]
    sep = " │ "

    def fila(valores):
        return sep.join(str(v).center(w) for v, w in zip(valores, anchos)).rstrip()

    lineas = [sep.join(columnas)]
    lineas.append("─┼─".join("─" * w for w in anchos))
    for a in asignaciones(nombres) if nombres else [{}]:
        lineas.append(fila([a[n] for n in nombres] + [valor(g, a) for g in formulas]))
    return None, "\n".join(lineas)


def clasificar(texto):
    f, mal = _formula_o_indeterminado(texto)
    if mal:
        return mal, None
    nombres = letras(f)
    if len(nombres) > MAX_LETRAS:
        return f"indeterminado: demasiadas letras ({len(nombres)})", None
    verdad, mentira = [], []
    for a in asignaciones(nombres):
        (verdad if valor(f, a) else mentira).append(a)
    total = len(verdad) + len(mentira)
    if not mentira:
        return f"tautología: vale 1 en las {total} asignaciones", None
    if not verdad:
        return f"contradicción: vale 0 en las {total} asignaciones (insatisfacible)", None
    return (f"contingente (satisfacible): vale 1 en {len(verdad)} de {total}; "
            f"p. ej. 1 con {_tupla(nombres, verdad[0])} y 0 con {_tupla(nombres, mentira[0])}"), None


def _partir_arriba(texto, signo):
    """Parte por `signo` fuera de paréntesis."""
    partes, nivel, actual = [], 0, ""
    for c in texto:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        if c == signo and nivel == 0:
            partes.append(actual)
            actual = ""
        else:
            actual += c
    partes.append(actual)
    return [p.strip() for p in partes]


def equivalencia(texto):
    partes = _partir_arriba(texto, "≡")
    if len(partes) != 2 or not all(partes):
        return "indeterminado: escribe dos fórmulas separadas por ≡ (φ ≡ ψ)", None
    formulas = []
    for p in partes:
        f, mal = _formula_o_indeterminado(p)
        if mal:
            return f"{mal}: «{p}»", None
        formulas.append(f)
    nombres = letras(*formulas)
    if len(nombres) > MAX_LETRAS:
        return f"indeterminado: demasiadas letras ({len(nombres)})", None
    for a in asignaciones(nombres):
        v1, v2 = valor(formulas[0], a), valor(formulas[1], a)
        if v1 != v2:
            return (f"no son equivalentes: con {_tupla(nombres, a)} la primera vale {v1} "
                    f"y la segunda {v2}"), None
    return "sí, son equivalentes: valen lo mismo en todas las asignaciones", None


def consecuencia(texto):
    partes = _partir_arriba(texto, "⊨")
    if len(partes) != 2 or not partes[1]:
        return "indeterminado: escribe premisas ⊨ conclusión (φ₁, φ₂ ⊨ ψ)", None
    premisas = [p for p in _partir_arriba(partes[0], ",") if p]
    formulas = []
    for p in premisas + [partes[1]]:
        f, mal = _formula_o_indeterminado(p)
        if mal:
            return f"{mal}: «{p}»", None
        formulas.append(f)
    nombres = letras(*formulas)
    if len(nombres) > MAX_LETRAS:
        return f"indeterminado: demasiadas letras ({len(nombres)})", None
    *ps, c = formulas
    for a in asignaciones(nombres):
        if all(valor(p, a) for p in ps) and not valor(c, a):
            return (f"no es consecuencia lógica: con {_tupla(nombres, a)} las premisas "
                    f"valen 1 y la conclusión 0"), None
    if not ps:
        return "sí: la conclusión es una tautología", None
    return "sí, es consecuencia lógica: donde las premisas valen 1, la conclusión también", None


def analizar(texto):
    f, mal = _formula_o_indeterminado(texto)
    if mal:
        return mal, None
    lineas = [f"Fórmula: {estricta(f)}"]
    if f[0] in ("atom", "const"):
        lineas.append("Es atómica: no tiene conectiva principal.")
    else:
        principal = "¬" if f[0] == "no" else f[1]
        inmediatas = [f[1]] if f[0] == "no" else [f[2], f[3]]
        lineas.append(f"Conectiva principal: {principal}")
        lineas.append("Subfórmulas inmediatas: " + ", ".join(estricta(g) for g in inmediatas))
    subf = subformulas(f)
    lineas.append(f"Nod = {nod(f)} · Rango = {rango(f)} · Subf ({len(subf)}): "
                  + ", ".join(estricta(g) for g in subf))
    lineas.append("Árbol sintáctico:")
    lineas += ["  " + l for l in _arbol(f)]
    return None, "\n".join(lineas)


def fnc(texto):
    return _normal(texto, "fnc", "FNC")


def fnd(texto):
    return _normal(texto, "fnd", "FND")


def _normal(texto, clave, nombre):
    f, mal = _formula_o_indeterminado(texto)
    if mal:
        return mal, None
    try:
        r = formas_normales(f)
    except NoEsFormula as e:
        return f"indeterminado: {e.motivo}", None
    if r[clave] == r[clave + "_corta"]:
        return f"{nombre}: {r[clave]}", None
    return f"{nombre}: {r[clave + '_corta']}   (canónica: {r[clave]})", None

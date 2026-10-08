# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Álgebra con incógnitas: resolver, simplificar, desarrollar, factorizar,
derivar e integrar. Usa sympy.

El texto del editor se lee con un analizador propio que construye las
expresiones de sympy directamente (sin pasar nunca texto a eval). Se
escribe como en el editor:

    2x + 3 = 7          x² − 5x + 6 = 0        sen(x)² + cos(x)²
    ∫ x² dx             ∫₀¹ x² dx               d/dx no: se dice "deriva"

- Las letras sueltas son incógnitas (reales): "2xy" es 2·x·y; x₁ es una.
- Funciones: sen/sin, cos, tg/tan, arcsen, arccos, arctg, ln, log, exp, √.
- π, e, i (unidad imaginaria) y φ (número áureo) son números, no incógnitas.
- La coma decimal es la española (2,5 = 5/2, exacto).
"""

import re

import sympy as sp

FUNCIONES = {
    "sen": sp.sin, "sin": sp.sin, "cos": sp.cos, "tg": sp.tan, "tan": sp.tan,
    "arcsen": sp.asin, "arcsin": sp.asin, "arccos": sp.acos, "arctg": sp.atan,
    "arctan": sp.atan, "ln": sp.log, "log": sp.log, "exp": sp.exp,
}
# Las mismas que calculo.py, para que un cálculo exacto con π o √ no se
# quede a medias por llevar un mcd: (nombre -> (función, argumentos)).
FUNCIONES_VARIAS = {
    "mcd": (lambda *a: sp.gcd(*a) if len(a) > 2 else sp.gcd(a[0], a[1]), None),
    "mcm": (lambda *a: sp.lcm(*a) if len(a) > 2 else sp.lcm(a[0], a[1]), None),
    "V": (lambda n, k: sp.ff(n, k), 2),
    "VR": (lambda n, k: n ** k, 2),
    "C": (lambda n, k: sp.binomial(n, k), 2),
    "CR": (lambda n, k: sp.binomial(n + k - 1, k), 2),
    "P": (lambda n: sp.factorial(n), 1),
}

SUPER = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6",
         "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-",
         "ˣ": "x", "ⁿ": "n", "ⁱ": "i", "ᵏ": "k", "ᵐ": "m"}
SUB = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6",
       "₇": "7", "₈": "8", "₉": "9"}
CIFRAS = "0123456789"


class NoSePuede(Exception):
    pass


_simbolos = {}


def incognita(nombre):
    if nombre not in _simbolos:
        _simbolos[nombre] = sp.Symbol(nombre, real=True)
    return _simbolos[nombre]


# --- leer ------------------------------------------------------------------

def _trozos(texto):
    fuera, i = [], 0
    pila = []     # "f": paréntesis de una función de varios argumentos
    while i < len(texto):
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        if c in CIFRAS:
            j = i
            while j < len(texto) and texto[j] in CIFRAS:
                j += 1
            dentro_de_funcion = pila and pila[-1] == "f"
            if (j + 1 < len(texto) and texto[j] in ",." and texto[j + 1] in CIFRAS
                    and not (dentro_de_funcion and texto[j] == ",")):
                k = j + 1
                while k < len(texto) and texto[k] in CIFRAS:
                    k += 1
                fuera.append(("num", sp.Rational(texto[i:k].replace(",", "."))))
                i = k
            else:
                fuera.append(("num", sp.Integer(texto[i:j])))
                i = j
            continue
        if c in SUPER:
            j = i
            while j < len(texto) and texto[j] in SUPER:
                j += 1
            fuera.append(("sup", "".join(SUPER[x] for x in texto[i:j])))
            i = j
            continue
        if c.isalpha() and c != "π" and c not in SUPER:
            j = i
            # ojo: "ˣ".isalpha() es True: los superíndices no son letras aquí
            while (j < len(texto) and texto[j].isalpha() and texto[j] != "π"
                   and texto[j] not in SUPER):
                j += 1
            palabra = texto[i:j]
            # una funcion conocida va entera; si no, letra a letra (2xy = 2·x·y)
            if palabra.lower() in FUNCIONES:
                fuera.append(("fun", palabra.lower()))
            elif palabra in FUNCIONES_VARIAS and j < len(texto) and texto[j] == "(":
                fuera.append(("varias", palabra))
            else:
                for k, letra in enumerate(palabra):
                    nombre = letra
                    if k == len(palabra) - 1:
                        while j < len(texto) and texto[j] in SUB:
                            nombre += texto[j]
                            j += 1
                    fuera.append(("var", nombre))
            i = j
            continue
        if c == "(":
            pila.append("f" if fuera and fuera[-1][0] == "varias" else "g")
        elif c == ")" and pila:
            pila.pop()
        fuera.append(("op", {"-": "−", "*": "·", "×": "·", "⋅": "·", ":": "÷",
                             "[": "(", "]": ")"}.get(c, c)))
        i += 1
    return fuera


class _Lector:
    def __init__(self, texto):
        self.s = _trozos(texto)
        self.i = 0

    def ver(self):
        return self.s[self.i] if self.i < len(self.s) else (None, None)

    def es(self, *ops):
        t, v = self.ver()
        return t == "op" and v in ops

    def esperar(self, op, que):
        if not self.es(op):
            raise NoSePuede(f"falta {que}")
        self.i += 1

    def expresion_entera(self):
        if not self.s:
            raise NoSePuede("no hay nada")
        e = self.suma()
        if self.i != len(self.s):
            raise NoSePuede(f"no entiendo lo que hay desde «{self.ver()[1]}»")
        return e

    def suma(self):
        a = self.producto()
        while self.es("+", "−"):
            op = self.ver()[1]
            self.i += 1
            b = self.producto()
            a = a + b if op == "+" else a - b
        return a

    def producto(self):
        a = self.unaria()
        while True:
            if self.es("·", "/", "÷"):
                op = self.ver()[1]
                self.i += 1
                b = self.unaria()
                if op == "·":
                    a = a * b
                else:
                    if b == 0:
                        raise NoSePuede("división entre 0")
                    a = a / b
            elif self._empieza_factor():
                a = a * self.potencia()          # 2x, x(y + 1), 3sen(x)
            else:
                return a

    def _empieza_factor(self):
        t, v = self.ver()
        return t in ("var", "fun", "num", "varias") or (t == "op" and v in ("(", "√", "π"))

    def unaria(self):
        if self.es("−"):
            self.i += 1
            return -self.unaria()
        if self.es("+"):
            self.i += 1
            return self.unaria()
        return self.potencia()

    def potencia(self):
        a = self.postfijo()
        t, v = self.ver()
        if t == "op" and v == "^":
            self.i += 1
            return a ** self.unaria()
        if t == "sup":
            self.i += 1
            signo, cuerpo = (-1, v[1:]) if v.startswith("-") else (1, v)
            if cuerpo.isalpha():                  # eˣ, xⁿ, e⁻ˣ
                return a ** (signo * sp.Mul(*(self._constante_o_incognita(c) for c in cuerpo)))
            try:
                return a ** sp.Integer(int(v))
            except ValueError:
                raise NoSePuede(f"exponente «{v}» sin número")
        return a

    @staticmethod
    def _constante_o_incognita(c):
        return {"e": sp.E, "i": sp.I}.get(c) or incognita(c)

    def postfijo(self):
        a = self.atomo()
        while self.es("!"):
            self.i += 1
            a = sp.factorial(a)
        return a

    def atomo(self):
        t, v = self.ver()
        self.i += 1
        if t == "num":
            return v
        if t == "var":
            # e, i y φ son números, no incógnitas (decisión de pipataki)
            if v == "e":
                return sp.E
            if v == "i":
                return sp.I
            if v == "φ":
                # su valor exacto: sympy no simplifica GoldenRatio (φ² − φ
                # se quedaba sin reducir); así da 1
                return (1 + sp.sqrt(5)) / 2
            return incognita(v)
        if t == "varias":
            f, cuantos = FUNCIONES_VARIAS[v]
            self.esperar("(", f"el paréntesis de {v}(…)")
            args = [self.suma()]
            while self.es(",", ";"):
                self.i += 1
                args.append(self.suma())
            self.esperar(")", f"cerrar {v}(…)")
            if cuantos is not None and len(args) != cuantos:
                raise NoSePuede(f"{v} pide {cuantos} número{'s' if cuantos > 1 else ''}")
            if cuantos is None and len(args) < 2:
                raise NoSePuede(f"{v} pide al menos dos números")
            return f(*args)
        if t == "fun":
            f = FUNCIONES[v]
            if self.es("("):
                self.i += 1
                x = self.suma()
                self.esperar(")", f"cerrar {v}(…)")
            else:
                x = self.potencia()
            r = f(x)
            if self.ver()[0] == "sup":           # sen(x)² = (sen x)²
                e = self.ver()[1]
                self.i += 1
                r = r ** sp.Integer(int(e))
            return r
        if t == "op":
            if v == "π":
                return sp.pi
            if v == "∞":
                return sp.oo
            if v == "√":
                return sp.sqrt(self.potencia())
            if v == "(":
                x = self.suma()
                self.esperar(")", "cerrar un paréntesis")
                return x
        raise NoSePuede(f"no entiendo «{v}»" if v else "falta algo al final")


def leer(texto):
    """Una expresión, o una ecuación (sympy.Eq) si lleva un solo «=»."""
    partes = texto.split("=")
    if len(partes) > 2:
        raise NoSePuede("hay más de un «=»")
    if len(partes) == 2:
        if not partes[0].strip() or not partes[1].strip():
            raise NoSePuede("a la ecuación le falta un lado")
        return sp.Eq(_Lector(partes[0]).expresion_entera(),
                     _Lector(partes[1]).expresion_entera(), evaluate=False)
    return _Lector(texto).expresion_entera()


# --- escribir ----------------------------------------------------------------

_A_SUPER = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def escribir(e):
    """De sympy al texto del editor: x², 2x, √(…), sen, ln, π, −."""
    if isinstance(e, sp.Equality):
        return f"{escribir(e.lhs)} = {escribir(e.rhs)}"
    s = sp.sstr(e, order="lex") if not isinstance(e, (list, tuple)) else str(e)
    s = re.sub(r"\*\*\((-?\d+)\)", lambda m: m.group(1).translate(_A_SUPER), s)
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_A_SUPER), s)
    s = s.replace("**", "^")
    s = s.replace("sqrt(", "√(")
    s = re.sub(r"√\((\d+|[A-Za-z])\)", r"√\1", s)     # √(2) -> √2
    for de, a in (("asin(", "arcsen("), ("acos(", "arccos("), ("atan(", "arctg("),
                  ("sin(", "sen("), ("tan(", "tg("), ("log(", "ln("), ("exp(", "e^(")):
        s = s.replace(de, a)
    s = re.sub(r"e\^\(([xnikm])\)", lambda m: "e" + "ˣⁿⁱᵏᵐ"["xnikm".index(m.group(1))], s)
    s = re.sub(r"e\^\((−?-?\d+)\)", lambda m: "e" + m.group(1).replace("−", "-").translate(_A_SUPER), s)
    s = re.sub(r"\bpi\b", "π", s)
    s = re.sub(r"\bE\b", "e", s)
    s = re.sub(r"\bI\b", "i", s)
    s = re.sub(r"\boo\b", "∞", s)
    # 2*x -> 2x, 2*(…) -> 2(…), 2*√ -> 2√ ; el resto, ·
    s = re.sub(r"(?<=\d)\*(?=[A-Za-z(√π])", "", s)
    s = re.sub(r"(?<=[A-Za-z₀-₉²³⁴⁵⁶⁷⁸⁹¹⁰])\*(?=[A-Za-z](?![a-z(]))", "", s)  # x*y -> xy
    s = re.sub(r"(?<=[)A-Za-z0-9₀-₉])\*(?=\()", "", s)   # (x − 1)(x + 1), x(x + 1)
    s = s.replace("*", "·")
    s = s.replace("-", "−")
    return s


def _variable(e, preferida="x"):
    libres = sorted(e.free_symbols, key=lambda s: s.name)
    if not libres:
        return None
    for s in libres:
        if s.name == preferida:
            return s
    return libres[0]


# --- herramientas: texto -> (en_linea, debajo) ----------------------------------

def _solucion(sol, incognitas):
    """Una solución (dict) como "x = 1, y = 2"."""
    return ", ".join(f"{escribir(k)} = {escribir(sol[k])}" for k in incognitas if k in sol)


def resolver(texto):
    """Una ecuación, o un sistema: una ecuación por línea."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    if not lineas:
        raise NoSePuede("no hay ecuación")
    ecuaciones = []
    for l in lineas:
        e = leer(l)
        if not isinstance(e, sp.Equality):
            raise NoSePuede(f"«{l.strip()}» no es una ecuación (le falta el «=»)")
        ecuaciones.append(sp.Eq(e.lhs, e.rhs))
    for e, l in zip(ecuaciones, lineas):
        if e is sp.false:
            # con incógnitas reales, sympy ya decide x² + 1 = 0 como falso
            con_letras = bool(leer(l).free_symbols)
            return ("sin solución real" if con_letras else "sin solución: la igualdad es falsa"), None
    ecuaciones = [e for e in ecuaciones if e is not sp.true]
    if not ecuaciones:
        return "se cumple siempre (identidad)", None
    incognitas = sorted(set().union(*(e.free_symbols for e in ecuaciones)), key=lambda s: s.name)
    if not incognitas:
        return "no hay incógnitas", None
    soluciones = sp.solve(ecuaciones, incognitas, dict=True)
    if not soluciones:
        return "sin solución real", None
    libres = [s for s in incognitas if all(s not in sol for sol in soluciones)]
    textos = [_solucion(sol, incognitas) for sol in soluciones]
    r = " o ".join(textos)
    if libres:
        r += f"   (infinitas soluciones: {', '.join(escribir(s) for s in libres)} libre{'s' if len(libres) > 1 else ''})"
    return r, None


def simplificar(texto):
    e = leer(texto)
    if isinstance(e, sp.Equality):
        # Una ecuación se simplifica pasando todo a un lado y quitando el
        # factor común: 2x + 4 = 2 -> x + 1 = 0.
        izq = sp.simplify(e.lhs - e.rhs)
        if izq == 0:
            return "se cumple siempre (identidad)", None
        num, _den = sp.fraction(sp.together(izq))
        num = sp.expand(num)
        contenido, primitiva = num.as_content_primitive()
        primitiva = sp.expand(primitiva)
        if primitiva.could_extract_minus_sign():
            primitiva = -primitiva
        return f"{escribir(primitiva)} = 0", None
    return "= " + escribir(sp.simplify(e)), None


def desarrollar(texto):
    e = leer(texto)
    if isinstance(e, sp.Equality):
        return f"{escribir(sp.expand(e.lhs))} = {escribir(sp.expand(e.rhs))}", None
    return "= " + escribir(sp.expand(e)), None


def factorizar(texto):
    e = leer(texto)
    if isinstance(e, sp.Equality):
        return f"{escribir(sp.factor(e.lhs - e.rhs))} = 0", None
    return "= " + escribir(sp.factor(e)), None


def derivar(texto):
    e = leer(texto)
    if isinstance(e, sp.Equality):
        raise NoSePuede("se deriva una expresión, no una ecuación")
    x = _variable(e)
    if x is None:
        return "derivada: 0 (no hay variable)", None
    d = sp.simplify(sp.diff(e, x))
    return f"d/d{escribir(x)}: {escribir(d)}", None


# Límites de la integral definida, en cualquiera de estas formas:
#     ∫₀¹ x² dx           subíndice y superíndice (solo enteros)
#     ∫₀^π sen(x) dx      _ y ^ con un número, π, e, ∞, una letra o (…)
#     ∫_(−1)^(π/2) …      lo mismo con paréntesis
#     ∫[0, π] sen(x) dx   como intervalo (separa «;» o «, »)
# Ojo: ¹ ² ³ no están en el bloque ⁰-⁹ de Unicode (son U+00B9, U+00B2, U+00B3).
_SUB_INT = "₀₁₂₃₄₅₆₇₈₉₋"
_SUPER_INT = "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"
_RE_LIMITE = re.compile(r"[−-]?(?:\d+(?:[.,]\d+)?|π|e|∞|[A-Za-z])")
_RE_CUERPO = re.compile(r"^(.*?)\s*d([A-Za-z][₀-₉]*)\s*$", re.S)


def _cerrar(s, i, abre, cierra):
    """Índice del cierre que empareja con s[i] == abre."""
    nivel = 0
    for j in range(i, len(s)):
        if s[j] == abre:
            nivel += 1
        elif s[j] == cierra:
            nivel -= 1
            if nivel == 0:
                return j
    raise NoSePuede(f"falta cerrar «{abre}» en los límites")


def _limite(s, i):
    """(texto del límite, siguiente índice) tras un _ o un ^."""
    if i < len(s) and s[i] == "(":
        j = _cerrar(s, i, "(", ")")
        return s[i + 1:j], j + 1
    m = _RE_LIMITE.match(s, i)
    if not m:
        raise NoSePuede("no entiendo el límite de la integral")
    return m.group(), m.end()


def _partes_integral(texto):
    """(abajo, arriba, cuerpo, variable); los límites, texto o None."""
    s = texto.strip()
    i, abajo, arriba = 1, None, None
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in _SUB_INT:
            j = i
            while j < len(s) and s[j] in _SUB_INT:
                j += 1
            abajo = s[i:j].translate(str.maketrans(_SUB_INT, "0123456789-"))
            i = j
        elif c in _SUPER_INT:
            j = i
            while j < len(s) and s[j] in _SUPER_INT:
                j += 1
            arriba = s[i:j].translate(str.maketrans(_SUPER_INT, "0123456789-"))
            i = j
        elif c == "_":
            abajo, i = _limite(s, i + 1)
        elif c == "^":
            arriba, i = _limite(s, i + 1)
        elif c == "[" and abajo is None and arriba is None:
            j = _cerrar(s, i, "[", "]")
            dentro = s[i + 1:j]
            partes = dentro.split(";") if ";" in dentro else re.split(r",\s+|,(?![0-9])", dentro)
            if len(partes) != 2:
                raise NoSePuede("el intervalo de la integral pide dos límites: ∫[a, b]")
            abajo, arriba = partes
            i = j + 1
        else:
            break
    m = _RE_CUERPO.match(s[i:])
    if not m:
        # sin diferencial (pipataki: "integral entre cero y dos de equis al
        # cuadrado integra"): la variable la elige integrar()
        if not s[i:].strip():
            raise NoSePuede("falta lo que se integra")
        return abajo, arriba, s[i:], None
    return abajo, arriba, m.group(1), m.group(2)


def _valor_limite(texto):
    texto = texto.strip()
    if texto in ("∞", "+∞"):
        return sp.oo
    if texto in ("−∞", "-∞"):
        return -sp.oo
    return leer(texto)


def integrar(texto):
    """∫ x² dx, ∫₀¹ x² dx, ∫₀^π …, ∫[a, b] …, o la expresión sola (respecto de x)."""
    if texto.strip().startswith("∫"):
        abajo, arriba, cuerpo, var = _partes_integral(texto)
        e = leer(cuerpo)
        # sin diferencial: x si está; si no, la única letra (o x si no hay)
        x = incognita(var) if var else (_variable(e) or incognita("x"))
        if abajo is not None or arriba is not None:
            if abajo is None or arriba is None:
                raise NoSePuede("la integral definida pide los dos límites")
            a, b = _valor_limite(abajo), _valor_limite(arriba)
            r = sp.integrate(e, (x, a, b))
            if r.has(sp.Integral):
                raise NoSePuede("no sé hacer esta integral")
            if r in (sp.oo, -sp.oo, sp.zoo) or r is sp.nan:
                raise NoSePuede("la integral no converge")
            return _numero(r), None
    else:
        if "∫" in texto:
            raise NoSePuede("escribe la integral como ∫ … dx (o ∫₀¹ … dx)")
        e = leer(texto)
        if isinstance(e, sp.Equality):
            raise NoSePuede("se integra una expresión, no una ecuación")
        x = _variable(e)
        if x is None:
            x = incognita("x")
    r = sp.integrate(e, x)
    if r.has(sp.Integral):
        raise NoSePuede("no sé hacer esta integral")
    return f"∫ d{escribir(x)}: {escribir(sp.simplify(r))} + C", None


def _numero(r):
    r = sp.nsimplify(r) if r.is_Float else r
    exacto = escribir(r)
    if r.is_Rational and r.q == 1:
        return f"= {exacto}"
    if r.is_Rational:
        # como en calculo.py: decimal exacto sin ≈ (7/8 = 0,875), ≈ si no acaba
        import calculo
        from fractions import Fraction
        return "= " + calculo.escribir(Fraction(int(r.p), int(r.q)))
    try:
        aprox = f"{float(r):.6f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")
    except TypeError:
        return f"= {exacto}"
    return f"= {exacto} (≈ {aprox})" if exacto != aprox else f"= {exacto}"


def calcular(texto):
    """Calcula con sympy lo que el cálculo exacto no sabe: los complejos (i)."""
    e = leer(texto)
    if isinstance(e, sp.Equality):
        raise NoSePuede("aquí no se resuelve: para ecuaciones, «resuelve»")
    libres = sorted(e.free_symbols, key=lambda s: s.name)
    if libres:
        raise NoSePuede(f"«{escribir(libres[0])}» no tiene valor")
    r = sp.nsimplify(sp.simplify(e)) if e.has(sp.Float) else sp.simplify(e)
    r = sp.expand(r) if r.has(sp.I) else r
    exacto = escribir(r)
    if r.is_Rational:
        # como calculo.py: la fracción y su decimal (exacto, o ≈ si no acaba)
        import calculo
        from fractions import Fraction
        return "= " + calculo.escribir(Fraction(int(r.p), int(r.q))), None
    re_, im_ = r.as_real_imag()
    if re_.is_Rational and im_.is_Rational:
        return f"= {exacto}", None
    a, b = (float(x) for x in sp.N(r).as_real_imag())
    def d(x):
        return f"{x:.6f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")
    aprox = d(a) if b == 0 else f"{d(a)} {'+' if b >= 0 else '−'} {d(abs(b))}i"
    return f"= {exacto} (≈ {aprox})", None


HERRAMIENTAS = {
    "calcula": calcular, "resuelve": resolver, "simplifica": simplificar, "desarrolla": desarrollar,
    "factoriza_algebra": factorizar, "deriva": derivar, "integra": integrar,
}


def aplicar(nombre, texto):
    """Lo que hace el proceso aparte: devuelve (en_linea, debajo) ya en texto."""
    try:
        return HERRAMIENTAS[nombre](texto)
    except NoSePuede as e:
        return f"indeterminado ({e})", None
    except (ZeroDivisionError, ValueError, TypeError, NotImplementedError) as e:
        return f"indeterminado ({e})", None

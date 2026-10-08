# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Cálculo: aritmética exacta, combinatoria, divisibilidad y conjuntos.

Se escribe como en el editor (Unicode):
    2 + 3 · 4        7 ÷ 2        3,5 · 2        2¹⁰        √9        5!
    mcd(12, 18)      mcm(4, 6)    17 mod 5       V(10, 4)   V⁴₁₀      C(5, 2)
    {1, 2} ∪ {2, 3}  |{a, b}|     ℘({1, 2})      2 ∈ {1, 2}           17 ≡ 2 (mod 5)

- Exacto con fracciones: 1 ÷ 3 da 1/3, no 0,333...
- La coma decimal es la española (3,14). Dentro de una función o de un
  conjunto, la coma separa: mcd(12,18) son dos números.
- Lo que no se puede calcular (entre 0, raíz de un negativo, factorial de
  algo que no es natural...) es "indeterminado", con el motivo.
"""

import itertools
import math
import re
from fractions import Fraction

MAX_DIGITOS = 3000          # un resultado más largo no se calcula
MAX_ELEMENTOS = 4096        # conjuntos más grandes, tampoco

SUPER = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6",
         "⁷": "7", "⁸": "8", "⁹": "9", "⁺": "+", "⁻": "-"}
SUB = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6",
       "₇": "7", "₈": "8", "₉": "9"}
FRACCIONES = {"½": Fraction(1, 2), "⅓": Fraction(1, 3), "¼": Fraction(1, 4),
              "¾": Fraction(3, 4), "⅔": Fraction(2, 3)}
FUNCIONES = {"mcd", "mcm", "V", "VR", "C", "CR", "P", "PR"}
RELACIONES = {"=", "≠", "<", ">", "≤", "≥", "∈", "∉", "⊆", "⊂", "⊄", "⊇", "⊃", "≡"}


CIFRAS = "0123456789"      # ojo: "¹".isdigit() es True en Python


# Números con nombre de letra (pipataki: "e", "pi", "fi" son sus números). La
# i, unidad imaginaria, no la sabe este módulo: con i calcula sympy
# (herramientas.py lo desvía).
CONSTANTES = {"e": None, "φ": None}   # se rellenan tras definir Irracional


class Indeterminado(Exception):
    pass


class Irracional(float):
    """Un número que ya no es exacto (√2, π...): se escribe con ≈."""


CONSTANTES.update({"e": Irracional(math.e), "φ": Irracional((1 + math.sqrt(5)) / 2)})


# --- símbolos sueltos -----------------------------------------------------

def _simbolos(texto):
    """(tipo, valor) con la coma decidida según dónde esté."""
    fuera, i = [], 0
    pila = []          # "f" función, "g" paréntesis, "c" conjunto, "|" valor absoluto
    while i < len(texto):
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        if c in CIFRAS:
            j = i
            while j < len(texto) and texto[j] in CIFRAS:
                j += 1
            # coma o punto decimal: pegado a cifras, y fuera de funciones y conjuntos
            if (j + 1 < len(texto) and texto[j] in ",." and texto[j + 1] in CIFRAS
                    and not (pila and pila[-1] in "fc" and texto[j] == ",")):
                k = j + 1
                while k < len(texto) and texto[k] in CIFRAS:
                    k += 1
                fuera.append(("num", Fraction(texto[i:k].replace(",", "."))))
                i = k
            else:
                fuera.append(("num", Fraction(int(texto[i:j]))))
                i = j
            continue
        if c in SUPER:
            j = i
            while j < len(texto) and texto[j] in SUPER:
                j += 1
            fuera.append(("sup", "".join(SUPER[x] for x in texto[i:j])))
            i = j
            continue
        if c in SUB:
            j = i
            while j < len(texto) and texto[j] in SUB:
                j += 1
            fuera.append(("sub", "".join(SUB[x] for x in texto[i:j])))
            i = j
            continue
        if c in FRACCIONES:
            fuera.append(("num", FRACCIONES[c]))
            i += 1
            continue
        if c.isalpha() and c != "π":
            j = i
            while j < len(texto) and texto[j].isalpha() and texto[j] != "π":
                j += 1
            palabra = texto[i:j]
            fuera.append(("id", palabra))
            i = j
            continue
        if texto.startswith("(mod", i) or texto.startswith("( mod", i):
            fuera.append(("op", "(mod"))
            pila.append("g")
            i = texto.index("mod", i) + 3
            continue
        if c == "(":
            pila.append("f" if fuera and fuera[-1][0] in ("id", "sup", "sub") or
                        (fuera and fuera[-1] == ("op", "℘")) else "g")
        elif c == ")":
            if pila:
                pila.pop()
        elif c == "{":
            pila.append("c")
        elif c == "}":
            if pila:
                pila.pop()
        elif c == "|":
            if pila and pila[-1] == "|":
                pila.pop()
            else:
                pila.append("|")
        fuera.append(("op", {"-": "−", "*": "·", "×": "×", "⋅": "·", ":": "÷",
                             "^": "^", "<=": "≤"}.get(c, c)))
        i += 1
    return fuera


# --- valores --------------------------------------------------------------

def _es_num(v):
    return isinstance(v, (Fraction, Irracional)) and not isinstance(v, bool)


def _entero(v, para):
    if isinstance(v, Fraction) and v.denominator == 1:
        return v.numerator
    raise Indeterminado(f"{para} pide números enteros")


def _natural(v, para):
    n = _entero(v, para)
    if n < 0:
        raise Indeterminado(f"{para} pide números naturales")
    return n


def _vigilar(v):
    if isinstance(v, Fraction):
        if len(str(abs(v.numerator))) > MAX_DIGITOS or len(str(v.denominator)) > MAX_DIGITOS:
            raise Indeterminado("el resultado es demasiado grande")
    if isinstance(v, frozenset) and len(v) > MAX_ELEMENTOS:
        raise Indeterminado("el conjunto es demasiado grande")
    return v


def _num(v, para):
    if not _es_num(v):
        raise Indeterminado(f"{para} pide números")
    return v


def _potencia(a, b):
    _num(a, "una potencia"), _num(b, "una potencia")
    if a == 0 and b == 0:
        raise Indeterminado("0⁰")
    if a == 0 and b < 0:
        raise Indeterminado("división entre 0")
    if isinstance(a, Fraction) and isinstance(b, Fraction) and b.denominator == 1:
        if abs(b.numerator) * max(1, math.log10(max(abs(a.numerator), a.denominator, 2))) > MAX_DIGITOS:
            raise Indeterminado("el resultado es demasiado grande")
        return a ** b.numerator
    if a < 0:
        raise Indeterminado("potencia no entera de un negativo")
    return Irracional(float(a) ** float(b))


def _raiz(a):
    _num(a, "la raíz")
    if a < 0:
        raise Indeterminado("raíz cuadrada de un negativo")
    if isinstance(a, Fraction):
        n, d = math.isqrt(a.numerator), math.isqrt(a.denominator)
        if n * n == a.numerator and d * d == a.denominator:
            return Fraction(n, d)
    return Irracional(math.sqrt(a))


def _factorial(a):
    n = _natural(a, "el factorial")
    if n > 1000:
        raise Indeterminado("el factorial es demasiado grande")
    return Fraction(math.factorial(n))


def _funcion(nombre, args):
    if nombre in ("mcd", "mcm"):
        if len(args) < 2:
            raise Indeterminado(f"{nombre} pide al menos dos números")
        ns = [_entero(a, nombre) for a in args]
        if nombre == "mcd":
            if all(n == 0 for n in ns):
                raise Indeterminado("mcd(0, 0)")
            return Fraction(math.gcd(*ns))
        return Fraction(math.lcm(*ns))
    if nombre == "P":
        if len(args) != 1:
            raise Indeterminado("P(n) pide un número")
        return _factorial(args[0])
    if nombre == "PR":
        # permutaciones con repetición: PR(n; a, b, ...) = n! / (a!·b!·...)
        if len(args) < 2:
            raise Indeterminado("PR pide n y las repeticiones: PR(n, a, b...)")
        n, *rep = [_natural(a, "PR") for a in args]
        if sum(rep) != n:
            raise Indeterminado("en PR las repeticiones tienen que sumar n")
        r = math.factorial(n)
        for k in rep:
            r //= math.factorial(k)
        return Fraction(r)
    if len(args) != 2:
        raise Indeterminado(f"{nombre}(n, k) pide dos números")
    n, k = (_natural(a, nombre) for a in args)
    if nombre == "V":
        return Fraction(math.perm(n, k))
    if nombre == "VR":
        return _potencia(Fraction(n), Fraction(k))
    if nombre == "C":
        return Fraction(math.comb(n, k))
    if nombre == "CR":
        return Fraction(math.comb(n + k - 1, k)) if n > 0 else Fraction(int(k == 0))
    raise Indeterminado(f"no conozco la función {nombre}")


def _operar(op, a, b):
    if op in "+−":
        if isinstance(a, frozenset) or isinstance(b, frozenset):
            raise Indeterminado(f"«{op}» con conjuntos: usa ∪ o ∖")
        _num(a, op), _num(b, op)
        r = a + b if op == "+" else a - b
        return Irracional(r) if isinstance(a, Irracional) or isinstance(b, Irracional) else r
    if op in "·×":
        if isinstance(a, frozenset) and isinstance(b, frozenset) and op == "×":
            if len(a) * len(b) > MAX_ELEMENTOS:
                raise Indeterminado("el producto cartesiano es demasiado grande")
            return frozenset(itertools.product(a, b))
        _num(a, op), _num(b, op)
        r = a * b
        return Irracional(r) if isinstance(a, Irracional) or isinstance(b, Irracional) else r
    if op in "÷/":
        _num(a, op), _num(b, op)
        if b == 0:
            raise Indeterminado("división entre 0")
        if isinstance(a, Irracional) or isinstance(b, Irracional):
            return Irracional(a / b)
        return Fraction(a) / Fraction(b)
    if op == "mod":
        x, n = _entero(a, "mod"), _entero(b, "mod")
        if n == 0:
            raise Indeterminado("módulo 0")
        return Fraction(x % n)
    if op in "∪∩∖":
        if not (isinstance(a, frozenset) and isinstance(b, frozenset)):
            raise Indeterminado(f"«{op}» es de conjuntos")
        return a | b if op == "∪" else (a & b if op == "∩" else a - b)
    if op == "^":
        return _potencia(a, b)
    raise Indeterminado(f"no sé operar «{op}»")


def _relacion(op, a, b, modulo=None):
    if op == "≡":
        if modulo is None:
            raise Indeterminado("≡ entre números pide (mod n)")
        n = _entero(modulo, "mod")
        if n == 0:
            raise Indeterminado("módulo 0")
        return (_entero(a, "≡") - _entero(b, "≡")) % n == 0
    if op == "=":
        return a == b
    if op == "≠":
        return a != b
    if op in "<>≤≥":
        _num(a, op), _num(b, op)
        return {"<": a < b, ">": a > b, "≤": a <= b, "≥": a >= b}[op]
    if op in "∈∉":
        if not isinstance(b, frozenset):
            raise Indeterminado(f"a la derecha de «{op}» tiene que ir un conjunto")
        return (a in b) == (op == "∈")
    if not (isinstance(a, frozenset) and isinstance(b, frozenset)):
        raise Indeterminado(f"«{op}» es entre conjuntos")
    return {"⊆": a <= b, "⊂": a < b, "⊄": not a <= b, "⊇": a >= b, "⊃": a > b}[op]


# --- lectura y cálculo a la vez ---------------------------------------------

class _Lector:
    def __init__(self, texto):
        self.s = _simbolos(texto)
        self.i = 0
        self.en_conjunto = 0

    def ver(self, k=0):
        return self.s[self.i + k] if self.i + k < len(self.s) else (None, None)

    def tomar(self):
        x = self.ver()
        self.i += 1
        return x

    def es(self, *ops):
        t, v = self.ver()
        return t == "op" and v in ops

    def esperar(self, op, que):
        if not self.es(op):
            raise Indeterminado(f"falta {que}")
        self.i += 1

    def todo(self):
        if not self.s:
            raise Indeterminado("no hay nada que calcular")
        v = self.relacion()
        if self.i != len(self.s):
            t, x = self.ver()
            raise Indeterminado(f"no entiendo lo que hay desde «{x}»")
        return v

    def relacion(self):
        a = self.suma()
        t, op = self.ver()
        if t == "op" and op in RELACIONES:
            self.i += 1
            b = self.suma()
            modulo = None
            if op == "≡":
                if self.es("(mod"):
                    self.i += 1
                    modulo = self.suma()
                    self.esperar(")", "cerrar el (mod n)")
                elif not (isinstance(a, frozenset) or isinstance(b, frozenset)):
                    raise Indeterminado("≡ entre números pide (mod n)")
            return _relacion(op, a, b, modulo)
        return a

    def suma(self):
        a = self.producto()
        while self.es("+", "−", "∪", "∖"):
            op = self.tomar()[1]
            a = _vigilar(_operar(op, a, self.producto()))
        return a

    def producto(self):
        a = self.unaria()
        while True:
            t, v = self.ver()
            if t == "op" and v in ("·", "×", "÷", "/", "∩"):
                self.i += 1
                a = _vigilar(_operar(v, a, self.unaria()))
            elif t == "id" and v == "mod":
                self.i += 1
                a = _operar("mod", a, self.unaria())
            elif self._empieza_factor() and _es_num(a):
                # multiplicación implícita: 2(3 + 1), 2π, 3√2
                a = _vigilar(_operar("·", a, self.unaria()))
            else:
                return a

    def _empieza_factor(self):
        t, v = self.ver()
        return (t == "op" and v in ("(", "√", "π")) or (t == "id" and (v in FUNCIONES or v in CONSTANTES))

    def unaria(self):
        if self.es("−"):
            self.i += 1
            return _operar("−", Fraction(0), self.unaria())
        if self.es("+"):
            self.i += 1
            return self.unaria()
        if self.es("√"):
            self.i += 1
            return _raiz(self.unaria())
        return self.potencia()

    def potencia(self):
        a = self.postfijo()
        t, v = self.ver()
        if t == "op" and v == "^":
            self.i += 1
            return _vigilar(_potencia(a, self.unaria()))
        if t == "sup":
            self.i += 1
            try:
                e = Fraction(int(v))
            except ValueError:
                raise Indeterminado(f"exponente «{v}» sin número")
            return _vigilar(_potencia(a, e))
        return a

    def postfijo(self):
        a = self.atomo()
        while self.es("!"):
            self.i += 1
            a = _factorial(a)
        return a

    def _argumentos(self, cierre):
        args = [self.relacion()]
        while self.es(",", ";"):
            self.i += 1
            args.append(self.relacion())
        self.esperar(cierre, f"cerrar con «{cierre}»")
        return args

    def atomo(self):
        t, v = self.tomar()
        if t == "num":
            return v
        if t == "op" and v == "π":
            return Irracional(math.pi)
        if t == "op" and v == "(":
            x = self.relacion()
            self.esperar(")", "cerrar un paréntesis")
            return x
        if t == "op" and v == "{":
            if self.es("}"):
                self.i += 1
                return frozenset()
            self.en_conjunto += 1
            elementos = self._argumentos("}")
            self.en_conjunto -= 1
            return _vigilar(frozenset(elementos))
        if t == "op" and v == "∅":
            return frozenset()
        if t == "op" and v == "|":
            x = self.suma()
            self.esperar("|", "cerrar el |…|")
            if isinstance(x, frozenset):
                return Fraction(len(x))
            return abs(_num(x, "|…|"))
        if t == "op" and v == "℘":
            self.esperar("(", "el paréntesis de ℘(…)")
            a = self.relacion()
            self.esperar(")", "cerrar ℘(…)")
            if not isinstance(a, frozenset):
                raise Indeterminado("℘ es de un conjunto")
            if len(a) > 12:
                raise Indeterminado("℘ de un conjunto de más de 12 elementos es demasiado grande")
            elems = list(a)
            return frozenset(frozenset(c) for r in range(len(elems) + 1)
                             for c in itertools.combinations(elems, r))
        if t == "id":
            if v in FUNCIONES:
                # V⁴₁₀: arriba k, abajo n (como en el libro)
                arriba = abajo = None
                while self.ver()[0] in ("sup", "sub"):
                    tt, vv = self.tomar()
                    if tt == "sup":
                        arriba = vv
                    else:
                        abajo = vv
                if arriba is not None or abajo is not None:
                    if v == "P" and abajo is not None and arriba is None:
                        return _funcion("P", [Fraction(int(abajo))])
                    if arriba is None or abajo is None:
                        raise Indeterminado(f"{v} pide los dos números: {v}ᵏₙ")
                    return _vigilar(_funcion(v, [Fraction(int(abajo)), Fraction(int(arriba))]))
                self.esperar("(", f"el paréntesis de {v}(…)")
                return _vigilar(_funcion(v, self._argumentos(")")))
            if v in CONSTANTES:
                return CONSTANTES[v]
            if self.en_conjunto:
                return v
            raise Indeterminado(f"«{v}» no tiene valor")
        raise Indeterminado(f"no entiendo «{v}»" if v else "falta algo al final")


# --- escribir ---------------------------------------------------------------

def _decimal(x, cifras=6):
    if isinstance(x, Fraction) and x.denominator == 1:
        return str(x.numerator).replace("-", "−")
    s = f"{float(x):.{cifras}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",").replace("-", "−")


def _decimal_exacto(f):
    """El desarrollo decimal de una fracción, si es finito (denominador 2ᵃ5ᵇ)."""
    d = f.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d != 1:
        return None
    cifras = 0
    while (f * 10 ** cifras).denominator != 1:
        cifras += 1
    n = f * 10 ** cifras
    s = f"{abs(n.numerator):0{cifras + 1}d}"
    s = s[:-cifras] + "," + s[-cifras:]
    return ("−" if f < 0 else "") + s


def escribir(v):
    if isinstance(v, bool):
        return "cierto" if v else "falso"
    if isinstance(v, Irracional):
        return "≈ " + _decimal(v)
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator).replace("-", "−")
        frac = f"{v.numerator}/{v.denominator}".replace("-", "−")
        exacto = _decimal_exacto(v)
        return f"{frac} ({exacto})" if exacto else f"{frac} (≈ {_decimal(v)})"
    if isinstance(v, frozenset):
        return "{" + ", ".join(_elemento(x) for x in sorted(v, key=_orden)) + "}"
    if isinstance(v, tuple):
        return "(" + ", ".join(_elemento(x) for x in v) + ")"
    return str(v)


def _elemento(x):
    if isinstance(x, (Fraction, Irracional)):
        e = escribir(x)
        return e.split(" (")[0].replace("≈ ", "")
    return escribir(x)


def _orden(x):
    if isinstance(x, (Fraction, Irracional)):
        return (0, float(x), "")
    if isinstance(x, str):
        return (1, 0, x)
    if isinstance(x, tuple):
        return (2, 0, str([_orden(e) for e in x]))
    return (3, len(x), escribir(x))


# --- las herramientas: texto -> (en_linea, debajo) ----------------------------

def calcular(texto):
    """'2 + 3' -> ('= 5', None); '2 ∈ {1, 2}' -> ('— cierto', None)."""
    try:
        v = _Lector(texto).todo()
    except Indeterminado as e:
        return f"= indeterminado ({e})", None
    except (ZeroDivisionError,):
        return "= indeterminado (división entre 0)", None
    except (OverflowError, ValueError) as e:
        return f"= indeterminado ({e})", None
    if isinstance(v, bool):
        return f"— {escribir(v)}", None
    e = escribir(v)
    return (e if e.startswith("≈") else f"= {e}"), None


def _primos_de(n):
    factores, d = {}, 2
    while d * d <= n:
        while n % d == 0:
            factores[d] = factores.get(d, 0) + 1
            n //= d
        d += 1 if d == 2 else 2
        if d > 10 ** 7:
            raise Indeterminado("el número es demasiado grande para factorizar aquí")
    if n > 1:
        factores[n] = factores.get(n, 0) + 1
    return factores


_SUPER_DE = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def factorizar(texto):
    try:
        v = _Lector(texto).todo()
        n = _entero(v, "factorizar")
        if n < 2:
            return "— indeterminado (se factorizan los naturales desde 2)", None
        f = _primos_de(n)
    except (Indeterminado, ValueError, ZeroDivisionError) as e:
        return f"— indeterminado ({e})", None
    partes = " · ".join(str(p) + (str(k).translate(_SUPER_DE) if k > 1 else "")
                        for p, k in sorted(f.items()))
    if len(f) == 1 and list(f.values())[0] == 1:
        return f"— {n} es primo", None
    return f"— {n} = {partes} (no es primo)", None


# Lo que deja un cálculo anterior detrás de la expresión, para quitarlo al
# volver a calcular la misma línea.
_RE_RESULTADO = re.compile(
    r"(\s+—\s.*"                                   # — cierto / — 360 = 2³ · ...
    r"|\s+=\s+indeterminado\b.*"
    r"|\s+=\s+−?\d+/\d+\s+\((?:≈\s)?−?[\d,]+\)"     # = 7/2 (3,5)
    r"|\s+≈\s+−?[\d,]+)\s*$")


def quitar_resultado(linea):
    return _RE_RESULTADO.sub("", linea)

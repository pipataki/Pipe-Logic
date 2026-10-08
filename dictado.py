# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Del texto que reconoce Vosk a lo que se escribe en el editor.

Todo sale de simbolos.json: simbolos, letras, indices, decimales y ordenes.
Aqui no hay ninguna lista de palabras; solo la mecanica.

    traducir("pe sub uno and no cu")  ->  [{"tipo": "texto", "texto": "p₁ ∧ ¬q"}]

Reglas:
- Gana la coincidencia mas larga: "no pertenece a" antes que "no".
- Un numero se lee entero ("dos mil veintiséis" -> 2026); seguido de
  "coma" y otro numero, con decimales ("tres coma catorce" -> 3,14).
- "sub" / "super" + numero o letra, con "más"/"menos" delante si se quiere:
  "pe sub doce" -> p₁₂, "equis super menos uno" -> x⁻¹.
- Una letra seguida de "mayúscula" va en mayuscula.
- Lo que no se entiende no se escribe: se devuelve aparte para avisar.
"""

import json
import re
import unicodedata
from pathlib import Path

import numeros

SIMBOLOS = Path(__file__).resolve().parent / "simbolos.json"


# Las palabras de los números tal como las escribe Vosk (con tildes), para
# su gramática. Propio de Pipe-Logic: numeros.py es copia exacta del de VC
# y no lleva nada nuestro.
_NUMEROS_CON_TILDE = {
    "dieciseis": "dieciséis", "veintidos": "veintidós", "veintitres": "veintitrés",
    "veintiseis": "veintiséis", "millon": "millón", "billon": "billón",
}


def palabras_de_numeros():
    todas = (set(numeros.UNITS) | set(numeros.TEENS) | set(numeros.TWENTIES)
             | set(numeros.TENS) | set(numeros.HUNDREDS))
    for palabras, _ in numeros._SCALES:
        todas |= palabras
    todas.add("y")
    return sorted(_NUMEROS_CON_TILDE.get(p, p) for p in todas)


def normalizar(palabra):
    """Minusculas y sin tildes (la ñ se queda: es otra letra)."""
    palabra = palabra.lower().replace("ñ", "\0")
    sin = "".join(c for c in unicodedata.normalize("NFD", palabra)
                  if unicodedata.category(c) != "Mn")
    return sin.replace("\0", "ñ")


def _tokens(frase):
    return tuple(normalizar(p) for p in frase.split())


class Traductor:
    def __init__(self, datos=None):
        if datos is None:
            datos = json.loads(SIMBOLOS.read_text(encoding="utf-8"))
        self.datos = datos
        self.frases = {}          # tokens -> (tipo, valor)
        self.sub = {}             # "1" -> "₁", "n" -> "ₙ", "+" -> "₊"
        self.super = {}

        def anotar(frase, tipo, valor):
            t = _tokens(frase)
            if t in self.frases and self.frases[t] != (tipo, valor):
                raise ValueError(f"'{frase}' significa dos cosas: "
                                 f"{self.frases[t]} y {(tipo, valor)}")
            self.frases[t] = (tipo, valor)

        for grupo in datos["grupos"]:
            for sim in grupo["simbolos"]:
                for frase in sim.get("dichos", []) + sim.get("oido", []):
                    anotar(frase, "simbolo", (sim["s"], bool(sim.get("binario"))))
                if "sub" in sim:
                    self.sub[sim["sub"]] = sim["s"]
                if "super" in sim:
                    self.super[sim["super"]] = sim["s"]
        for letra, frases in datos["letras"].items():
            if letra.startswith("_"):
                continue
            for frase in frases:
                anotar(frase, "letra", letra)
        for cual in ("sub", "super"):
            for frase in datos["indices"][cual]:
                anotar(frase, "indice", cual)
        for orden, frases in datos["ordenes"].items():
            for frase in frases:
                anotar(frase, "orden", orden)
        for grupo_h, lista in datos.get("herramientas", {}).items():
            if grupo_h.startswith("_"):
                continue
            for h in lista:
                for frase in h["dichos"]:
                    anotar(frase, "herramienta", h["id"])

        ient = datos.get("integral_entre", {})
        for frase in ient.get("dichos", []):
            anotar(frase, "integral_entre", ient["plantilla"])
        self.y_integral = {_tokens(f) for f in ient.get("y", [])}
        self.cierre_integral = {_tokens(f) for f in ient.get("cierre", [])}

        comb = datos.get("combinatorio", {})
        for frase in comb.get("dichos", []):
            anotar(frase, "combinatorio", comb["plantilla"])

        self.mayuscula = {_tokens(f) for f in datos["mayuscula"]}
        self.coma = {_tokens(f) for f in datos["decimales"]["dichos"]}
        self.separador = datos["decimales"]["separador"]
        self.mas = {t for t, (tipo, v) in self.frases.items()
                    if tipo == "simbolo" and v[0] == "+"}
        self.menos = {t for t, (tipo, v) in self.frases.items()
                      if tipo == "simbolo" and v[0] == "−"}
        self.largo = max(len(t) for t in self.frases)

    # -- piezas sueltas -------------------------------------------------------

    def _frase(self, toks, i):
        """La frase conocida mas larga que empieza en toks[i]."""
        for n in range(min(self.largo, len(toks) - i), 0, -1):
            hallada = self.frases.get(tuple(toks[i:i + n]))
            if hallada:
                return hallada, n
        return None, 0

    def _en(self, conjunto, toks, i):
        """Cuantos tokens ocupa en toks[i] alguna frase del conjunto (0 si ninguna)."""
        for t in sorted(conjunto, key=len, reverse=True):
            if tuple(toks[i:i + len(t)]) == t:
                return len(t)
        return 0

    def _numero(self, toks, i):
        """(texto, consumidos): un numero, con sus decimales si los dice."""
        valor, n = numeros.parse_number_prefix(list(toks), i)
        if valor is None:
            return None, 0
        texto = str(valor)
        j = i + n
        c = self._en(self.coma, toks, j)
        if c:
            decimales, k = "", j + c
            while True:
                v, m = numeros.parse_number_prefix(list(toks), k)
                if v is None:
                    break
                decimales += str(v)
                k += m
            if decimales:
                texto += self.separador + decimales
                j = k
        return texto, j - i

    def _indice(self, cual, toks, i):
        """(texto, consumidos) del indice que va detras de 'sub'/'super'."""
        mapa = self.sub if cual == "sub" else self.super
        texto, j = "", i
        for signos, clave in ((self.mas, "+"), (self.menos, "-")):
            n = self._en(signos, toks, j)
            if n:
                texto += clave
                j += n
                break
        valor, n = numeros.parse_number_prefix(list(toks), j)
        if valor is not None:
            texto += str(valor)
            j += n
        else:
            hallada, n = self._frase(toks, j)
            if hallada and hallada[0] == "letra":
                texto += hallada[1]
                j += n
            elif hallada and hallada[0] == "simbolo" and len(hallada[1][0]) == 1:
                texto += hallada[1][0]           # "sub i": i ya no es letra, es el número
                j += n
        if not texto:
            return None, 0
        if any(c not in mapa for c in texto):
            # No cabe en un superíndice (π, e...): se escribe ^(…) / _(…),
            # que el álgebra entiende ("super pi" -> ^(π), para ∫₀^(π)).
            return ("^(" if cual == "super" else "_(") + texto.replace("-", "−") + ")", j - i
        return "".join(mapa[c] for c in texto), j - i

    def _limite(self, toks, i):
        """(texto, consumidos): un límite de integral: número (con
        decimales), letra o número con nombre (π, e, ∞), con 'menos' delante."""
        signo, j = "", i
        n = self._en(self.menos, toks, j)
        if n:
            signo, j = "−", j + n
        num, m = self._numero(toks, j)
        if num is not None:
            return signo + num, j - i + m
        hallada, m = self._frase(toks, j)
        if hallada and (hallada[0] == "letra" or
                        (hallada[0] == "simbolo" and len(hallada[1][0]) == 1)):
            v = hallada[1] if hallada[0] == "letra" else hallada[1][0]
            return signo + v, j - i + m
        return None, 0

    @staticmethod
    def _poner_diferencial(piezas, desde):
        """El diferencial de una integral dictada (pipataki, 7-oct-2026):
        - ya dicho ("de equis" -> d, x): se deja;
        - una letra suelta al final, tras algo más, es el diferencial:
          "… equis al cuadrado te integra" -> x²dt;
        - si no, nada: lo decide el álgebra (x si está; si no, la única
          letra que haya): "… equis al cuadrado integra" -> ∫[0, 2]x².
        """
        cuerpo = piezas[desde:]
        texto = "".join(cuerpo).rstrip()
        if re.search(r"d[A-Za-z]$", texto) and len(cuerpo) >= 2 and cuerpo[-2] == "d":
            return
        if len(cuerpo) >= 2 and re.fullmatch(r"[A-Za-z]", cuerpo[-1]):
            piezas[-1] = "d" + cuerpo[-1]

    def _intervalo(self, toks, i):
        """'A y B de' desde toks[i] -> (A, B, consumidos) o None.

        Hasta el 'de' no se cierra; se prueba cada 'y' y vale el que deja
        un límite completo a cada lado. Así "treinta y cinco y cuarenta de"
        es 35 y 40, y "treinta y cinco de" es 30 y 5.
        """
        for fin in range(i, len(toks)):
            c = self._en(self.cierre_integral, toks, fin)
            if not c:
                continue
            for medio in range(i + 1, fin):
                y = self._en(self.y_integral, toks, medio)
                if not y:
                    continue
                # cada límite solo puede leer su trozo: si no, "treinta"
                # se come "y cinco" y se lee 35
                a_txt, ka = self._limite(toks[:medio], i)
                b_txt, kb = self._limite(toks[:fin], medio + y)
                if (a_txt is not None and b_txt is not None
                        and i + ka == medio and medio + y + kb == fin):
                    return a_txt, b_txt, fin + c - i
            return None        # el primer 'de' cierra: si no cuadra, no vale
        return None

    def _operando(self, toks, i):
        """(texto, consumidos): un numero entero o una letra en toks[i]."""
        valor, n = numeros.parse_number_prefix(list(toks), i)
        if valor is not None:
            return str(valor), n
        hallada, n = self._frase(toks, i)
        if hallada and hallada[0] == "letra":
            return hallada[1], n
        return None, 0

    # -- la frase entera ------------------------------------------------------

    def traducir(self, frase):
        """Devuelve (acciones, no_entendidas).

        acciones: lista de {"tipo": "texto", "texto": ...},
                  {"tipo": "orden", "orden": ...} y
                  {"tipo": "herramienta", "herramienta": ...},
                  en el orden en que se dijeron.
        no_entendidas: palabras que no se han escrito.
        """
        toks = list(_tokens(frase.replace("[unk]", " ")))
        acciones, piezas, no_entendidas = [], [], []
        cuerpo_integral = None   # en piezas, dónde empieza lo que se integra

        def soltar():
            if piezas:
                texto = " ".join("".join(piezas).split())
                if piezas[0].startswith(" "):
                    texto = " " + texto
                if piezas[-1].endswith(" "):
                    texto += " "
                acciones.append({"tipo": "texto", "texto": texto})
                piezas.clear()

        i = 0
        while i < len(toks):
            hallada, n = self._frase(toks, i)
            num, m = self._numero(toks, i)
            if num is not None and m >= n:
                piezas.append(num)
                i += m
                continue
            if not hallada:
                no_entendidas.append(toks[i])
                i += 1
                continue
            tipo, valor = hallada
            i += n
            if tipo == "simbolo":
                s, binario = valor
                piezas.append(f" {s} " if binario else s)
                if s == "∫":
                    cuerpo_integral = len(piezas)
            elif tipo == "letra":
                k = self._en(self.mayuscula, toks, i)
                piezas.append(valor.upper() if k else valor)
                i += k
            elif tipo == "indice":
                texto, k = self._indice(valor, toks, i)
                if texto is None:
                    no_entendidas.append(" ".join(toks[i - n:i]))
                else:
                    piezas.append(texto)
                    i += k
            elif tipo == "integral_entre":
                # "integral entre cero y pi de" -> ∫[0, π]
                hallado = self._intervalo(toks, i)
                if hallado is None:
                    no_entendidas.append(" ".join(toks[i - n:i]))
                else:
                    a_txt, b_txt, k = hallado
                    piezas.append(valor.format(a=a_txt, b=b_txt))
                    cuerpo_integral = len(piezas)
                    i += k
            elif tipo == "combinatorio":
                # "n sobre k": n es lo ultimo escrito (un numero o una letra)
                k_texto, k = self._operando(toks, i)
                n_texto = piezas[-1] if piezas else ""
                if k_texto is None or not re.fullmatch(r"[0-9]+|[A-Za-zñ]", n_texto):
                    no_entendidas.append(" ".join(toks[i - n:i]))
                else:
                    piezas[-1] = valor.format(n=n_texto, k=k_texto)
                    i += k
            elif tipo == "orden":
                soltar()
                acciones.append({"tipo": "orden", "orden": valor})
            elif tipo == "herramienta":
                if valor == "integra" and cuerpo_integral is not None:
                    self._poner_diferencial(piezas, cuerpo_integral)
                    cuerpo_integral = None
                soltar()
                acciones.append({"tipo": "herramienta", "herramienta": valor})
        soltar()
        return acciones, no_entendidas

    # -- para Vosk ------------------------------------------------------------

    def palabras_para_vosk(self):
        """Todas las palabras que pueden decirse, como las escribe Vosk."""
        d = self.datos
        frases = []
        for grupo in d["grupos"]:
            for sim in grupo["simbolos"]:
                frases += sim.get("dichos", []) + sim.get("oido", [])
        for letra, fs in d["letras"].items():
            if not letra.startswith("_"):
                frases += fs
        frases += d["mayuscula"] + d["indices"]["sub"] + d["indices"]["super"]
        frases += d["decimales"]["dichos"]
        frases += d.get("combinatorio", {}).get("dichos", [])
        frases += d.get("integral_entre", {}).get("dichos", []) + d.get("integral_entre", {}).get("y", [])
        for fs in d["ordenes"].values():
            frases += fs
        for grupo_h, lista in d.get("herramientas", {}).items():
            if not grupo_h.startswith("_"):
                for h in lista:
                    frases += h["dichos"]
        palabras = {p.lower() for f in frases for p in f.split()}
        palabras |= set(palabras_de_numeros())
        return sorted(palabras)

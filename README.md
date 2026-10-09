# Pipe-Logic

**Escribe lógica y matemáticas con los símbolos de verdad, con botones o al
dictado, y calcula con lo escrito.** Pensado para estudiar y, como sus
hermanas, para poder usarse sin manos.

- **Los símbolos que no están en el teclado**, a un toque: `¬ ∧ ∨ → ↔ ⊨ ∀ ∃
  ∈ ⊆ ∪ ∩ ℕ ℝ ∑ ∫ √ π`, índices y letras griegas. Escribe texto Unicode
  normal, que se copia y pega en cualquier sitio.
- **Al dictado**: «pe and no cu implica erre» se escribe `p ∧ ¬q → r`. El
  reconocimiento de voz va en tu ordenador, sin conexión.
- **Lógica**: ¿bien formada?, tabla de verdad, tautología/contradicción,
  equivalencia y consecuencia con contraejemplo, árbol sintáctico, formas
  normales.
- **Cálculo exacto**: `1 ÷ 3 = 1/3 (≈ 0,333333)`, `√2 · √2 = 2`.
  Combinatoria, divisibilidad, conjuntos. Lo que no se puede calcular dice
  «indeterminado» y por qué.
- **Álgebra**: ecuaciones y sistemas, simplificar, factorizar, derivar,
  integrar.
- **App para el móvil**, emparejada con tu ordenador por un código que el
  ordenador dice en voz alta.

> **Versión 0.2.2**. Para Linux y Windows (lo de Windows, aún sin probar a fondo).

## Descarga

En [Releases](https://github.com/pipataki/Pipe-Logic/releases): el paquete de
instalación (zip, con la app del móvil dentro), la app sola (apk) y el manual
en PDF en español e inglés. Más información en
[pipataki.net](https://pipataki.net/pipe-logic.html).

## Instalar

    unzip Pipe-Logic-0.2.2.zip
    cd Pipe-Logic-0.2.2
    ./install.sh

y luego `./pipelogic.sh --abrir`. En **Windows** (con Python 3.10 o más
nuevo): descomprime el zip, ejecuta `install.bat` y luego
`pipelogic.bat --abrir`. Para actualizar, lo mismo con la versión nueva:
tus ajustes se conservan. El manual explica el resto.

## Licencia

Software libre, © 2026 pipataki, **LGPLv3** (`LICENSE`, que se apoya en
`LICENSE.GPL-3.0`). Componentes de terceros en `AVISOS.md`.

---

## In English

**Pipe-Logic** is an editor for logic and mathematics with the real
symbols, by buttons or by voice (in Spanish), that also calculates: truth
tables, normal forms, exact arithmetic, equations, derivatives and
integrals. It runs on your Linux or Windows computer, offline, with an Android
companion app. Downloads in
[Releases](https://github.com/pipataki/Pipe-Logic/releases); manual in
English included. Free software, © 2026 pipataki, LGPLv3.

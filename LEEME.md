# Pipe-Logic

Editor de símbolos lógicos y matemáticos, en el navegador, con botones y
**voz**. Escribe en texto Unicode normal (se copia y pega en cualquier
sitio): `(p ∨ q) → r`, `∀x P(x)`, `x² + 2x + 1`, `∫[0, π] sen(x)`.

Además calcula: tablas de verdad, fórmulas bien formadas, formas normales,
aritmética exacta con fracciones, combinatoria, conjuntos, ecuaciones y
sistemas, derivadas e integrales.

Autor: pipataki · Licencia: LGPLv3 (ver `LICENSE`).

## Instalar (Linux)

    unzip Pipe-Logic-<versión>.zip
    cd Pipe-Logic-<versión>
    ./install.sh

El instalador pregunta dónde instalar (por defecto `~/Pipe-Logic`), crea su
entorno de Python, descarga el modelo de voz (54 MB) y la voz del PC
(63 MB), y pregunta el micrófono y la dirección para el móvil. Si falta algo
del sistema, te dice el `sudo apt install …` que hay que ejecutar.

**Actualizar** es lo mismo: descomprime la versión nueva y ejecuta su
`install.sh` apuntando a tu instalación. Tus ajustes no se tocan.

## Usar

    ./pipelogic.sh --abrir      arranca y lo abre en el navegador
    ./pipelogic.sh --parar      lo para
    ./pipelogic.sh --estado     ¿está en marcha?
    ./pipelogic.sh --codigo     dice el código de emparejamiento

Dictar: botón **Escuchar** o **F2**. Variables por el nombre de la letra
("pe", "cu"), "and", "or", "no", "implica", "sí y solo sí", "sub dos",
"super tres", números ("tres coma catorce"), y órdenes: "borra",
"deshacer", "vaciar", "espacio", "nueva línea". Para calcular: "calcula",
"tabla de verdad", "resuelve", "deriva", "integra"...

## Desde el móvil

1. Instala `Pipe-Logic.apk` (viene en este zip).
2. Ábrela y escribe la dirección que dio el instalador.
3. La primera vez enseña un **código**, y el PC dice el suyo en voz alta.
   Si coinciden, pulsa "Coincide": el móvil queda emparejado con ese PC.

## Sin aviso del navegador

El certificado lo firma una autoridad propia de tu instalación. Impórtala
una vez en el navegador como **autoridad** ("confiar para identificar
sitios web"): `certificado/ca.pem`.

## Desinstalar

    ./desinstalar.sh

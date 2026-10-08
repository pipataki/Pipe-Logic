# Avisos legales de Pipe-Logic

Pipe-Logic es **© 2026 pipataki**, software libre con licencia **LGPLv3**
(ver `LICENSE`). Parte de su código viene de VoiceController, del mismo
autor y con la misma licencia.

## Componentes de terceros

No van dentro del paquete: el instalador los descarga o los instala con pip
en tu equipo.

| Componente | Autor | Licencia | Para qué |
|---|---|---|---|
| Vosk | Alpha Cephei Inc. | Apache 2.0 | reconocimiento de voz, sin conexión |
| Modelo `vosk-model-small-es-0.42` | Alpha Cephei Inc. | Apache 2.0 | el español del reconocedor |
| sympy, mpmath | sus autores | BSD | álgebra: ecuaciones, derivadas, integrales |
| Flask, flask-sock, simple-websocket | Pallets y otros | BSD / MIT | el servidor de la página |
| cryptography | PyCA | Apache 2.0 / BSD | el certificado HTTPS |
| sounddevice | Matthias Geier | MIT | el micrófono del ordenador |
| piper-tts | Open Home Foundation | GPLv3 | la voz que dice el código de emparejamiento |
| Voz `es_ES-sharvard-medium` | entrenada sobre el corpus Sharvard (Universidad de Edimburgo) | CC BY 3.0 | esa voz |

La voz «sharvard» se usa con atribución: corpus Sharvard,
<https://datashare.ed.ac.uk/handle/10283/574>, licencia
<http://creativecommons.org/licenses/by/3.0/>.

## Privacidad

- La voz se reconoce **en tu ordenador**, y los cálculos se hacen ahí.
- Entre el móvil y el ordenador, la conexión va **cifrada** y solo con el
  ordenador con el que te emparejaste.
- Lo que escribes se guarda en el navegador de cada aparato.

// Pipe-Logic: los botones salen de /simbolos (simbolos.json). Nada de
// listas de simbolos aqui: la unica fuente es ese fichero.

const texto = document.getElementById("texto");
const aviso = document.getElementById("aviso");
const pestanas = document.getElementById("pestanas");
const botones = document.getElementById("botones");

const BORRADOR = "pipe-logic-borrador";
const PESTANA = "pipe-logic-pestana";

function leer(clave) {
  try { return localStorage.getItem(clave); } catch (e) { return null; }
}
function escribir(clave, valor) {
  try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacen */ }
}

function avisar(frase) {
  aviso.textContent = frase;
}

// Mete el texto donde esta el cursor (o sustituye lo seleccionado) y
// devuelve el foco al editor, para seguir escribiendo sin tocar el raton.
// Con execCommand entra en el historial del navegador: Control+Z y la
// orden "deshaz" lo quitan. Si el navegador no lo admite, setRangeText.
function insertar(s) {
  texto.focus();
  if (!document.execCommand("insertText", false, s)) {
    texto.setRangeText(s, texto.selectionStart, texto.selectionEnd, "end");
  }
  guardarBorrador();
}

// Lo dictado llega con espacios alrededor de los simbolos binarios
// (" ∧ "). Si delante del cursor ya hay un espacio o nada, el del
// principio sobra.
function insertarDictado(s) {
  const antes = texto.value.slice(0, texto.selectionStart);
  if (s.startsWith(" ") && (antes === "" || /\s$/.test(antes))) {
    s = s.slice(1);
  }
  if (s) insertar(s);
}

// "borra": el ultimo simbolo antes del cursor, saltando los espacios.
function borrarUno() {
  texto.focus();
  const quitar = () => document.execCommand("delete", false);
  while (/[ \t]$/.test(texto.value.slice(0, texto.selectionStart))) quitar();
  quitar();
  while (/[ \t]$/.test(texto.value.slice(0, texto.selectionStart))) quitar();
  guardarBorrador();
}

// Vaciar sin perder nada: seleccionar todo y borrar entra en el historial,
// asi que "deshacer" (o Control+Z) lo devuelve. Por eso la voz no pregunta.
function vaciar() {
  texto.focus();
  texto.select();
  if (!document.execCommand("delete", false)) texto.value = "";
  guardarBorrador();
}

// --- zoom y tema ----------------------------------------------------------
// El zoom es SOLO del cuadro de texto principal (las fórmulas), no del
// resto de la página. Los dos se recuerdan en el navegador (por aparato: el móvil y el PC, cada uno lo suyo).

const ZOOM = "pipe-logic-zoom";
const TEMA = "pipe-logic-tema";
const ZOOM_MIN = 0.6, ZOOM_MAX = 3, ZOOM_PASO = 1.2;
let zoom = parseFloat(leer(ZOOM)) || 1;

function ponerZoom(z) {
  zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  document.documentElement.style.setProperty("--zoom", zoom.toFixed(3));
  escribir(ZOOM, String(zoom));
  avisar("Zoom: " + Math.round(zoom * 100) + " %");
}

function ponerTema(tema) {
  document.documentElement.dataset.tema = tema;
  document.getElementById("tema").textContent = tema === "oscuro" ? "☀" : "☾";
  escribir(TEMA, tema);
}

function temaActual() {
  const elegido = document.documentElement.dataset.tema;
  if (elegido) return elegido;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro";
}

const ORDENES = {
  borra: borrarUno,
  vaciar,
  zoom_mas: () => ponerZoom(zoom * ZOOM_PASO),
  zoom_menos: () => ponerZoom(zoom / ZOOM_PASO),
  deshaz: () => { texto.focus(); document.execCommand("undo"); guardarBorrador(); },
  espacio: () => insertar(" "),
  nueva_linea: () => insertar("\n"),
};

function guardarBorrador() {
  escribir(BORRADOR, texto.value);
}

function pintarGrupo(grupo) {
  botones.innerHTML = "";
  for (const sim of grupo.simbolos) {
    const b = document.createElement("button");
    b.type = "button";
    b.title = sim.nombre;
    b.setAttribute("aria-label", sim.nombre);
    b.innerHTML = '<span class="s"></span><span class="n"></span>';
    b.querySelector(".s").textContent = sim.s;
    b.querySelector(".n").textContent = sim.nombre;
    // mousedown sin foco: el cursor del editor no se pierde al pulsar
    b.addEventListener("mousedown", (e) => e.preventDefault());
    b.addEventListener("click", () => insertar(sim.s));
    botones.appendChild(b);
  }
  for (const p of pestanas.children) {
    p.setAttribute("aria-selected", p.dataset.id === grupo.id ? "true" : "false");
  }
  escribir(PESTANA, grupo.id);
}

// --- herramientas ----------------------------------------------------------
//
// Actuan sobre lo seleccionado o, si no hay nada, sobre la linea del
// cursor. El servidor dice que va detras (en la misma linea) y que va
// debajo; aqui solo se coloca, y con execCommand para que se pueda deshacer.

function lineaDelCursor() {
  const v = texto.value;
  const desde = v.lastIndexOf("\n", texto.selectionStart - 1) + 1;
  let hasta = v.indexOf("\n", texto.selectionStart);
  if (hasta < 0) hasta = v.length;
  return [desde, hasta];
}

// Las lineas seguidas (sin una en blanco en medio) alrededor del cursor:
// un sistema de ecuaciones, una por linea.
function bloqueDelCursor() {
  const lineas = texto.value.split("\n");
  let pos = 0, n = 0;
  for (; n < lineas.length; n++) {
    if (pos + lineas[n].length >= texto.selectionStart) break;
    pos += lineas[n].length + 1;
  }
  let a = n, b = n;
  while (a > 0 && lineas[a - 1].trim()) a--;
  while (b < lineas.length - 1 && lineas[b + 1].trim()) b++;
  const desde = lineas.slice(0, a).reduce((s, l) => s + l.length + 1, 0);
  const hasta = desde + lineas.slice(a, b + 1).join("\n").length;
  return [desde, hasta];
}

function reemplazar(desde, hasta, nuevo) {
  texto.focus();
  texto.setSelectionRange(desde, hasta);
  if (!document.execCommand("insertText", false, nuevo)) {
    texto.setRangeText(nuevo, desde, hasta, "end");
  }
  guardarBorrador();
}

const DE_BLOQUE = new Set();   // herramientas con "bloque": true en simbolos.json

async function ejecutarHerramienta(id) {
  const a = texto.selectionStart, b = texto.selectionEnd;
  const conSeleccion = a !== b;
  let desde, hasta;
  if (conSeleccion) [desde, hasta] = [a, b];
  else if (DE_BLOQUE.has(id)) [desde, hasta] = bloqueDelCursor();
  else [desde, hasta] = lineaDelCursor();
  const trozo = texto.value.slice(desde, hasta);
  let r;
  try {
    const resp = await fetch("/herramienta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, texto: trozo }),
    });
    r = await resp.json();
  } catch (e) {
    avisar("No se pudo calcular: " + e.message);
    return;
  }
  if (r.error) { avisar(r.error); return; }
  if (r.aviso) { avisar(r.aviso); return; }
  let nuevo;
  if (conSeleccion) {
    // Lo seleccionado se queda tal cual; el resultado va detras, y lo de
    // debajo, tras el final de esa linea.
    nuevo = trozo + (r.en_linea ? " " + r.en_linea : "");
    reemplazar(desde, hasta, nuevo);
    if (r.debajo) {
      const v = texto.value;
      let fin = v.indexOf("\n", desde + nuevo.length);
      if (fin < 0) fin = v.length;
      reemplazar(fin, fin, "\n" + r.debajo);
    }
  } else {
    nuevo = r.expresion + (r.en_linea ? " " + r.en_linea : "") +
            (r.debajo ? "\n" + r.debajo : "");
    reemplazar(desde, hasta, nuevo);
  }
  avisar("Hecho. «Deshacer» o Control+Z lo quita.");
}

async function pintarHerramientas() {
  const caja = document.getElementById("herramientas");
  const grupos = await (await fetch("/herramientas")).json();
  const nombres = { logica: "Lógica:", algebra: "Álgebra:", calculo: "Cálculo:" };
  for (const [grupo, lista] of Object.entries(grupos)) {
    if (grupo.startsWith("_")) continue;
    const e = document.createElement("span");
    e.className = "grupo";
    e.textContent = nombres[grupo] || grupo;
    caja.appendChild(e);
    for (const h of lista) {
      if (h.bloque) DE_BLOQUE.add(h.id);
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = h.nombre;
      b.title = "Sobre lo seleccionado o la línea del cursor. Por voz: «" + h.dichos[0] + "»";
      b.addEventListener("mousedown", (ev) => ev.preventDefault());
      b.addEventListener("click", () => ejecutarHerramienta(h.id));
      caja.appendChild(b);
    }
  }
}

async function arrancar() {
  // Un enlace con #t=<texto> lo deja escrito (para pasar una fórmula).
  if (location.hash.startsWith("#t=")) {
    try {
      texto.value = decodeURIComponent(location.hash.slice(3));
      guardarBorrador();
    } catch (e) { /* enlace mal formado: se ignora */ }
  }
  pintarHerramientas();
  document.documentElement.style.setProperty("--zoom", zoom.toFixed(3));
  // En la app del móvil, oscuro de serie: el WebView no siempre dice que el
  // móvil está en modo oscuro. En el PC, el del sistema hasta elegir otro.
  const tema = leer(TEMA) || (window.plAudioNativo ? "oscuro" : null);
  if (tema) ponerTema(tema);
  else document.getElementById("tema").textContent = temaActual() === "oscuro" ? "☀" : "☾";
  if (!location.hash.startsWith("#t=")) texto.value = leer(BORRADOR) || "";
  const grupos = await (await fetch("/simbolos")).json();
  for (const g of grupos) {
    const p = document.createElement("button");
    p.type = "button";
    p.setAttribute("role", "tab");
    p.dataset.id = g.id;
    p.textContent = g.nombre;
    p.addEventListener("click", () => pintarGrupo(g));
    pestanas.appendChild(p);
  }
  const guardada = grupos.find((g) => g.id === leer(PESTANA));
  pintarGrupo(guardada || grupos[0]);
}

texto.addEventListener("input", guardarBorrador);

document.getElementById("copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(texto.value);
    avisar("Copiado.");
  } catch (e) {
    texto.select();
    avisar("No se pudo copiar solo: está seleccionado, pulsa Control+C.");
  }
});

document.getElementById("guardar").addEventListener("click", () => {
  const blob = new Blob([texto.value], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pipe-logic.txt";
  a.click();
  URL.revokeObjectURL(a.href);
  avisar("Guardado como pipe-logic.txt.");
});

document.getElementById("abrir").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  texto.value = await f.text();
  guardarBorrador();
  avisar("Abierto " + f.name + ".");
  e.target.value = "";
});

for (const [id, f] of [["zoom_mas", () => ORDENES.zoom_mas()], ["zoom_menos", () => ORDENES.zoom_menos()],
                       ["tema", () => ponerTema(temaActual() === "oscuro" ? "claro" : "oscuro")]]) {
  const b = document.getElementById(id);
  b.addEventListener("mousedown", (e) => e.preventDefault());
  b.addEventListener("click", f);
}

document.getElementById("borrar").addEventListener("click", () => {
  if (texto.value && !confirm("¿Vaciar el editor?")) return;
  vaciar();
});

// --- voz ----------------------------------------------------------------
//
// Por el WebSocket /voz. El servidor dice al conectar de donde sale el
// audio:
//   "servidor"  -> abre el micro por ALSA, como VoiceController; aqui solo
//                  se manda "escuchar" y "parar";
//   "navegador" -> el micro de esta pagina, como PCM de 16 kHz.

const botonEscuchar = document.getElementById("escuchar");
const oido = document.getElementById("oido");
const nivel = document.getElementById("nivel");
let voz = null;   // {ws, modo, contexto, flujo, nodo}

function pintarOido(clase, frase, fuera) {
  oido.innerHTML = "";
  const s = document.createElement("span");
  s.className = clase;
  s.textContent = frase;
  oido.appendChild(s);
  if (fuera && fuera.length) {
    const f = document.createElement("span");
    f.className = "fuera";
    f.textContent = "  (no entendido: " + fuera.join(", ") + ")";
    oido.appendChild(f);
  }
}

function pintarNivel(pico) {
  // Escala de raiz: la voz normal da picos de 0,05-0,3 y asi se ve.
  nivel.value = Math.min(1, Math.sqrt(pico));
}

async function aplicar(acciones) {
  // En orden: "pe or no pe tabla de verdad" escribe y luego calcula.
  for (const a of acciones) {
    if (a.tipo === "texto") insertarDictado(a.texto);
    else if (a.tipo === "herramienta") await ejecutarHerramienta(a.herramienta);
    else if (ORDENES[a.orden]) ORDENES[a.orden]();
  }
}

function marcarEscuchando(si) {
  botonEscuchar.setAttribute("aria-pressed", si ? "true" : "false");
  botonEscuchar.textContent = si ? "Parar" : "Escuchar";
  nivel.hidden = !si;
  if (!si) nivel.value = 0;
}

// Dentro de la app android: el micro lo graba Android (AudioNativo.java) y
// nos pasa trozos de 100 ms en base64. En algunos móviles (MediaTek) el
// WebView no abre nunca el micro, por eso existe este camino.
function microNativo(ws) {
  window.plAudio = {
    trozo(b64) {
      if (ws.readyState !== WebSocket.OPEN) return;
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      ws.send(bytes.buffer);
    },
    error(msg) {
      avisar(msg);
      pararDeEscuchar();
    },
  };
  window.plAudioNativo.empezar();
  voz.nativo = true;
}

async function microDelNavegador(ws) {
  if (window.plAudioNativo && window.plAudioNativo.disponible()) {
    microNativo(ws);
    return;
  }
  const flujo = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const contexto = new AudioContext();
  // Creado tras un await, el navegador puede dejarlo en pausa.
  await contexto.resume();
  await contexto.audioWorklet.addModule("/static/microfono.js");
  const fuente = contexto.createMediaStreamSource(flujo);
  const nodo = new AudioWorkletNode(contexto, "microfono");
  nodo.port.onmessage = (e) => {
    if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
  };
  fuente.connect(nodo);
  // Un nodo que no acaba en la salida puede no procesarse nunca. El
  // procesador no escribe nada en su salida: no se oye.
  nodo.connect(contexto.destination);
  Object.assign(voz, { contexto, flujo, nodo });
}

function empezarAEscuchar() {
  const ws = new WebSocket(`wss://${location.host}/voz`);
  ws.binaryType = "arraybuffer";
  voz = { ws, modo: null };
  marcarEscuchando(true);
  avisar("Conectando con la voz...");

  ws.onerror = () => avisar("No se pudo conectar con la voz del servidor.");
  ws.onclose = () => { if (voz && voz.ws === ws) pararDeEscuchar(false); };
  ws.onmessage = async (e) => {
    const d = JSON.parse(e.data);
    if (d.tipo === "modo") {
      voz.modo = d.micro;
      if (d.micro === "servidor") {
        ws.send("escuchar");
      } else {
        try {
          await microDelNavegador(ws);
          avisar("Escuchando por el micro del navegador. F2 o el botón para parar.");
        } catch (err) {
          avisar("No hay micro: " + err.message);
          pararDeEscuchar();
        }
      }
    } else if (d.tipo === "escuchando") {
      avisar("Escuchando por " + (d.nombre || "el micro del servidor") +
             ". F2 o el botón para parar.");
    } else if (d.tipo === "nivel") {
      pintarNivel(d.pico);
    } else if (d.tipo === "parcial") {
      pintarOido("parcial", d.texto);
    } else if (d.tipo === "final") {
      pintarOido("", d.texto, d.no_entendidas);
      aplicar(d.acciones);
    } else if (d.tipo === "error") {
      avisar(d.texto);
      pararDeEscuchar();
    }
  };
  texto.focus();
}

function pararDeEscuchar(avisarAlServidor = true) {
  if (!voz) return;
  const { ws, modo, contexto, flujo, nodo, nativo } = voz;
  voz = null;
  if (nativo && window.plAudioNativo) window.plAudioNativo.parar();
  if (nodo) nodo.port.onmessage = null;
  if (flujo) flujo.getTracks().forEach((t) => t.stop());
  if (contexto) contexto.close();
  if (avisarAlServidor && ws.readyState === WebSocket.OPEN) {
    if (modo === "navegador") {
      // Medio segundo de silencio antes de "fin": sin el, Vosk se come la
      // ultima palabra (medido con audio sintetico el 6-oct-2026).
      for (let i = 0; i < 5; i++) ws.send(new Int16Array(1600).buffer);
      ws.send("fin");
    } else {
      ws.send("parar");
    }
    // Se deja abierta un momento: aun puede llegar la ultima frase.
    const cerrar = () => ws.close();
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.tipo === "final") { pintarOido("", d.texto, d.no_entendidas); aplicar(d.acciones); }
      if (d.tipo === "parado") cerrar();
    };
    setTimeout(cerrar, 2000);
  }
  marcarEscuchando(false);
  avisar("Micro apagado.");
}

function alternarEscucha() {
  if (voz) pararDeEscuchar(); else empezarAEscuchar();
}

botonEscuchar.addEventListener("click", alternarEscucha);
document.addEventListener("keydown", (e) => {
  if (e.key === "F2") { e.preventDefault(); alternarEscucha(); }
});

arrancar();

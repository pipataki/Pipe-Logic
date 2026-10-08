// AudioWorklet: del micro (a 44,1 o 48 kHz, en coma flotante) a PCM de
// 16 bits a 16 kHz, que es lo que espera Vosk. Manda trozos de 100 ms.

const DESTINO = 16000;
const TROZO = 1600;

class Microfono extends AudioWorkletProcessor {
  constructor() {
    super();
    this.paso = sampleRate / DESTINO;   // sampleRate: global del worklet
    this.pos = 0;
    this.salida = new Int16Array(TROZO);
    this.n = 0;
  }

  process(entradas) {
    const canal = entradas[0] && entradas[0][0];
    if (!canal) return true;
    // Diezmado con interpolacion lineal; para voz a 16 kHz basta.
    while (this.pos < canal.length - 1) {
      const i = Math.floor(this.pos);
      const f = this.pos - i;
      const v = canal[i] * (1 - f) + canal[i + 1] * f;
      this.salida[this.n++] = Math.max(-1, Math.min(1, v)) * 0x7fff;
      if (this.n === TROZO) {
        this.port.postMessage(this.salida.buffer.slice(0));
        this.n = 0;
      }
      this.pos += this.paso;
    }
    this.pos -= canal.length;
    return true;
  }
}

registerProcessor("microfono", Microfono);

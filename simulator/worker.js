// Ein Board = ein Web Worker mit echtem MicroPython (WebAssembly).
// Blockierende Schleifen in main.py sind hier kein Problem.
import { IO, ADC_INDEX, BUTTON_PINS, SSD1306Emu, Inbox } from "./simcore.js";

let io, ram, emu, inboxes, macs, myIndex, mod, sleepArr, allIo;
let i2cBuf = [], i2cFreq = 400000, lastRssi = -50;

function out(text) { postMessage({ t: "out", s: text }); }
function err(text) { postMessage({ t: "err", s: text }); }

function sleepMs(ms) {
  if (ms > 0) Atomics.wait(sleepArr, 0, 0, ms);
}

function readBytes(ptr, len) {
  const a = new Uint8Array(len);
  for (let i = 0; i < len; i++) a[i] = mod.getValue(ptr + i, "i8") & 255;
  return a;
}
function writeBytes(ptr, bytes) {
  for (let i = 0; i < bytes.length; i++) mod.setValue(ptr + i, bytes[i], "i8");
}
function macEq(a, b) { for (let i = 0; i < 6; i++) if (a[i] !== b[i]) return false; return true; }

// Diese Funktionen ruft der Python-Code als Modul "simhw" auf.
const hw = {
  sleep: (ms) => sleepMs(ms),
  pin_get: (n) => {
    if (BUTTON_PINS.includes(n)) return (Atomics.load(io, IO.BUTTONS) >> n) & 1;
    const w = n < 32 ? Atomics.load(io, IO.OUT_LO) : Atomics.load(io, IO.OUT_HI);
    return (w >>> (n & 31)) & 1;
  },
  pin_set: (n, v) => {
    const idx = n < 32 ? IO.OUT_LO : IO.OUT_HI;
    const bit = 1 << (n & 31);
    if (v) Atomics.or(io, idx, bit); else Atomics.and(io, idx, ~bit);
  },
  adc: (n) => {
    const idx = ADC_INDEX[n];
    if (idx === undefined) return 0;
    // etwas Rauschen wie beim echten ADC
    const v = Atomics.load(io, idx) + Math.round((Math.random() - 0.5) * 300);
    return Math.max(0, Math.min(65535, v));
  },
  pwm: (pin, freq, duty) => {
    Atomics.store(io, IO.PWM_FREQ + pin, freq | 0);
    Atomics.store(io, IO.PWM_DUTY + pin, duty | 0);
  },
  i2c_start: (freq) => { i2cBuf = []; i2cFreq = freq || 400000; },
  i2c_data: (ptr, len) => { const b = readBytes(ptr, len); for (const x of b) i2cBuf.push(x); },
  i2c_end: () => {
    const bytes = Uint8Array.from(i2cBuf);
    emu.transfer(bytes);
    Atomics.add(io, IO.I2C_BYTES, bytes.length);
    if (Atomics.load(io, IO.REAL_TIMING)) {
      // 9 Takte pro Byte + Start/Adresse/Stop
      sleepMs(((bytes.length + 2) * 9) / i2cFreq * 1000);
    }
  },
  mac: (i) => macs[myIndex][i],
  reset: () => { postMessage({ t: "reset" }); sleepMs(100000); },
  en_active: (a) => Atomics.store(io, IO.ESPNOW_ON, a ? 1 : 0),
  en_send: (macPtr, msgPtr, len) => {
    const dst = readBytes(macPtr, 6);
    const data = readBytes(msgPtr, len);
    const bc = dst.every((x) => x === 255);
    let ok = false;
    for (let j = 0; j < inboxes.length; j++) {
      if (j === myIndex || !inboxes[j]) continue;
      // nur Boards, auf denen gerade ein Programm mit aktivem ESP-NOW laeuft
      if (!Atomics.load(allIo[j], IO.RUNNING) || !Atomics.load(allIo[j], IO.ESPNOW_ON)) continue;
      if (bc || macEq(dst, macs[j])) {
        if (inboxes[j].push(macs[myIndex], data)) ok = true;
      }
    }
    return ok || bc ? 1 : 0;
  },
  en_any: () => inboxes[myIndex].count(),
  en_recv: (macPtr, bufPtr, timeout) => {
    const start = performance.now();
    for (;;) {
      const p = inboxes[myIndex].pop();
      if (p) {
        writeBytes(macPtr, p.mac);
        writeBytes(bufPtr, p.data);
        lastRssi = -42 - Math.round(Math.random() * 8);
        return p.data.length;
      }
      if (timeout === 0 || (timeout > 0 && performance.now() - start >= timeout)) return -1;
      sleepMs(1);
    }
  },
  en_rssi: () => lastRssi,
};

onmessage = async (e) => {
  const m = e.data;
  if (m.cmd !== "start") return;
  io = new Int32Array(m.ioBuf);
  ram = new Uint8Array(m.ramBuf);
  sleepArr = new Int32Array(m.sleepBuf);
  emu = new SSD1306Emu(ram, io);
  inboxes = m.inboxBufs.map((b) => (b ? new Inbox(b) : null));
  macs = m.macs;
  allIo = m.allIo.map((b) => new Int32Array(b));
  myIndex = m.index;
  try {
    const { loadMicroPython } = await import(m.mpBase + "micropython.mjs");
    const mp = await loadMicroPython({
      url: m.mpBase + "micropython.wasm",
      heapsize: 4 * 1024 * 1024,
      stdout: out,
      stderr: err,
    });
    mod = mp._module;
    mp.registerJsModule("simhw", hw);
    for (const [name, text] of Object.entries(m.files)) mp.FS.writeFile("/" + name, text);
    Atomics.store(io, IO.RUNNING, 1);
    postMessage({ t: "running" });
    mp.runPython("import _boot");
  } catch (ex) {
    err(String(ex && ex.message ? ex.message : ex));
  }
  Atomics.store(io, IO.RUNNING, 0);
  postMessage({ t: "end" });
};

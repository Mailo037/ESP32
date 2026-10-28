// espBoard-Simulator: Hauptseite.
// Baut die Boards, liest Maus/Tastatur, zeigt OLED/LEDs und laedt die
// Programme aus GitHub. Jedes Board laeuft in einem eigenen Worker (worker.js).
import { IO, IO_LEN, INBOX_BYTES, Inbox } from "./simcore.js";

const MAX_BOARDS = 2;
const LED_PINS = [13, 12, 14, 27, 26, 25, 33, 32];          // P7 (links) ... P0 (rechts)
const LED_FARBEN = ["rot", "gelb", "rot", "gelb", "rot", "gelb", "rot", "gelb"];
const RGB_PINS = [19, 23, 18];
const BUZZER = 15;
const $ = (s, el = document) => el.querySelector(s);

// ------------------------------------------------------------------
//  Bauteile (Arbeitsblatt "Kennenlernen des espBoards")
// ------------------------------------------------------------------
const BAUTEILE = [
  { nr: 1, sel: ".esp", name: "ESP32-DevKit", info: "Mikrocontroller, 240 MHz, WLAN + Bluetooth, 3,3 V", pos: [25, 29] },
  { nr: 2, sel: ".leds", name: "8 LEDs P7…P0", info: "GPIO 13, 12, 14, 27, 26, 25, 33, 32 · RN220 = 8 × 220 Ω", pos: [24, 13] },
  { nr: 3, sel: ".kreuz", name: "Taster S17, S4, S5, S16", info: "GPIO 17, 4, 5, 16 · active-high mit 10 kΩ Pull-down", pos: [24, 75] },
  { nr: 4, sel: ".potis", name: "Potis RP3 und RP0", info: "GPIO 39 (ADC1 Kanal 3) und GPIO 36 (Kanal 0)", pos: [65, 14] },
  { nr: 5, sel: ".joystick", name: "Joystick RJ6/RJ7 + Taster S2", info: "X = GPIO 34, Y = GPIO 35, Taster = GPIO 2", pos: [85, 73] },
  { nr: 6, sel: ".rgb", name: "RGB-LED P8", info: "rot GPIO 19, grün GPIO 23, blau GPIO 18 (PWM)", pos: [65, 71] },
  { nr: 7, sel: ".oled-modul", name: "OLED SSD1306 128 × 64", info: "I²C: SDA 21, SCL 22, Adresse 0x3C", pos: [79, 47] },
  { nr: 8, sel: ".bmp", name: "BMP280 (Sockel)", info: "Temperatur/Luftdruck an I²C, 0x76 – hier leer", pos: [79, 23] },
];

// ------------------------------------------------------------------
//  Gemeinsamer Speicher fuer alle Boards (vorab angelegt, damit sich
//  die Boards per ESP-NOW finden, egal wann sie starten)
// ------------------------------------------------------------------
if (!self.crossOriginIsolated) {
  const h = $("#hinweis");
  h.hidden = false;
  h.textContent = location.protocol === "file:"
    ? "Bitte die Seite über GitHub Pages oder einen lokalen Webserver öffnen (z. B. „python -m http.server“ im Repo-Ordner) – direkt als Datei geht es nicht."
    : "Der Browser gibt den gemeinsamen Speicher (SharedArrayBuffer) noch nicht frei. Bitte die Seite einmal neu laden. Hilft das nicht: aktuellen Chrome, Edge oder Firefox verwenden.";
}

function zufallsMac(i) {
  let m;
  try { m = JSON.parse(localStorage.getItem("espboard-mac-" + i) || "null"); } catch { m = null; }
  if (!Array.isArray(m) || m.length !== 6) {
    m = [0x24, 0x6f, 0x28, 0xb0 + i, (Math.random() * 256) | 0, (Math.random() * 256) | 0];
    try { localStorage.setItem("espboard-mac-" + i, JSON.stringify(m)); } catch { /* egal */ }
  }
  return m;
}

const speicher = [];
for (let i = 0; i < MAX_BOARDS; i++) {
  const sab = (n) => (self.SharedArrayBuffer ? new SharedArrayBuffer(n) : new ArrayBuffer(n));
  speicher.push({ io: sab(IO_LEN * 4), ram: sab(1024), sleep: sab(4), inbox: sab(INBOX_BYTES), mac: zufallsMac(i) });
}

// ------------------------------------------------------------------
//  Ton (Piezo an GPIO 15)
// ------------------------------------------------------------------
let audio = null;
function tonAn() {
  if (audio) return;
  try { audio = new AudioContext(); } catch { audio = null; }
}

// ------------------------------------------------------------------
//  Programme aus GitHub
// ------------------------------------------------------------------
const quelle = { repo: "", branch: "", baum: [], ordner: [] };
const dateiCache = new Map();

async function ladeProgrammliste() {
  const status = $("#status");
  status.classList.remove("fehler");
  quelle.repo = $("#repo").value.trim();
  let branch = $("#branch").value.trim() || "main";
  status.textContent = "Lade Programmliste aus " + quelle.repo + " …";
  try {
    let r = await fetch(`https://api.github.com/repos/${quelle.repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
    let ersatz = "";
    if (r.status === 404 || r.status === 422) {
      const info = await fetch(`https://api.github.com/repos/${quelle.repo}`);
      if (!info.ok) throw new Error(info.status === 404 ? "Repo nicht gefunden" : "GitHub antwortet mit " + info.status);
      const def = (await info.json()).default_branch;
      if (def && def !== branch) {
        ersatz = branch;
        branch = def;
        r = await fetch(`https://api.github.com/repos/${quelle.repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
      }
    }
    if (r.status === 403) throw new Error("GitHub-Limit erreicht (60 Abrufe pro Stunde). Bitte später neu laden.");
    if (!r.ok) throw new Error("GitHub antwortet mit " + r.status);
    const daten = await r.json();
    quelle.branch = branch;
    quelle.baum = daten.tree.filter((e) => e.type === "blob");
    quelle.ordner = quelle.baum
      .map((e) => e.path.split("/"))
      .filter((p) => p.length === 2 && p[1] === "main.py" && p[0] !== "simulator")
      .map((p) => p[0])
      .sort();
    status.textContent = `${quelle.ordner.length} Programme aus ${quelle.repo} @ ${branch}` +
      (ersatz ? ` (Branch „${ersatz}“ gibt es noch nicht – Standard-Branch geladen)` : "");
    for (const b of boards) b.programmeEintragen();
  } catch (e) {
    status.textContent = "Fehler: " + e.message;
    status.classList.add("fehler");
  }
}

async function ladeDatei(eintrag) {
  const key = eintrag.path + "@" + eintrag.sha;
  if (dateiCache.has(key)) return dateiCache.get(key);
  const url = `https://raw.githubusercontent.com/${quelle.repo}/${encodeURIComponent(quelle.branch)}/${eintrag.path.split("/").map(encodeURIComponent).join("/")}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(eintrag.path + ": " + r.status);
  const text = await r.text();
  dateiCache.set(key, text);
  return text;
}

async function programmDateien(ordner) {
  const dateien = {};
  const liste = quelle.baum.filter((e) => e.path.startsWith(ordner + "/") && e.path.split("/").length === 2
    && /\.(py|txt|json|csv)$/i.test(e.path) && (e.size || 0) < 200000);
  await Promise.all(liste.map(async (e) => { dateien[e.path.split("/")[1]] = await ladeDatei(e); }));
  return dateien;
}

let simDateien = null;
async function simulatorDateien() {
  if (simDateien) return simDateien;
  const namen = ["_boot.py", "_sim_machine.py", "_sim_time.py", "_sim_network.py", "_sim_espnow.py"];
  simDateien = {};
  await Promise.all(namen.map(async (n) => {
    const r = await fetch(new URL("py/" + n, import.meta.url));
    if (!r.ok) throw new Error("Simulator-Datei fehlt: " + n);
    simDateien[n] = await r.text();
  }));
  return simDateien;
}

// ------------------------------------------------------------------
//  Ein Board
// ------------------------------------------------------------------
const boards = [];
let aktiv = null;

function boardHTML() {
  const leds = LED_FARBEN.map((f, i) => `<div class="led" data-i="${i}" style="--c: var(--led-${f})"></div>`).join("");
  return `
  <div class="schraube" style="left:2%;top:2%"></div><div class="schraube" style="left:94.5%;top:2%"></div>
  <div class="schraube" style="left:2%;top:94%"></div><div class="schraube" style="left:94.5%;top:94%"></div>
  <div class="rn"></div><span class="silk" style="left:21%;top:3.6%">RN220</span>
  <span class="silk" style="left:7.5%;top:3.6%">P7</span><span class="silk" style="left:38.5%;top:3.6%">P0</span>
  <span class="silk" style="left:2%;top:9.5%">X51</span>
  <div class="leds">${leds}</div>
  <span class="silk" style="left:13%;top:11.6%">MP26</span>
  <div class="potis">
    <div class="poti" data-poti="39" style="left:51%;top:.6%"><div class="knopf"></div></div>
    <div class="poti" data-poti="36" style="left:68%;top:.6%"><div class="knopf"></div></div>
  </div>
  <span class="silk" style="left:45.5%;top:3.6%">RP3</span><span class="silk" style="left:86%;top:4%">RP0</span>
  <span class="silk" style="left:51.5%;top:13.2%">MP3 MP0</span>
  <div class="bmp"></div><span class="silk" style="left:73.5%;top:14.5%">BMP280</span>
  <div class="esp"><div class="reihe" style="top:3%"></div><div class="reihe" style="bottom:3%"></div>
    <div class="usb"></div><div class="pwr"></div><div class="modul">ESP-32D</div></div>
  <span class="silk" style="left:56.5%;top:29%">MP6</span><span class="silk" style="left:56.5%;top:38%">MP7</span>
  <div class="oled-modul"><div class="pins">GND VCC SCL SDA</div><div class="glas"><canvas width="128" height="64"></canvas></div></div>
  <span class="silk" style="left:1.5%;top:56%">XJ15</span><span class="silk" style="left:3%;top:61%">T3</span>
  <span class="silk" style="left:9%;top:61.5%">MP4</span>
  <span class="silk" style="left:35.5%;top:58.5%">R19</span><span class="silk" style="left:33.5%;top:64%">R18</span>
  <span class="silk" style="left:43.5%;top:64%">R23</span>
  <span class="silk" style="left:52%;top:55.5%">MCL</span><span class="silk" style="left:52%;top:60%">MDA</span>
  <div class="kreuz">
    <div class="taster" data-pin="17" style="left:15%;top:60.5%"></div>
    <div class="taster" data-pin="4" style="left:1.8%;top:71%"></div>
    <div class="taster" data-pin="5" style="left:27%;top:71%"></div>
    <div class="taster" data-pin="16" style="left:14.5%;top:81.5%"></div>
  </div>
  <span class="silk" style="left:15.5%;top:68.6%">S17</span><span class="silk" style="left:3.4%;top:79%">S4</span>
  <span class="silk" style="left:28.6%;top:79%">S5</span><span class="silk" style="left:15%;top:89.5%">S16</span>
  <div class="rgb"><div class="licht"></div></div><span class="silk" style="left:60%;top:78.5%">P8</span>
  <div class="joystick"><div class="orange-a"></div><div class="orange-b"></div><div class="mulde"></div><div class="stick"></div></div>
  <span class="silk" style="left:90%;top:57.8%">RJ6</span><span class="silk" style="left:63.5%;top:68%">RJ7</span>
  <span class="silk" style="left:90%;top:86%">S2</span>
  <span class="silk" style="left:38%;top:85%;font-size:3.6cqw">BZTG Oldenburg</span>
  <span class="silk" style="left:42%;top:90.5%;font-size:3.6cqw">espBoard / August 26</span>
  <span class="silk" style="left:84%;top:93%">GND</span>
  ${BAUTEILE.map((b) => `<div class="nummer" style="left:${b.pos[0]}%;top:${b.pos[1]}%">${b.nr}</div>`).join("")}`;
}

class Board {
  constructor(i) {
    this.i = i;
    this.sp = speicher[i];
    this.io = new Int32Array(this.sp.io);
    this.ram = new Uint8Array(this.sp.ram);
    this.worker = null;
    this.letzterFrame = -1;
    this.letzteFlags = -1;
    this.tasten = 0;              // gehaltene Taster (Maus/Finger)
    this.tastatur = 0;            // gehaltene Taster (Tastatur)
    this.joyMaus = null;          // {x, y} solange gezogen wird
    this.joyTasten = { x: 0, y: 0 };
    this.poti = { 39: 0.6, 36: 0.4 };
    this.osc = null; this.gain = null;
    this.bauen();
    this.eingabenSchreiben();
  }

  bauen() {
    const karte = document.createElement("section");
    karte.className = "board-karte";
    karte.innerHTML = `
      <div class="board-leiste">
        <span class="name">Board ${this.i + 1}</span>
        <label class="sr" for="prog-${this.i}" hidden>Programm</label>
        <select id="prog-${this.i}" aria-label="Programm für Board ${this.i + 1}"><option>…</option></select>
        <button type="button" class="haupt" data-aktion="start">Start</button>
        <button type="button" data-aktion="stopp">Stopp</button>
      </div>
      <div class="board">${boardHTML()}</div>
      <div class="konsole" aria-live="polite"></div>`;
    $("#boards").appendChild(karte);
    this.karte = karte;
    this.boardEl = $(".board", karte);
    this.canvas = $("canvas", karte);
    this.ctx = this.canvas.getContext("2d");
    this.bild = this.ctx.createImageData(128, 64);
    this.ledEls = [...karte.querySelectorAll(".led")];
    this.rgbEl = $(".rgb .licht", karte);
    this.konsole = $(".konsole", karte);
    this.select = $("select", karte);
    this.stick = $(".stick", karte);
    this.joyEl = $(".joystick", karte);

    karte.addEventListener("pointerdown", () => setAktiv(this), true);
    $('[data-aktion="start"]', karte).addEventListener("click", () => this.start());
    $('[data-aktion="stopp"]', karte).addEventListener("click", () => this.stopp("Gestoppt."));
    this.select.addEventListener("change", () => this.start());

    // Taster
    for (const t of karte.querySelectorAll(".taster")) {
      const pin = +t.dataset.pin;
      const los = () => { this.tasten &= ~(1 << pin); this.eingabenSchreiben(); };
      t.addEventListener("pointerdown", (e) => { e.preventDefault(); t.setPointerCapture(e.pointerId); this.tasten |= 1 << pin; this.eingabenSchreiben(); tonAn(); });
      t.addEventListener("pointerup", los);
      t.addEventListener("pointercancel", los);
    }

    // Joystick: ziehen = Auslenkung, kurz antippen = Taster S2
    let start = null;
    this.joyEl.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      this.joyEl.setPointerCapture(e.pointerId);
      start = { x: e.clientX, y: e.clientY, t: performance.now(), bewegt: false };
      tonAn();
    });
    this.joyEl.addEventListener("pointermove", (e) => {
      if (!start) return;
      const r = this.joyEl.getBoundingClientRect();
      const rad = r.width * 0.33;
      let x = (e.clientX - (r.left + r.width / 2)) / rad;
      let y = -(e.clientY - (r.top + r.height / 2)) / rad;
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 6) start.bewegt = true;
      if (!start.bewegt) return;
      const l = Math.hypot(x, y);
      if (l > 1) { x /= l; y /= l; }
      this.joyMaus = { x, y };
      this.eingabenSchreiben();
    });
    const joyLos = () => {
      if (start && !start.bewegt) {          // antippen -> S2
        this.tasten |= 1 << 2; this.eingabenSchreiben();
        setTimeout(() => { this.tasten &= ~(1 << 2); this.eingabenSchreiben(); }, 160);
      }
      start = null;
      this.joyMaus = null;
      this.eingabenSchreiben();
    };
    this.joyEl.addEventListener("pointerup", joyLos);
    this.joyEl.addEventListener("pointercancel", joyLos);

    // Potis: hoch/runter ziehen oder Mausrad
    for (const p of karte.querySelectorAll(".poti")) {
      const pin = +p.dataset.poti;
      let y0 = null, w0 = 0;
      p.addEventListener("pointerdown", (e) => { e.preventDefault(); p.setPointerCapture(e.pointerId); y0 = e.clientY; w0 = this.poti[pin]; });
      p.addEventListener("pointermove", (e) => { if (y0 === null) return; this.potiSetzen(pin, w0 + (y0 - e.clientY) / 160); });
      p.addEventListener("pointerup", () => { y0 = null; });
      p.addEventListener("wheel", (e) => { e.preventDefault(); this.potiSetzen(pin, this.poti[pin] - Math.sign(e.deltaY) * 0.05); }, { passive: false });
    }
    this.potiSetzen(39, this.poti[39]);
    this.potiSetzen(36, this.poti[36]);
  }

  potiSetzen(pin, w) {
    this.poti[pin] = Math.max(0, Math.min(1, w));
    const el = $(`.poti[data-poti="${pin}"] .knopf`, this.karte);
    el.style.transform = `rotate(${-135 + this.poti[pin] * 270}deg)`;
    this.eingabenSchreiben();
  }

  joystick() {
    return this.joyMaus || this.joyTasten;
  }

  eingabenSchreiben() {
    const knoepfe = this.tasten | this.tastatur;
    Atomics.store(this.io, IO.BUTTONS, knoepfe);
    const j = this.joystick();
    Atomics.store(this.io, IO.ADC34, Math.round(32768 + j.x * 32767));
    Atomics.store(this.io, IO.ADC35, Math.round(32768 + j.y * 32767));
    Atomics.store(this.io, IO.ADC36, Math.round(this.poti[36] * 65535));
    Atomics.store(this.io, IO.ADC39, Math.round(this.poti[39] * 65535));
    for (const t of this.karte.querySelectorAll(".taster")) t.classList.toggle("gedrueckt", !!(knoepfe & (1 << +t.dataset.pin)));
    this.joyEl.classList.toggle("gedrueckt", !!(knoepfe & 4));
    this.stick.style.transform = `translate(${j.x * 70}%, ${-j.y * 70}%)`;
    if (this === aktiv) messprotokoll();
  }

  programmeEintragen() {
    const alt = this.select.value;
    this.select.innerHTML = quelle.ordner.map((o) => `<option>${o}</option>`).join("");
    const wunsch = alt && quelle.ordner.includes(alt) ? alt
      : (this.i === 0 ? ["Geometry-Dash", "ESP-Pong"] : ["ESP-Pong"]).find((o) => quelle.ordner.includes(o)) || quelle.ordner[0];
    if (wunsch) this.select.value = wunsch;
  }

  log(text, art = "") {
    const z = document.createElement("div");
    if (art) z.className = art;
    z.textContent = text;
    this.konsole.appendChild(z);
    while (this.konsole.childElementCount > 300) this.konsole.firstChild.remove();
    this.konsole.scrollTop = this.konsole.scrollHeight;
  }

  zuruecksetzen() {
    this.io.fill(0);
    this.ram.fill(0);
    new Inbox(this.sp.inbox).reset();
    this.letzterFrame = -1;
    this.letzteFlags = -1;
    Atomics.store(this.io, IO.REAL_TIMING, $("#opt-timing").checked ? 1 : 0);
    this.eingabenSchreiben();
  }

  stopp(meldung) {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      if (meldung) this.log(meldung, "s");
    }
    Atomics.store(this.io, IO.RUNNING, 0);
    Atomics.store(this.io, IO.ESPNOW_ON, 0);
    // Pins gehen beim Stopp aus (wie beim Reset)
    Atomics.store(this.io, IO.OUT_LO, 0);
    Atomics.store(this.io, IO.OUT_HI, 0);
    for (let p = 0; p < 40; p++) { this.io[IO.PWM_FREQ + p] = 0; this.io[IO.PWM_DUTY + p] = 0; }
  }

  async start() {
    const ordner = this.select.value;
    if (!ordner || !quelle.ordner.includes(ordner)) return;
    if (!self.crossOriginIsolated) { this.log("SharedArrayBuffer ist nicht verfügbar – siehe Hinweis oben.", "e"); return; }
    this.stopp();
    this.zuruecksetzen();
    this.konsole.textContent = "";
    this.log(`Lade ${ordner} aus ${quelle.repo} @ ${quelle.branch} …`, "s");
    let dateien;
    try {
      dateien = { ...(await simulatorDateien()), ...(await programmDateien(ordner)) };
    } catch (e) {
      this.log("Fehler beim Laden: " + e.message, "e");
      return;
    }
    this.log("Dateien: " + Object.keys(dateien).filter((n) => !n.startsWith("_")).join(", "), "s");
    const w = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
    this.worker = w;
    w.onmessage = (e) => {
      const m = e.data;
      if (m.t === "out") this.log(m.s);
      else if (m.t === "err") this.log(m.s, "e");
      else if (m.t === "running") this.log("MicroPython läuft – main.py gestartet.", "s");
      else if (m.t === "reset") { this.log("machine.reset()", "s"); this.start(); }
      else if (m.t === "end") { if (this.worker === w) { this.worker = null; } }
    };
    w.onerror = (e) => this.log("Worker-Fehler: " + (e.message || e), "e");
    w.postMessage({
      cmd: "start",
      index: this.i,
      files: dateien,
      ioBuf: this.sp.io, ramBuf: this.sp.ram, sleepBuf: this.sp.sleep,
      inboxBufs: speicher.map((s) => s.inbox),
      allIo: speicher.map((s) => s.io),
      macs: speicher.map((s) => s.mac),
      mpBase: new URL("mp/", import.meta.url).href,
    });
  }

  // Wird bei jedem Bild der Seite aufgerufen
  zeichnen() {
    const io = this.io;
    const frame = Atomics.load(io, IO.FRAME);
    const flags = Atomics.load(io, IO.DISP);
    if (frame !== this.letzterFrame || flags !== this.letzteFlags) {
      this.letzterFrame = frame;
      this.letzteFlags = flags;
      const an = flags & 1, inv = (flags >> 1) & 1;
      const hell = 0.55 + 0.45 * (((flags >> 8) & 255) / 255);
      const d = this.bild.data;
      for (let y = 0; y < 64; y++) {
        const zeile = (y >> 3) * 128, bit = 1 << (y & 7);
        for (let x = 0; x < 128; x++) {
          let p = (this.ram[zeile + x] & bit) ? 1 : 0;
          if (inv) p ^= 1;
          const o = (y * 128 + x) * 4;
          if (an && p) { d[o] = 111 * hell; d[o + 1] = 227 * hell; d[o + 2] = 255 * hell; }
          else { d[o] = 4; d[o + 1] = 8; d[o + 2] = 12; }
          d[o + 3] = 255;
        }
      }
      this.ctx.putImageData(this.bild, 0, 0);
    }
    const lo = Atomics.load(io, IO.OUT_LO), hi = Atomics.load(io, IO.OUT_HI);
    const pegel = (p) => (p < 32 ? (lo >>> p) & 1 : (hi >>> (p - 32)) & 1);
    const pwmAn = (p) => io[IO.PWM_FREQ + p] > 0 && io[IO.PWM_DUTY + p] > 0;
    LED_PINS.forEach((p, k) => this.ledEls[k].classList.toggle("an", !!(pegel(p) || pwmAn(p))));
    const kanal = (p) => (io[IO.PWM_FREQ + p] > 0 ? io[IO.PWM_DUTY + p] / 65535 : pegel(p));
    const [r, g, b] = RGB_PINS.map(kanal);
    const staerke = Math.max(r, g, b);
    this.rgbEl.style.opacity = staerke > 0.01 ? String(Math.min(1, 0.35 + staerke)) : "0";
    if (staerke > 0.01) {
      const f = (v) => Math.round(255 * Math.min(1, v / staerke));
      this.rgbEl.style.background = `radial-gradient(circle, rgb(${f(r)},${f(g)},${f(b)}) 0%, rgba(${f(r)},${f(g)},${f(b)},.55) 35%, transparent 70%)`;
    }
    this.summer();
  }

  summer() {
    if (!audio) return;
    const hoerbar = $("#opt-ton").checked && this.worker;
    const f = this.io[IO.PWM_FREQ + BUZZER], d = this.io[IO.PWM_DUTY + BUZZER];
    if (!this.osc) {
      this.osc = audio.createOscillator();
      this.osc.type = "square";
      this.gain = audio.createGain();
      this.gain.gain.value = 0;
      this.osc.connect(this.gain).connect(audio.destination);
      this.osc.start();
    }
    // Piezo ist bei 50 % Tastverhaeltnis am lautesten
    const laut = hoerbar && f > 20 && d > 0 ? 0.12 * Math.min(d, 65535 - d) / 32768 : 0;
    if (f > 20) this.osc.frequency.setTargetAtTime(Math.min(f, 12000), audio.currentTime, 0.002);
    this.gain.gain.setTargetAtTime(laut, audio.currentTime, 0.004);
  }
}

// ------------------------------------------------------------------
//  Aktives Board, Tastatur, Messprotokoll
// ------------------------------------------------------------------
function setAktiv(b) {
  if (aktiv === b) return;
  aktiv = b;
  for (const x of boards) x.karte.classList.toggle("aktiv", x === b);
  messprotokoll();
}

const TASTEN = { KeyW: 17, KeyA: 4, KeyD: 5, KeyS: 16, Space: 2 };
const gehalten = new Set();
function tastaturAuswerten() {
  if (!aktiv) return;
  let bits = 0;
  for (const [code, pin] of Object.entries(TASTEN)) if (gehalten.has(code)) bits |= 1 << pin;
  aktiv.tastatur = bits;
  aktiv.joyTasten = {
    x: (gehalten.has("ArrowRight") ? 1 : 0) - (gehalten.has("ArrowLeft") ? 1 : 0),
    y: (gehalten.has("ArrowUp") ? 1 : 0) - (gehalten.has("ArrowDown") ? 1 : 0),
  };
  aktiv.eingabenSchreiben();
}
addEventListener("keydown", (e) => {
  if (e.target.closest && e.target.closest("input, select, textarea")) return;
  const p = { KeyQ: [39, -0.05], KeyE: [39, 0.05], KeyZ: [36, -0.05], KeyY: [36, -0.05], KeyC: [36, 0.05] }[e.code];
  if (p && aktiv) { aktiv.potiSetzen(p[0], aktiv.poti[p[0]] + p[1]); e.preventDefault(); return; }
  if (e.code in TASTEN || e.code.startsWith("Arrow")) {
    e.preventDefault();
    tonAn();
    gehalten.add(e.code);
    tastaturAuswerten();
  }
});
addEventListener("keyup", (e) => { if (gehalten.delete(e.code)) tastaturAuswerten(); });
addEventListener("blur", () => { gehalten.clear(); tastaturAuswerten(); });

function v(x) { return x.toFixed(2).replace(".", ",") + " V"; }
function messprotokoll() {
  const b = aktiv;
  if (!b) return;
  const j = b.joystick();
  const s4 = (b.tasten | b.tastatur) & (1 << 4);
  const zeilen = [
    ["MP4", "Taster S4", s4 ? 3.3 : 0],
    ["MP0", "Poti RP0", b.poti[36] * 3.3],
    ["MP3", "Poti RP3", b.poti[39] * 3.3],
    ["MP6", "Joystick X (RJ6)", 1.65 + j.x * 1.65],
    ["MP7", "Joystick Y (RJ7)", 1.65 + j.y * 1.65],
  ];
  $("#mess").innerHTML = zeilen.map(([mp, was, u]) =>
    `<tr><td><b>${mp}</b> · ${was}<div class="balken"><i style="width:${(u / 3.3) * 100}%"></i></div></td><td class="wert">${v(u)}</td></tr>`).join("");
}

// ------------------------------------------------------------------
//  Start
// ------------------------------------------------------------------
$("#teile").innerHTML = BAUTEILE.map((b) => `<li><button type="button" data-sel="${b.sel}">${b.name}</button><br><small>${b.info}</small></li>`).join("");
$("#teile").addEventListener("click", (e) => {
  const knopf = e.target.closest("button");
  if (!knopf || !aktiv) return;
  const el = $(knopf.dataset.sel, aktiv.boardEl);
  if (!el) return;
  el.classList.remove("bauteil-markiert");
  void el.offsetWidth;
  el.classList.add("bauteil-markiert");
  aktiv.boardEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
$("#opt-nummern").addEventListener("change", (e) => { for (const b of boards) b.boardEl.classList.toggle("zeige-nummern", e.target.checked); });
$("#opt-timing").addEventListener("change", (e) => { for (const b of boards) Atomics.store(b.io, IO.REAL_TIMING, e.target.checked ? 1 : 0); });
$("#opt-ton").addEventListener("change", (e) => { if (e.target.checked) { tonAn(); audio && audio.resume(); } });
$("#zweites").addEventListener("click", (e) => {
  if (boards.length >= MAX_BOARDS) return;
  const b = new Board(boards.length);
  boards.push(b);
  b.programmeEintragen();
  b.boardEl.classList.toggle("zeige-nummern", $("#opt-nummern").checked);
  e.target.hidden = true;
  setAktiv(b);
  if (quelle.ordner.length) b.start();
});
$("#quelle").addEventListener("submit", async (e) => {
  e.preventDefault();
  dateiCache.clear();
  await ladeProgrammliste();
  for (const b of boards) if (b.worker) b.start();
});

boards.push(new Board(0));
setAktiv(boards[0]);
function schleife() {
  for (const b of boards) b.zeichnen();
  requestAnimationFrame(schleife);
}
requestAnimationFrame(schleife);
await ladeProgrammliste();
if (self.crossOriginIsolated && quelle.ordner.length) boards[0].start();

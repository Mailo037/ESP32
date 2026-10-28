// Gemeinsamer Kern des espBoard-Simulators (Hauptseite + Worker).
// Speicher-Layout der SharedArrayBuffer, SSD1306-Nachbau und ESP-NOW-Postfach.

// ---- io: Int32Array(IO_LEN) pro Board ----
export const IO_LEN = 128;
export const IO = {
  BUTTONS: 0,      // Bitmaske: Bit n = GPIO n gedrueckt
  ADC34: 1, ADC35: 2, ADC36: 3, ADC39: 4,
  OUT_LO: 8,       // Ausgangspegel GPIO 0..31
  OUT_HI: 9,       // Ausgangspegel GPIO 32..39
  DISP: 15,        // Bit0 = an, Bit1 = invertiert, Bits 8..15 = Kontrast
  FRAME: 16,       // wird bei jeder Display-Uebertragung erhoeht
  SLEEP: 20,       // nur zum Warten (Atomics.wait)
  REAL_TIMING: 21, // 1 = I2C-Uebertragung dauert so lange wie echt
  ESPNOW_ON: 22,   // 1 = ESP-NOW aktiv
  RUNNING: 23,     // 1 = Programm laeuft
  I2C_BYTES: 24,   // gesendete I2C-Bytes (Statistik)
  PWM_FREQ: 40,    // + Pin
  PWM_DUTY: 80,    // + Pin
};
export const ADC_INDEX = { 34: IO.ADC34, 35: IO.ADC35, 36: IO.ADC36, 39: IO.ADC39 };
export const BUTTON_PINS = [2, 4, 5, 16, 17];

// ---- SSD1306-Controller ----
// Bekommt die rohen I2C-Bytes und schreibt in den Bildspeicher (1024 Byte),
// genau wie das echte Display. So sieht man auch Fehler im Treiber.
export class SSD1306Emu {
  constructor(ram, io) {
    this.ram = ram;          // Uint8Array(1024)
    this.io = io;            // Int32Array oder null
    this.col0 = 0; this.col1 = 127; this.page0 = 0; this.page1 = 7;
    this.col = 0; this.page = 0;
    this.mode = 2;           // nach Reset: Page-Adressierung
    this.cmd = [];           // laufender Befehl mit Argumenten
    this.on = false; this.inv = false; this.contrast = 0x7f;
  }
  // Ein I2C-Paket (eine Transaktion) verarbeiten
  transfer(bytes) {
    let i = 0;
    let wroteData = false;
    while (i < bytes.length) {
      const ctrl = bytes[i++];
      const co = ctrl & 0x80;
      const isData = ctrl & 0x40;
      if (co) {
        if (i >= bytes.length) break;
        const b = bytes[i++];
        if (isData) { this.data(b); wroteData = true; } else this.command(b);
      } else {
        for (; i < bytes.length; i++) {
          if (isData) { this.data(bytes[i]); wroteData = true; } else this.command(bytes[i]);
        }
      }
    }
    this.flags();
    if (wroteData && this.io) Atomics.add(this.io, IO.FRAME, 1);
  }
  flags() {
    if (!this.io) return;
    Atomics.store(this.io, IO.DISP, (this.on ? 1 : 0) | (this.inv ? 2 : 0) | (this.contrast << 8));
  }
  data(b) {
    this.ram[this.page * 128 + this.col] = b;
    if (this.mode === 2) {               // Page-Modus
      if (this.col < 127) this.col++;
      return;
    }
    this.col++;
    if (this.col > this.col1) {
      this.col = this.col0;
      if (this.mode === 0) {
        this.page++;
        if (this.page > this.page1) this.page = this.page0;
      }
    }
  }
  command(b) {
    const c = this.cmd;
    if (c.length) {
      c.push(b);
      const need = { 0x20: 2, 0x21: 3, 0x22: 3, 0x81: 2, 0xA8: 2, 0xD3: 2, 0xDA: 2,
                     0xD5: 2, 0xD9: 2, 0xDB: 2, 0x8D: 2 }[c[0]];
      if (c.length < need) return;
      switch (c[0]) {
        case 0x20: this.mode = c[1] & 3; break;
        case 0x21: this.col0 = c[1] & 127; this.col1 = c[2] & 127; this.col = this.col0; break;
        case 0x22: this.page0 = c[1] & 7; this.page1 = c[2] & 7; this.page = this.page0; break;
        case 0x81: this.contrast = c[1]; break;
      }
      this.cmd = [];
      return;
    }
    if ([0x20, 0x21, 0x22, 0x81, 0xA8, 0xD3, 0xDA, 0xD5, 0xD9, 0xDB, 0x8D].includes(b)) {
      this.cmd = [b];
    } else if (b === 0xAE) this.on = false;
    else if (b === 0xAF) this.on = true;
    else if (b === 0xA6) this.inv = false;
    else if (b === 0xA7) this.inv = true;
    else if (b >= 0xB0 && b <= 0xB7) this.page = b & 7;
    else if (b <= 0x0F) this.col = (this.col & 0xF0) | b;
    else if (b >= 0x10 && b <= 0x1F) this.col = (this.col & 0x0F) | ((b & 0x0F) << 4);
    // alle anderen Befehle (Remap, Startzeile, Timing ...) aendern das Bild nicht
  }
}

// ---- ESP-NOW-Postfach (Ringpuffer im SharedArrayBuffer) ----
export const INBOX_SLOTS = 32;
export const SLOT_SIZE = 264;               // 4 Laenge + 6 MAC + 2 frei + 250 Daten (+2)
export const INBOX_BYTES = 16 + INBOX_SLOTS * SLOT_SIZE;

export class Inbox {
  constructor(sab) {
    this.h = new Int32Array(sab, 0, 4);     // [Sperre, Schreib-Index, Lese-Index, Anzahl]
    this.u8 = new Uint8Array(sab);
    this.dv = new DataView(sab);
  }
  lock() { while (Atomics.compareExchange(this.h, 0, 0, 1) !== 0) { /* kurz warten */ } }
  unlock() { Atomics.store(this.h, 0, 0); }
  reset() { this.h[0] = 0; this.h[1] = 0; this.h[2] = 0; this.h[3] = 0; }
  push(mac, data) {
    this.lock();
    try {
      if (this.h[3] >= INBOX_SLOTS) return false;   // voll -> Paket geht verloren
      const base = 16 + this.h[1] * SLOT_SIZE;
      this.dv.setInt32(base, data.length, true);
      this.u8.set(mac, base + 4);
      this.u8.set(data, base + 12);
      this.h[1] = (this.h[1] + 1) % INBOX_SLOTS;
      this.h[3]++;
      return true;
    } finally { this.unlock(); }
  }
  pop() {
    this.lock();
    try {
      if (this.h[3] <= 0) return null;
      const base = 16 + this.h[2] * SLOT_SIZE;
      const n = this.dv.getInt32(base, true);
      const mac = this.u8.slice(base + 4, base + 10);
      const data = this.u8.slice(base + 12, base + 12 + n);
      this.h[2] = (this.h[2] + 1) % INBOX_SLOTS;
      this.h[3]--;
      return { mac, data };
    } finally { this.unlock(); }
  }
  count() { return Atomics.load(this.h, 3); }
}

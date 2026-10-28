import { readFileSync } from "node:fs";
import { Fehler } from "./basis.js";
import { projektDateien, sichererPfad } from "./zip.js";
import { firmwareAktuell, hash } from "./firmware.js";
const baseline = JSON.parse(readFileSync(new URL("../shared-drivers.json", import.meta.url), "utf8"));
export const MAX_PAKET = 512 * 1024;
const protectedNames = new Set(["boot.py", "hub_apps.py", "hub_online.py", "hub_update.py", "hub_galerie.py", "hub_version.json", "hub_online.json"]);

export async function appPaket(dateiname, daten) {
  if (!/\.zip$/i.test(dateiname)) throw new Fehler(400, "Projekte als .zip mit main.py hochladen");
  const files = projektDateien(daten, MAX_PAKET);
  if (!files["main.py"]?.length) throw new Fehler(400, "Im Projekt fehlt main.py");
  const shared = { ...baseline };
  // A configured database must be reachable: never silently deduplicate against stale firmware.
  const active = await firmwareAktuell();
  for (const f of active?.dateien || []) if (["ssd1306.py", "bmp280.py"].includes(f.name)) shared[f.name] = f.sha256;
  const geteilt = [], dateien = [];
  for (const [name, raw] of Object.entries(files)) {
    if (!sichererPfad(name) || name.split("/").some((p) => protectedNames.has(p)) || name === "manifest.json") throw new Fehler(400, "Reservierte Projektdatei: " + name);
    const sha256 = hash(raw);
    if (name.endsWith(".py") && (!Buffer.from(raw.toString("utf8"), "utf8").equals(raw) || raw.includes(0))) throw new Fehler(400, "Python-Datei ist kein UTF-8-Text: " + name);
    const driver = name.replace(/^lib\//, "");
    if (["ssd1306.py", "bmp280.py"].includes(driver) && shared[driver] === sha256) {
      if (!geteilt.some((d) => d.name === driver)) geteilt.push({ name: driver, sha256, groesse: raw.length });
      continue;
    }
    dateien.push({ name, daten: raw.toString("base64") });
  }
  const code = files["main.py"].toString("utf8");
  if (code.includes("\u0000")) throw new Fehler(400, "main.py ist keine Textdatei");
  return { code, datei: dateiname.replace(/\.zip$/i, ".py"), dateien, geteilt };
}

export function paketEintrag(app, record) {
  if (!record.dateien?.length) return app;
  app.dateien = Object.fromEntries(record.dateien.map((f) => [f.name, Buffer.from(f.daten, "base64")]));
  const meta = Object.entries(app.dateien).map(([name, raw]) => ({ name, groesse: raw.length, sha256: hash(raw) }));
  app.eintrag.dateien = meta;
  app.eintrag.geteilt = record.geteilt || [];
  app.eintrag.groesse = meta.reduce((s, f) => s + f.groesse, 0);
  app.eintrag.paket = hash(Buffer.from(JSON.stringify({ dateien: meta, geteilt: app.eintrag.geteilt })));
  return app;
}

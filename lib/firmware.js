import crypto from "node:crypto";
import { Fehler, firebase, firebaseVergleichen } from "./basis.js";
import { projektDateien } from "./zip.js";
export const FIRMWARE_DATEIEN = ["main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json"];
export const VERSION = /^(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})$/;
export const hash = (b) => crypto.createHash("sha256").update(b).digest("hex");
export const neuer = (a, b) => {
  const x = a.split(".").map(Number), y = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
};
export function firmwarePaket(daten, version, notizen = "") {
  if (!VERSION.test(version || "")) throw new Fehler(400, "Firmware-Version muss X.Y.Z sein");
  const files = projektDateien(daten, 512 * 1024);
  if (Object.keys(files).length !== FIRMWARE_DATEIEN.length || FIRMWARE_DATEIEN.some((n) => !files[n]?.length || files[n].length > 256 * 1024)) throw new Fehler(400, "Firmware-ZIP muss genau diese Dateien enthalten (max. 256 KB je Datei): " + FIRMWARE_DATEIEN.join(", "));
  for (const [name, raw] of Object.entries(files)) {
    if (!Buffer.from(raw.toString("utf8"), "utf8").equals(raw) || raw.includes(0)) throw new Fehler(400, "Firmware-Datei ist kein UTF-8-Text: " + name);
  }
  let meta;
  try { meta = JSON.parse(files["hub_version.json"].toString("utf8")); } catch { throw new Fehler(400, "hub_version.json ungueltig"); }
  if (meta.version !== version) throw new Fehler(400, "Version und hub_version.json stimmen nicht ueberein");
  const dateien = FIRMWARE_DATEIEN.map((name) => ({ name, groesse: files[name].length, sha256: hash(files[name]) }));
  const id = hash(Buffer.from(JSON.stringify({ version, dateien })));
  return { id, version, notizen: String(notizen).slice(0, 2000), dateien, groesse: dateien.reduce((s, d) => s + d.groesse, 0), inhalt: FIRMWARE_DATEIEN.map((name) => ({ name, daten: files[name].toString("base64") })) };
}
export function manifest(release) {
  if (!release) return null;
  const { inhalt, ...meta } = release;
  return meta;
}
export async function firmwareAktuell() { return firebase("GET", "esphub_admin/firmware/aktiv"); }
export async function firmwareRelease(id) {
  if (!/^[a-f0-9]{64}$/.test(id || "")) throw new Fehler(400, "Release-ID ungueltig");
  const release = await firebase("GET", `esphub_admin/firmware/releases/${id}`);
  if (!release) throw new Fehler(404, "Firmware unbekannt");
  return release;
}
export async function firmwareErstellen(b) {
  if (!/\.zip$/i.test(b?.dateiname || "")) throw new Fehler(400, "Firmware als ZIP hochladen");
  const release = firmwarePaket(Buffer.from(String(b.daten || ""), "base64"), b.version, b.notizen);
  const alt = await firebase("GET", `esphub_admin/firmware/releases/${release.id}`);
  if (!alt) await firebase("PUT", `esphub_admin/firmware/releases/${release.id}`, { ...release, erstellt: Date.now() });
  await firebaseVergleichen(`esphub_admin/firmware/versionen/${release.version.replaceAll(".", "_")}`, (existing) => {
    if (existing && existing.id !== release.id) throw new Fehler(409, "Diese Versionsnummer ist bereits vergeben");
    return manifest(alt || release);
  });
  return manifest(alt || release);
}
export async function firmwareVeroeffentlichen(id) {
  const release = await firmwareRelease(id);
  const registered = await firebase("GET", `esphub_admin/firmware/versionen/${release.version.replaceAll(".", "_")}`);
  if (registered?.id !== release.id) throw new Fehler(409, "Version ist nicht registriert");
  await firebaseVergleichen("esphub_admin/firmware/aktiv", (aktiv) => {
    if (aktiv && !neuer(release.version, aktiv.version)) throw new Fehler(409, "Nur eine neuere Firmware kann veroeffentlicht werden");
    return manifest(release);
  });
  return manifest(release);
}

import { Fehler, firebase, sitzungLesen, NAME } from "./basis.js";
import { katalog, privateApps, neuer } from "./store.js";
import { firmwareAktuell, firmwareRelease } from "./firmware.js";

export async function simulatorApps(req) {
  const apps = { ...(await katalog()) };
  const konto = sitzungLesen(req, "hubkonto");
  if (konto) {
    if (await firebase("GET", `esphub_admin/konten/${konto}/gesperrt`)) throw new Fehler(403, "Konto gesperrt");
    for (const [id, app] of Object.entries(await privateApps(konto))) {
      if (!apps[id] || !neuer(apps[id].eintrag.version, app.eintrag.version)) apps[id] = app;
    }
  }
  return { apps, angemeldet: !!konto };
}

let driverCache = { id: "", bis: 0, files: [] };
export async function simulatorTreiber() {
  let active = null;
  try { active = await firmwareAktuell(); } catch (e) { if (e.code !== 503) throw e; }
  const id = active?.id || "bootstrap";
  if (driverCache.id === id && driverCache.bis > Date.now()) return driverCache.files;
  let files;
  if (active) {
    files = (await firmwareRelease(active.id)).inhalt.filter((f) => ["ssd1306.py", "bmp280.py"].includes(f.name));
  } else {
    const repo = process.env.GITHUB_REPO || "Mailo037/ESP32";
    const branch = process.env.HUB_GITHUB_BRANCH || "hub";
    files = await Promise.all(["ssd1306.py", "bmp280.py"].map(async (name) => {
      const headers = { "User-Agent": "esphub-simulator" };
      if (process.env.GITHUB_TOKEN) headers.Authorization = "Bearer " + process.env.GITHUB_TOKEN;
      const r = await fetch(`https://raw.githubusercontent.com/${repo}/${encodeURIComponent(branch)}/${name}`, { headers });
      if (!r.ok) throw new Fehler(502, "Gemeinsamer Treiber nicht erreichbar: " + name);
      return { name, daten: Buffer.from(await r.arrayBuffer()).toString("base64") };
    }));
  }
  if (files.length !== 2) throw new Fehler(502, "Firmware-Treiber fehlen");
  driverCache = { id, bis: Date.now() + 300000, files };
  return files;
}

export async function simulatorRoute(req, path, url) {
  if (path === "treiber") return { dateien: await simulatorTreiber() };
  const { apps, angemeldet } = await simulatorApps(req);
  if (path === "apps") return { apps: Object.values(apps).map((a) => ({ ...a.eintrag, quelle: a.quelle })), angemeldet };
  const id = path.startsWith("apps/") ? path.slice(5) : "";
  if (!NAME.test(id)) throw new Fehler(404, "Simulator-Endpunkt unbekannt");
  const app = apps[id];
  if (!app) throw new Fehler(404, "App nicht verfuegbar");
  if (url.searchParams.get("paket") !== (app.eintrag.paket || app.eintrag.sha256)) throw new Fehler(409, "App wurde aktualisiert; Liste neu laden");
  const files = app.dateien || { "main.py": app.roh };
  return { app: app.eintrag, dateien: Object.entries(files).map(([name, raw]) => ({ name, daten: raw.toString("base64") })) };
}

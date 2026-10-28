// App-Store: Apps aus dem GitHub-Repo (Ordner mit main.py) plus Apps,
// die im Admin hochgeladen wurden. Ausgeblendete Apps fehlen im Katalog.
import crypto from "node:crypto";
import { Fehler, firebase, NAME } from "./basis.js";
import { paketEintrag } from "./pakete.js";
import { FIRMWARE_DATEIEN } from "./firmware.js";

const REPO = process.env.GITHUB_REPO || "Mailo037/ESP32";
const BRANCH = process.env.GITHUB_BRANCH || "programs";
const OHNE_ORDNER = new Set(["Hub", "simulator", "docs"]);

let cache = { bis: 0, alle: null };

export function katalogVergessen() {
  cache = { bis: 0, alle: null };
}

export function kopfzeilen(text, ersatzName) {
  const k = { name: ersatzName, version: "", info: "" };
  for (const z of String(text).split("\n").slice(0, 40)) {
    const m = /^#\s*HUB-(NAME|VERSION|INFO):\s*(.*)$/.exec(z.trim());
    if (m) k[m[1].toLowerCase()] = m[2].trim().slice(0, 80);
  }
  return k;
}

export function versionTupel(v) {
  return String(v || "").split(".").map((t) => parseInt(t, 10) || 0);
}

export function neuer(a, b) {
  const x = versionTupel(a), y = versionTupel(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  }
  return false;
}

function eintrag(id, roh, kopf, quelle) {
  return {
    eintrag: {
      id, ...kopf,
      groesse: roh.length,
      sha256: crypto.createHash("sha256").update(roh).digest("hex"),
    },
    roh,
    quelle,
  };
}

async function github(url) {
  const h = { "User-Agent": "esphub" };
  if (process.env.GITHUB_TOKEN) h.Authorization = "Bearer " + process.env.GITHUB_TOKEN;
  const r = await fetch(url, { headers: h });
  if (!r.ok) throw new Fehler(502, "GitHub antwortet mit " + r.status);
  return r;
}

async function vonGithub() {
  const baum = await (await github(`https://api.github.com/repos/${REPO}/git/trees/${encodeURIComponent(BRANCH)}?recursive=1`)).json();
  const ordner = (baum.tree || [])
    .filter((e) => e.type === "blob" && /^[^/]+\/main\.py$/.test(e.path))
    .map((e) => e.path.split("/")[0])
    .filter((o) => !OHNE_ORDNER.has(o) && !o.startsWith("."));
  const apps = {};
  await Promise.all(ordner.map(async (o) => {
    const roh = Buffer.from(await (await github(`https://raw.githubusercontent.com/${REPO}/${encodeURIComponent(BRANCH)}/${encodeURIComponent(o)}/main.py`)).arrayBuffer());
    const id = o.replace(/[^A-Za-z0-9]/g, "_");
    apps[id] = eintrag(id, roh, kopfzeilen(roh.toString("utf8"), o.replace(/-/g, " ")), "github");
  }));
  return apps;
}

/** Alle Apps, auch ausgeblendete: {id: {eintrag, roh, quelle, versteckt}} */
export async function alleApps() {
  if (cache.alle && cache.bis > Date.now()) return cache.alle;
  let gh = {};
  let ghFehler = null;
  try { gh = await vonGithub(); } catch (e) { ghFehler = e.message; }
  let hoch = {}, versteckt = {};
  try {
    [hoch, versteckt] = await Promise.all([firebase("GET", "esphub_admin/apps"), firebase("GET", "esphub_admin/versteckt")]);
  } catch { /* ohne Firebase: nur GitHub */ }
  const alle = { ...gh };
  for (const [id, a] of Object.entries(hoch || {})) {
    if (!NAME.test(id) || !a || typeof a.code !== "string") continue;
    const neu = paketEintrag(eintrag(id, Buffer.from(a.code, "utf8"), { name: a.name, version: a.version, info: a.info || "" }, "upload"), a);
    neu.hochgeladen = a.hochgeladen;
    // gleiche ID wie eine GitHub-App: die neuere Version gewinnt
    if (!alle[id] || !neuer(alle[id].eintrag.version, a.version)) alle[id] = neu;
  }
  for (const a of Object.values(alle)) a.versteckt = !!(versteckt || {})[a.eintrag.id];
  cache = { bis: Date.now() + (ghFehler ? 30000 : 5 * 60000), alle };
  if (ghFehler && !Object.keys(alle).length) throw new Fehler(502, ghFehler);
  return alle;
}

/** Katalog fuer die Boards (ohne ausgeblendete Apps). */
export async function katalog() {
  const alle = await alleApps();
  const k = {};
  for (const [id, a] of Object.entries(alle)) if (!a.versteckt) k[id] = a;
  return k;
}

/** Private Apps eines Kontos (nur auf dessen Boards sichtbar). */
export async function privateApps(konto) {
  if (!konto) return {};
  const roh = (await firebase("GET", `esphub_admin/privat/${konto}`)) || {};
  const apps = {};
  for (const [id, a] of Object.entries(roh)) {
    if (!NAME.test(id) || !a || typeof a.code !== "string") continue;
    const e = paketEintrag(eintrag(id, Buffer.from(a.code, "utf8"), { name: a.name, version: a.version, info: a.info || "" }, "privat"), a);
    e.eintrag.privat = true;
    e.zeit = a.zeit;
    apps[id] = e;
  }
  return apps;
}

/** Katalog fuer ein bestimmtes Board: oeffentlich + private Apps des Besitzers. */
export async function katalogFuer(board) {
  const k = { ...(await katalog()) };
  let konto = null;
  try { konto = await firebase("GET", `esphub_admin/boards/${board}/konto`); } catch { /* ohne Firebase */ }
  for (const [id, a] of Object.entries(await privateApps(konto).catch(() => ({})))) {
    if (!k[id] || !neuer(k[id].eintrag.version, a.eintrag.version)) k[id] = a;
  }
  return k;
}

// ------------------------------------------------------------------
//  Original-Pruefsummen der Hub-Dateien (aus dem Repo, Ordner Hub/)
// ------------------------------------------------------------------
export const HUB_DATEIEN = FIRMWARE_DATEIEN;
let hubCache = { bis: 0, wert: null, quelle: "" };

export async function hubPruefsummen(version) {
  if (/^\d+\.\d+\.\d+$/.test(version || "")) {
    const release = await firebase("GET", `esphub_admin/firmware/versionen/${version.replaceAll(".", "_")}`);
    if (release) return Object.fromEntries(release.dateien.map((f) => [f.name, f.sha256]));
  }
  const legacy = /^2\.0(?:\.0)?$/.test(version || "");
  const branch = legacy ? "main" : (process.env.HUB_GITHUB_BRANCH || "hub");
  const prefix = legacy ? "Hub/" : "";
  const dateien = legacy ? ["main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "ssd1306.py"] : HUB_DATEIEN;
  const quelle = branch + ":" + prefix;
  if (hubCache.wert && hubCache.quelle === quelle && hubCache.bis > Date.now()) return hubCache.wert;
  const wert = {};
  await Promise.all(dateien.map(async (d) => {
    const roh = Buffer.from(await (await github(`https://raw.githubusercontent.com/${REPO}/${encodeURIComponent(branch)}/${prefix}${d}`)).arrayBuffer());
    wert[d] = crypto.createHash("sha256").update(roh).digest("hex");
  }));
  hubCache = { bis: Date.now() + 10 * 60000, wert, quelle };
  return wert;
}

// Portal fuer alle: Konto, Boards koppeln, Apps aus der Ferne
// installieren/entfernen, Apps einreichen (Freigabe im Admin).
import {
  Fehler, firebase, koerper, ID, NAME, sitzungCookie, sitzungLesen, cookieLoeschen,
  passwortHash, passwortPruefen, bremse, zufall,
} from "./basis.js";
import { katalog, katalogFuer, kopfzeilen, privateApps } from "./store.js";
import { zipLesen } from "./zip.js";

const KONTO = /^[a-z0-9_-]{3,24}$/;
const SITZUNG_H = 24 * 7;
const MAX_APP = 200 * 1024;
const KOPPEL_MIN = 10;

export const konto = (req) => sitzungLesen(req, "hubkonto");
export const abmelden = cookieLoeschen("hubkonto");

// ------------------------------------------------------------------
//  Oeffentlich: Galerie + Bestenlisten
// ------------------------------------------------------------------
export async function galerie() {
  let apps = [];
  try { apps = Object.values(await katalog()).map((a) => a.eintrag); } catch { /* GitHub weg */ }
  let boards = {}, spiele = {};
  try {
    [boards, spiele] = await Promise.all([firebase("GET", "esphub_admin/boards"), firebase("GET", "esphub")]);
  } catch { /* ohne Firebase */ }
  const installs = {};
  for (const b of Object.values(boards || {})) for (const id of Object.keys((b && b.apps) || {})) installs[id] = (installs[id] || 0) + 1;
  const listen = {};
  for (const [s, inhalt] of Object.entries(spiele || {})) {
    if (!inhalt || typeof inhalt !== "object") continue;
    listen[s] = {};
    for (const [l, e] of Object.entries(inhalt.listen || {})) {
      // Board-IDs bleiben intern - oeffentlich nur Name und Punkte
      listen[s][l] = Object.values(e || {}).filter((x) => x && typeof x === "object")
        .sort((a, b) => b.p - a.p).slice(0, 20).map((x) => ({ n: x.n, p: x.p, t: x.t }));
    }
  }
  return { apps: apps.map((a) => ({ ...a, installs: installs[a.id] || 0 })), listen };
}

// ------------------------------------------------------------------
//  Konto
// ------------------------------------------------------------------
export async function registrieren(req) {
  const b = await koerper(req);
  const name = String((b && b.name) || "").trim().toLowerCase();
  const pw = String((b && b.passwort) || "");
  if (!KONTO.test(name)) throw new Fehler(400, "Name: 3-24 Zeichen, nur a-z, 0-9, _ und -");
  if (pw.length < 8) throw new Fehler(400, "Passwort: mindestens 8 Zeichen");
  if (await firebase("GET", `esphub_admin/konten/${name}/erstellt`)) throw new Fehler(409, "Name ist schon vergeben");
  await firebase("PUT", `esphub_admin/konten/${name}`, { pw: passwortHash(pw), erstellt: { ".sv": "timestamp" } });
  return sitzungCookie("hubkonto", name, SITZUNG_H);
}

export async function anmelden(req) {
  const b = await koerper(req);
  const name = String((b && b.name) || "").trim().toLowerCase();
  const k = KONTO.test(name) ? await firebase("GET", `esphub_admin/konten/${name}`) : null;
  if (!k || !passwortPruefen((b && b.passwort) || "", k.pw)) {
    await bremse();
    throw new Fehler(401, "Name oder Passwort falsch");
  }
  if (k.gesperrt) throw new Fehler(403, "Konto gesperrt");
  return sitzungCookie("hubkonto", name, SITZUNG_H);
}

async function eigeneBoards(name) {
  return Object.keys((await firebase("GET", `esphub_admin/konten/${name}/boards`)) || {});
}

async function besitzer(name, board) {
  if (!ID.test(board || "")) throw new Fehler(400, "Board-ID ungueltig");
  if ((await firebase("GET", `esphub_admin/boards/${board}/konto`)) !== name) throw new Fehler(403, "Das Board gehoert nicht zu deinem Konto");
}

async function ich(name) {
  const ids = await eigeneBoards(name);
  const boards = {};
  await Promise.all(ids.map(async (id) => {
    const [b, a, sperre] = await Promise.all([
      firebase("GET", `esphub_admin/boards/${id}`),
      firebase("GET", `esphub_admin/auftraege/${id}`),
      firebase("GET", `esphub_admin/gesperrt/${id}`),
    ]);
    const { schluessel, ...rest } = b || {};
    boards[id] = { ...rest, auftraege: { install: Object.keys((a && a.install) || {}), deinstall: Object.keys((a && a.deinstall) || {}) }, gesperrt: !!sperre };
  }));
  const privat = Object.values(await privateApps(name)).map((a) => ({ ...a.eintrag, zeit: a.zeit }));
  const alle = (await firebase("GET", "esphub_admin/einreichungen")) || {};
  const einreichungen = Object.entries(alle).filter(([, e]) => e && e.konto === name)
    .map(([sid, e]) => ({ sid, id: e.id, name: e.name, version: e.version, status: e.status, grund: e.grund || "", zeit: e.zeit }))
    .sort((x, y) => (y.zeit || 0) - (x.zeit || 0));
  return { name, boards, einreichungen, privat };
}

// ------------------------------------------------------------------
//  Board koppeln: Web fragt an -> Board zeigt Code -> Web bestaetigt
// ------------------------------------------------------------------
async function koppelnStarten(name, b) {
  const board = String((b && b.board) || "").trim().toLowerCase();
  if (!ID.test(board)) throw new Fehler(400, "Board-ID: 12 Zeichen 0-9/a-f (am Board unter Board-Info)");
  const info = await firebase("GET", `esphub_admin/boards/${board}`);
  if (!info || !info.schluessel) throw new Fehler(404, "Board unbekannt - es muss sich erst einmal online melden (Board-Info > Jetzt abgleichen)");
  if (info.konto && info.konto !== name) throw new Fehler(409, "Board ist schon mit einem anderen Konto gekoppelt");
  const code = String(100000 + (parseInt(zufall(4), 16) % 900000));
  await firebase("PUT", `esphub_admin/kopplung/${board}`, { konto: name, code, bis: Date.now() + KOPPEL_MIN * 60000, versuche: 0 });
  return { ok: true, minuten: KOPPEL_MIN };
}

async function koppelnBestaetigen(name, b) {
  const board = String((b && b.board) || "").trim().toLowerCase();
  if (!ID.test(board)) throw new Fehler(400, "Board-ID ungueltig");
  const k = await firebase("GET", `esphub_admin/kopplung/${board}`);
  if (!k || k.konto !== name || k.bis < Date.now()) throw new Fehler(410, "Keine offene Kopplung - bitte neu starten");
  if (String((b && b.code) || "").trim() !== k.code) {
    if (k.versuche >= 4) {
      await firebase("DELETE", `esphub_admin/kopplung/${board}`);
      throw new Fehler(429, "Zu viele falsche Codes - bitte neu starten");
    }
    await firebase("PATCH", `esphub_admin/kopplung/${board}`, { versuche: (k.versuche || 0) + 1 });
    await bremse();
    throw new Fehler(401, "Code falsch");
  }
  await firebase("PATCH", `esphub_admin/boards/${board}`, { konto: name });
  await firebase("PUT", `esphub_admin/konten/${name}/boards/${board}`, true);
  await firebase("DELETE", `esphub_admin/kopplung/${board}`);
  return { ok: true };
}

async function entkoppeln(name, board) {
  await besitzer(name, board);
  await firebase("DELETE", `esphub_admin/boards/${board}/konto`);
  await firebase("DELETE", `esphub_admin/konten/${name}/boards/${board}`);
  await firebase("DELETE", `esphub_admin/auftraege/${board}`);
  return { ok: true };
}

// ------------------------------------------------------------------
//  Fern-Installation: Auftrag ablegen, das Board holt ihn beim Abgleich
// ------------------------------------------------------------------
async function auftrag(name, board, b, loeschen) {
  await besitzer(name, board);
  const art = b && b.art;
  const app = String((b && b.app) || "");
  if (!["install", "deinstall"].includes(art) || !NAME.test(app)) throw new Fehler(400, "Auftrag ungueltig");
  if (loeschen) {
    await firebase("DELETE", `esphub_admin/auftraege/${board}/${art}/${app}`);
    return { ok: true };
  }
  if (art === "install" && !(await katalogFuer(board))[app]) throw new Fehler(404, "App nicht im Store");
  const gegen = art === "install" ? "deinstall" : "install";
  await firebase("DELETE", `esphub_admin/auftraege/${board}/${gegen}/${app}`);
  await firebase("PUT", `esphub_admin/auftraege/${board}/${art}/${app}`, true);
  return { ok: true };
}

// ------------------------------------------------------------------
//  App einreichen (.py oder .zip) - erscheint erst nach Freigabe
// ------------------------------------------------------------------
export function codeAusDatei(dateiname, daten) {
  if (/\.zip$/i.test(dateiname)) {
    const d = zipLesen(daten);
    const py = Object.keys(d).filter((n) => /\.py$/i.test(n) && !n.startsWith("__MACOSX"));
    const wahl = py.find((n) => /(^|\/)main\.py$/i.test(n)) || py.find((n) => /(^|\/)gal_[^/]+\.py$/i.test(n)) || (py.length === 1 ? py[0] : null);
    if (!wahl) throw new Fehler(400, "In der ZIP muss main.py, gal_NAME.py oder genau eine .py-Datei liegen");
    return { code: d[wahl].toString("utf8"), datei: wahl.split("/").pop() };
  }
  if (!/\.py$/i.test(dateiname)) throw new Fehler(400, "Nur .py oder .zip");
  return { code: daten.toString("utf8"), datei: dateiname };
}

/** App ablegen: ziel "privat" (sofort im eigenen Konto) oder
 *  "pruefung" (Einreichung, erscheint nach Freigabe fuer alle). */
export async function appAblegen(name, ziel, code, datei) {
  if (!code.trim()) throw new Fehler(400, "Datei ist leer");
  if (Buffer.byteLength(code) > MAX_APP) throw new Fehler(413, "App groesser als 200 KB");
  if (code.includes("\u0000")) throw new Fehler(400, "Keine Textdatei");
  const k = kopfzeilen(code, "");
  const id = (datei.startsWith("gal_") ? datei.slice(4).replace(/\.py$/i, "") : (k.name || datei.replace(/\.py$/i, "")))
    .replace(/[^A-Za-z0-9]/g, "_").slice(0, 40);
  if (!NAME.test(id) || id === "main") throw new Fehler(400, "Bitte # HUB-NAME: in die erste Zeile schreiben");
  const meta = { name: (k.name || id.replace(/_/g, " ")).slice(0, 40), version: k.version || "1.0", info: k.info || "", code, zeit: { ".sv": "timestamp" } };
  if (ziel === "privat") {
    await firebase("PUT", `esphub_admin/privat/${name}/${id}`, meta);
  } else {
    const sid = Date.now().toString(36) + zufall(3);
    await firebase("PUT", `esphub_admin/einreichungen/${sid}`, { ...meta, konto: name, id, status: "offen" });
  }
  return { ok: true, id, version: meta.version, ziel };
}

async function einreichen(name, req) {
  const b = await koerper(req, Math.ceil(MAX_APP * 1.4) + 4096);
  const daten = Buffer.from(String((b && b.daten) || ""), "base64");
  if (!daten.length) throw new Fehler(400, "Datei ist leer");
  const { code, datei } = codeAusDatei(String((b && b.dateiname) || ""), daten);
  return appAblegen(name, b && b.ziel === "privat" ? "privat" : "pruefung", code, datei);
}

/** Upload direkt vom Board (gekoppelt): roher Dateiinhalt im Body. */
export async function vomBoard(board, ziel, datei, code) {
  const name = await firebase("GET", `esphub_admin/boards/${board}/konto`);
  if (!name) throw new Fehler(403, "Board ist mit keinem Konto gekoppelt");
  if (!/^gal_[A-Za-z0-9_]{1,40}\.py$/.test(datei)) throw new Fehler(400, "Dateiname ungueltig");
  return appAblegen(name, ziel === "privat" ? "privat" : "pruefung", code, datei);
}

// ------------------------------------------------------------------
//  Router fuer /portal/api/... (angemeldet)
// ------------------------------------------------------------------
export async function portalApi(req, methode, pfad) {
  const name = konto(req);
  if (!name) throw new Fehler(401, "Nicht angemeldet");
  if (methode !== "GET" && req.headers["x-hub-konto"] !== "1") throw new Fehler(403, "Kopfzeile fehlt");
  const k = await firebase("GET", `esphub_admin/konten/${name}/gesperrt`);
  if (k) throw new Fehler(403, "Konto gesperrt");
  const t = pfad.split("/").filter(Boolean);
  if (t[0] === "ich" && methode === "GET") return ich(name);
  if (t[0] === "koppeln" && !t[1] && methode === "POST") return koppelnStarten(name, await koerper(req));
  if (t[0] === "koppeln" && t[1] === "bestaetigen" && methode === "POST") return koppelnBestaetigen(name, await koerper(req));
  if (t[0] === "board" && t[2] === "entkoppeln" && methode === "POST") return entkoppeln(name, t[1]);
  if (t[0] === "board" && t[2] === "auftrag" && (methode === "POST" || methode === "DELETE")) return auftrag(name, t[1], await koerper(req), methode === "DELETE");
  if (t[0] === "einreichen" && methode === "POST") return einreichen(name, req);
  if (t[0] === "privat" && NAME.test(t[1] || "")) {
    const a = await firebase("GET", `esphub_admin/privat/${name}/${t[1]}`);
    if (!a) throw new Fehler(404, "App unbekannt");
    if (!t[2] && methode === "DELETE") {
      await firebase("DELETE", `esphub_admin/privat/${name}/${t[1]}`);
      return { ok: true };
    }
    if (t[2] === "pruefen" && methode === "POST") return appAblegen(name, "pruefung", a.code, "gal_" + t[1] + ".py");
  }
  throw new Fehler(404, "unbekannt");
}

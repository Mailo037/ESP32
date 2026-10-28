// Admin: Anmeldung (Passwort = ADMIN_TOKEN) und alle Verwaltungs-Aktionen.
import { Fehler, firebase, koerper, ID, NAME, gleich, sitzungCookie, sitzungLesen, cookieLoeschen, bremse } from "./basis.js";
import { alleApps, katalogVergessen, kopfzeilen } from "./store.js";
import { limits, limitsVergessen, sperrenVergessen, schluesselVergessen, regelnVergessen, STANDARD_LIMITS } from "./boards.js";

const SITZUNG_H = 12;
const MAX_APP = 200 * 1024;

// ------------------------------------------------------------------
//  Sitzung: signiertes Cookie, kein Passwort im Browser gespeichert
// ------------------------------------------------------------------
export function angemeldet(req) {
  return sitzungLesen(req, "hubadmin") === "admin";
}

export async function anmelden(req) {
  const b = await koerper(req);
  const soll = process.env.ADMIN_TOKEN || "";
  if (soll.length < 8) throw new Fehler(503, "ADMIN_TOKEN ist in Vercel nicht gesetzt (mind. 8 Zeichen)");
  if (!b || !gleich(b.passwort || "", soll)) {
    await bremse();                       // Raten bremsen
    throw new Fehler(401, "Falsches Passwort");
  }
  return sitzungCookie("hubadmin", "admin", SITZUNG_H);
}

export const abmeldenCookie = cookieLoeschen("hubadmin");

// ------------------------------------------------------------------
//  Gesamtstand fuer die Oberflaeche
// ------------------------------------------------------------------
async function stand() {
  const [boardsRoh, belegt, gesperrt, spieleFlach, kontenRoh, einrRoh, auftraege, einstellungen, hoechstpunkte] = await Promise.all([
    firebase("GET", "esphub_admin/boards"),
    firebase("GET", "esphub_admin/belegt"),
    firebase("GET", "esphub_admin/gesperrt"),
    firebase("GET", "esphub", undefined, "shallow=true&"),
    firebase("GET", "esphub_admin/konten"),
    firebase("GET", "esphub_admin/einreichungen"),
    firebase("GET", "esphub_admin/auftraege"),
    firebase("GET", "esphub_admin/einstellungen"),
    firebase("GET", "esphub_admin/hoechstpunkte"),
  ]);
  // Geheimes nie an den Browser: Schluessel-Hashes, Passwort-Hashes, Code
  const boards = {};
  for (const [id, b] of Object.entries(boardsRoh || {})) {
    const { schluessel, ...rest } = b || {};
    boards[id] = { ...rest, registriert: !!schluessel };
  }
  const konten = {};
  for (const [n, k] of Object.entries(kontenRoh || {})) {
    konten[n] = { erstellt: k && k.erstellt, gesperrt: !!(k && k.gesperrt), boards: Object.keys((k && k.boards) || {}) };
  }
  const einreichungen = Object.entries(einrRoh || {}).map(([sid, e]) => ({
    sid, konto: e.konto, id: e.id, name: e.name, version: e.version, info: e.info, status: e.status,
    grund: e.grund || "", zeit: e.zeit, groesse: Buffer.byteLength(e.code || ""),
  })).sort((a, b) => (b.zeit || 0) - (a.zeit || 0));
  let apps = {};
  let appsFehler = null;
  try { apps = await alleApps(); } catch (e) { appsFehler = e.message; }
  const spiele = {};
  await Promise.all(Object.keys(spieleFlach || {}).map(async (s) => {
    const [listen, global] = await Promise.all([firebase("GET", `esphub/${s}/listen`), firebase("GET", `esphub/${s}/global`)]);
    spiele[s] = { listen: listen || {}, global: global || {} };
  }));
  return {
    zeit: Date.now(),
    boards,
    konten,
    einreichungen,
    auftraege: auftraege || {},
    einstellungen: { veraendert: "erlauben", ...(einstellungen || {}) },
    hoechstpunkte: hoechstpunkte || {},
    belegt: belegt || {},
    gesperrt: gesperrt || {},
    limits: await limits(),
    apps: Object.values(apps).map((a) => ({ ...a.eintrag, quelle: a.quelle, versteckt: a.versteckt, hochgeladen: a.hochgeladen || null })),
    appsFehler,
    spiele,
  };
}

function zahl(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n) || n < 0 || n > 10 * 1024 * 1024) throw new Fehler(400, "Limit ungueltig: " + v);
  return n;
}

async function boardLoeschen(id, auchDaten) {
  const besitzer = await firebase("GET", `esphub_admin/boards/${id}/konto`);
  if (besitzer && !auchDaten) await firebase("DELETE", `esphub_admin/konten/${besitzer}/boards/${id}`);
  if (auchDaten) {
    const spiele = Object.keys((await firebase("GET", "esphub", undefined, "shallow=true&")) || {});
    for (const s of spiele) {
      await firebase("DELETE", `esphub/${s}/boards/${id}`);
      const listen = Object.keys((await firebase("GET", `esphub/${s}/listen`, undefined, "shallow=true&")) || {});
      for (const l of listen) await firebase("DELETE", `esphub/${s}/listen/${l}/${id}`);
    }
    await firebase("DELETE", `esphub_admin/belegt/${id}`);
  }
  if (!auchDaten) {
    // Entfernen = Board vergessen inkl. Schluessel: beim naechsten
    // Abgleich meldet es sich neu an (z. B. nach neuem Flashen)
    await firebase("DELETE", `esphub_admin/boards/${id}`);
    await firebase("DELETE", `esphub_admin/auftraege/${id}`);
    schluesselVergessen(id);
  }
}

async function hochladen(b) {
  const code = String((b && b.code) || "");
  if (!code.trim()) throw new Fehler(400, "Datei ist leer");
  if (Buffer.byteLength(code) > MAX_APP) throw new Fehler(413, "App groesser als 200 KB");
  const k = kopfzeilen(code, "");
  let id = String((b && b.id) || k.name || "").replace(/^gal_/, "").replace(/\.py$/, "").replace(/[^A-Za-z0-9]/g, "_").slice(0, 40);
  if (!NAME.test(id)) throw new Fehler(400, "App-ID fehlt (Dateiname oder # HUB-NAME:)");
  const eintrag = {
    name: (k.name || id.replace(/_/g, " ")).slice(0, 40),
    version: k.version || "1.0",
    info: k.info || "",
    code,
    hochgeladen: { ".sv": "timestamp" },
  };
  await firebase("PUT", `esphub_admin/apps/${id}`, eintrag);
  katalogVergessen();
  return { id, name: eintrag.name, version: eintrag.version };
}

// ------------------------------------------------------------------
//  Router fuer /admin/api/...
// ------------------------------------------------------------------
export async function adminApi(req, methode, pfad) {
  if (!angemeldet(req)) throw new Fehler(401, "Nicht angemeldet");
  // Gegen fremde Seiten (CSRF): Aenderungen nur mit eigenem Kopf
  if (methode !== "GET" && req.headers["x-hub-admin"] !== "1") throw new Fehler(403, "Kopfzeile fehlt");
  const t = pfad.split("/").filter(Boolean);

  if (t[0] === "stand" && methode === "GET") return stand();

  if (t[0] === "limits" && methode === "PUT") {
    const b = await koerper(req, 65536);
    const l = {
      standard: { app: zahl(b?.standard?.app ?? STANDARD_LIMITS.app), board: zahl(b?.standard?.board ?? STANDARD_LIMITS.board) },
      boards: {}, apps: {},
    };
    for (const [k, v] of Object.entries(b?.boards || {})) { if (!ID.test(k)) throw new Fehler(400, "Board-ID: " + k); l.boards[k] = zahl(v); }
    for (const [k, v] of Object.entries(b?.apps || {})) { if (!NAME.test(k)) throw new Fehler(400, "App: " + k); l.apps[k] = zahl(v); }
    await firebase("PUT", "esphub_admin/limits", l);
    limitsVergessen();
    return { ok: true };
  }

  if (t[0] === "board" && ID.test(t[1] || "")) {
    const id = t[1];
    if (t[2] === "sperren" && methode === "POST") {
      const b = await koerper(req);
      if (b && b.gesperrt) {
        await firebase("PUT", `esphub_admin/gesperrt/${id}`, { grund: String(b.grund || "").slice(0, 80), seit: { ".sv": "timestamp" } });
      } else {
        await firebase("DELETE", `esphub_admin/gesperrt/${id}`);
      }
      sperrenVergessen();
      return { ok: true };
    }
    if (!t[2] && methode === "DELETE") {
      await boardLoeschen(id, new URL(req.url, "http://x").searchParams.get("daten") === "1");
      return { ok: true };
    }
  }

  if (t[0] === "apps") {
    if (!t[1] && methode === "POST") return hochladen(await koerper(req, MAX_APP + 4096));
    const id = t[1];
    if (!NAME.test(id || "")) throw new Fehler(400, "App-ID ungueltig");
    if (t[2] === "code" && methode === "GET") {
      const a = (await alleApps())[id];
      if (!a) throw new Fehler(404, "App unbekannt");
      return { id, code: a.roh.toString("utf8"), quelle: a.quelle };
    }
    if (t[2] === "versteckt" && methode === "POST") {
      const b = await koerper(req);
      await firebase(b && b.versteckt ? "PUT" : "DELETE", `esphub_admin/versteckt/${id}`, b && b.versteckt ? true : undefined);
      katalogVergessen();
      return { ok: true };
    }
    if (!t[2] && methode === "DELETE") {
      await firebase("DELETE", `esphub_admin/apps/${id}`);
      katalogVergessen();
      return { ok: true };
    }
  }

  if (t[0] === "einreichung" && /^[a-z0-9]{6,20}$/.test(t[1] || "")) {
    const e = await firebase("GET", `esphub_admin/einreichungen/${t[1]}`);
    if (!e) throw new Fehler(404, "Einreichung unbekannt");
    if (t[2] === "code" && methode === "GET") return { id: e.id, code: e.code, quelle: "Einreichung von " + e.konto };
    if (t[2] === "annehmen" && methode === "POST") {
      await firebase("PUT", `esphub_admin/apps/${e.id}`, {
        name: e.name, version: e.version, info: e.info || "", code: e.code, autor: e.konto, hochgeladen: { ".sv": "timestamp" },
      });
      await firebase("PATCH", `esphub_admin/einreichungen/${t[1]}`, { status: "angenommen" });
      katalogVergessen();
      return { ok: true };
    }
    if (t[2] === "ablehnen" && methode === "POST") {
      const b = await koerper(req);
      await firebase("PATCH", `esphub_admin/einreichungen/${t[1]}`, { status: "abgelehnt", grund: String((b && b.grund) || "").slice(0, 200) });
      return { ok: true };
    }
    if (!t[2] && methode === "DELETE") {
      await firebase("DELETE", `esphub_admin/einreichungen/${t[1]}`);
      return { ok: true };
    }
  }

  if (t[0] === "konto" && /^[a-z0-9_-]{3,24}$/.test(t[1] || "")) {
    if (t[2] === "sperren" && methode === "POST") {
      const b = await koerper(req);
      await firebase(b && b.gesperrt ? "PUT" : "DELETE", `esphub_admin/konten/${t[1]}/gesperrt`, b && b.gesperrt ? true : undefined);
      return { ok: true };
    }
    if (!t[2] && methode === "DELETE") {
      for (const id of Object.keys((await firebase("GET", `esphub_admin/konten/${t[1]}/boards`)) || {})) {
        await firebase("DELETE", `esphub_admin/boards/${id}/konto`);
        await firebase("DELETE", `esphub_admin/auftraege/${id}`);
      }
      await firebase("DELETE", `esphub_admin/konten/${t[1]}`);
      return { ok: true };
    }
  }

  if (t[0] === "einstellungen" && methode === "PUT") {
    const b = await koerper(req);
    const v = b && b.veraendert;
    if (!["erlauben", "lesen", "sperren"].includes(v)) throw new Fehler(400, "Regel ungueltig");
    await firebase("PUT", "esphub_admin/einstellungen/veraendert", v);
    regelnVergessen();
    return { ok: true };
  }

  if (t[0] === "hoechstpunkte" && methode === "PUT" && NAME.test(t[1] || "") && NAME.test(t[2] || "")) {
    const b = await koerper(req);
    if (b && b.max === null) await firebase("DELETE", `esphub_admin/hoechstpunkte/${t[1]}/${t[2]}`);
    else await firebase("PUT", `esphub_admin/hoechstpunkte/${t[1]}/${t[2]}`, Math.round(Number(b && b.max)) || 0);
    return { ok: true };
  }

  if (t[0] === "listen" && methode === "DELETE" && NAME.test(t[1] || "") && NAME.test(t[2] || "") && ID.test(t[3] || "")) {
    await firebase("DELETE", `esphub/${t[1]}/listen/${t[2]}/${t[3]}`);
    return { ok: true };
  }

  throw new Fehler(404, "unbekannt");
}

// Alles, was die Boards ansprechen: Online-Speicher, Limits, Anmeldung.
import { Fehler, firebase, ID, NAME, SCHLUESSEL, sha256, zufall } from "./basis.js";
import { hubPruefsummen, HUB_DATEIEN } from "./store.js";

export const STANDARD_LIMITS = { app: 4096, board: 32768 };

// ------------------------------------------------------------------
//  Sperren
// ------------------------------------------------------------------
let sperrCache = { bis: 0, wert: {} };

export function sperrenVergessen() {
  sperrCache = { bis: 0, wert: {} };
}

export async function gesperrt(board) {
  if (sperrCache.bis < Date.now()) {
    let wert = {};
    try {
      wert = (await firebase("GET", "esphub_admin/gesperrt")) || {};
    } catch (e) {
      if (e.code !== 503) throw e;         // ohne Firebase ist nichts gesperrt
    }
    sperrCache = { bis: Date.now() + 20000, wert };
  }
  return sperrCache.wert[board] || null;
}

// ------------------------------------------------------------------
//  Limits
// ------------------------------------------------------------------
let limitCache = { bis: 0, wert: null };

export function limitsVergessen() {
  limitCache = { bis: 0, wert: null };
}

export async function limits() {
  if (limitCache.wert && limitCache.bis > Date.now()) return limitCache.wert;
  const l = (await firebase("GET", "esphub_admin/limits")) || {};
  const wert = { standard: { ...STANDARD_LIMITS, ...(l.standard || {}) }, boards: l.boards || {}, apps: l.apps || {} };
  limitCache = { bis: Date.now() + 30000, wert };
  return wert;
}

export async function limitsFuer(board, spiel) {
  const l = await limits();
  const belegt = (await firebase("GET", `esphub_admin/belegt/${board}`)) || {};
  return {
    app: l.apps[spiel] ?? l.standard.app,
    board: l.boards[board] ?? l.standard.board,
    belegt: Object.values(belegt).reduce((a, b) => a + (+b || 0), 0),
    belegt_app: +belegt[spiel] || 0,
  };
}

const bytes = (w) => (w === null || w === undefined ? 0 : Buffer.byteLength(JSON.stringify(w)));

async function boardSchreiben(spiel, board, patch) {
  const alt = (await firebase("GET", `esphub/${spiel}/boards/${board}`)) || {};
  const neu = { ...alt };
  for (const [k, v] of Object.entries(patch)) {
    if (v === null) delete neu[k];
    else neu[k] = v;
  }
  const groesse = bytes(neu);
  const l = await limitsFuer(board, spiel);
  if (groesse > l.app) throw new Fehler(413, `Limit der App: ${groesse} > ${l.app} Bytes`);
  if (l.belegt - l.belegt_app + groesse > l.board) throw new Fehler(413, `Limit des Boards: ${l.board} Bytes`);
  const r = await firebase("PATCH", `esphub/${spiel}/boards/${board}`, patch);
  await firebase("PUT", `esphub_admin/belegt/${board}/${spiel}`, groesse);
  return r;
}

// ------------------------------------------------------------------
//  Board-Schluessel: bei der ersten Anmeldung vergibt der Server einen
//  geheimen Schluessel, den nur dieses Board kennt (liegt im Hub unter
//  /hubdaten/). Danach gilt jede Anfrage ohne passenden Schluessel als
//  fremd. Im Admin kann man ein Board zuruecksetzen.
// ------------------------------------------------------------------
const schluesselCache = new Map();

export function schluesselVergessen(board) {
  schluesselCache.delete(board);
}

async function schluesselHash(board) {
  const c = schluesselCache.get(board);
  if (c && c.bis > Date.now()) return c.hash;
  const hash = (await firebase("GET", `esphub_admin/boards/${board}/schluessel`)) || "";
  schluesselCache.set(board, { hash, bis: Date.now() + 60000 });
  return hash;
}

/** true = Board hat schon einen Schluessel und der passt. false = Board
 *  ist neu (nur /melden erlaubt). Wirft bei falschem Schluessel. */
export async function boardPruefen(board, schluessel) {
  const hash = await schluesselHash(board);
  if (!hash) return false;
  if (!schluessel || sha256(schluessel) !== hash) throw new Fehler(403, "Board-Schluessel falsch - im Admin zuruecksetzen");
  return true;
}

// ------------------------------------------------------------------
//  Anmeldung: das Board meldet Hub-Version, Apps, Nutzung und Speicher;
//  zurueck bekommt es offene Auftraege (Fern-Installation)
// ------------------------------------------------------------------
export async function melden(board, b, bekannt) {
  const apps = {};
  for (const [id, v] of Object.entries((b && b.apps) || {}).slice(0, 60)) {
    if (NAME.test(id)) apps[id] = String(v || "").slice(0, 16);
  }
  const nutzung = {};
  for (const [id, n] of Object.entries((b && b.nutzung) || {}).slice(0, 60)) {
    if (NAME.test(id) && n && typeof n === "object") nutzung[id] = { hub: !!n.hub, web: !!n.web, funk: !!(n.funk || n.now) };
  }
  const zahl = (x) => (Number.isFinite(+x) ? Math.max(0, Math.round(+x)) : null);
  // Hub-Dateien mit dem Original vergleichen. Ein absichtlich veraenderter
  // Hub kann hier luegen - das erkennt nur Basteleien, keine Betrueger.
  let veraendert = null;
  try {
    const soll = await hubPruefsummen();
    const ist = (b && b.pruef) || {};
    veraendert = HUB_DATEIEN.filter((d) => ist[d] !== soll[d]);
  } catch { /* GitHub nicht erreichbar: unbekannt */ }
  const info = {
    nr: zahl(b && b.nr),
    hub: String((b && b.hub) || "").slice(0, 16),
    apps,
    nutzung,
    frei: zahl(b && b.frei),
    ram: zahl(b && b.ram),
    veraendert: veraendert === null ? null : veraendert.length ? veraendert : false,
    zuletzt: { ".sv": "timestamp" },
  };
  regelCache.delete(board);
  const antwort = { gesperrt: false };
  if (!bekannt) {
    const s = zufall(24);
    info.schluessel = sha256(s);
    info.erstes = { ".sv": "timestamp" };
    antwort.schluessel = s;
    schluesselVergessen(board);
  }
  await firebase("PATCH", `esphub_admin/boards/${board}`, info);

  // erledigte Auftraege abhaken, offene mitgeben
  const erledigt = (b && b.erledigt) || {};
  for (const art of ["install", "deinstall"]) {
    for (const id of [].concat(erledigt[art] || []).slice(0, 60)) {
      if (NAME.test(String(id))) await firebase("DELETE", `esphub_admin/auftraege/${board}/${art}/${id}`);
    }
  }
  const a = (await firebase("GET", `esphub_admin/auftraege/${board}`)) || {};
  antwort.auftraege = { install: Object.keys(a.install || {}), deinstall: Object.keys(a.deinstall || {}) };
  antwort.konto = (await firebase("GET", `esphub_admin/boards/${board}/konto`)) || null;
  return antwort;
}

// ------------------------------------------------------------------
//  Regel fuer veraenderte Hubs: "erlauben" | "lesen" (nur lesen) | "sperren"
// ------------------------------------------------------------------
const regelCache = new Map();

export function regelnVergessen() {
  regelCache.clear();
}

export async function veraendertRegel(board) {
  const c = regelCache.get(board);
  if (c && c.bis > Date.now()) return c.wert;
  const [v, regel] = await Promise.all([
    firebase("GET", `esphub_admin/boards/${board}/veraendert`),
    firebase("GET", "esphub_admin/einstellungen/veraendert"),
  ]);
  const wert = v ? regel || "erlauben" : "erlauben";
  regelCache.set(board, { wert, bis: Date.now() + 30000 });
  return wert;
}

// ------------------------------------------------------------------
//  Kopplung: das Board holt den Code, den es auf dem OLED zeigt
// ------------------------------------------------------------------
export async function kopplungFuerBoard(board) {
  const [k, konto] = await Promise.all([
    firebase("GET", `esphub_admin/kopplung/${board}`),
    firebase("GET", `esphub_admin/boards/${board}/konto`),
  ]);
  if (k && k.bis > Date.now()) return { code: k.code, konto: k.konto };
  return { gekoppelt: konto || null };
}

// ------------------------------------------------------------------
//  Online-Speicher: nur diese Zugriffe sind erlaubt
// ------------------------------------------------------------------
const klein = (w) => JSON.stringify(w).length <= 512;

export async function speicher(methode, teile, body, board) {
  if (teile.length === 1 && teile[0] === "_ping" && methode === "GET") return null;
  const [spiel, art, a, b] = teile;
  if (!NAME.test(spiel || "")) throw new Fehler(400, "Spielname ungueltig");
  const basis = `esphub/${spiel}/`;
  // Ein Board darf nur unter der eigenen ID schreiben
  const eigen = (id) => {
    if (id !== board) throw new Fehler(403, "fremde Board-ID");
  };
  if (art === "boards" && teile.length === 3 && ID.test(a)) {
    eigen(a);
    if (methode === "GET") return firebase("GET", basis + `boards/${a}`);
    if (methode === "DELETE") {
      await firebase("DELETE", basis + `boards/${a}`);
      await firebase("DELETE", `esphub_admin/belegt/${a}/${spiel}`);
      return null;
    }
    if (methode === "PATCH") {
      if (!body || typeof body !== "object" || Array.isArray(body)) throw new Fehler(400, "Objekt erwartet");
      for (const k of Object.keys(body)) if (!SCHLUESSEL.test(k)) throw new Fehler(400, "Schluessel ungueltig: " + k);
      return boardSchreiben(spiel, a, body);
    }
  }
  if (art === "global" && teile.length === 2) {
    if (methode === "GET") return firebase("GET", basis + "global");
    if (methode === "PATCH") {
      if (!body || typeof body !== "object" || Array.isArray(body)) throw new Fehler(400, "Objekt erwartet");
      for (const [k, v] of Object.entries(body)) {
        if (!SCHLUESSEL.test(k)) throw new Fehler(400, "Schluessel ungueltig: " + k);
        const plus = v && typeof v === "object" && v[".sv"] && typeof v[".sv"].increment === "number";
        if (!plus && !klein(v)) throw new Fehler(400, "Wert zu gross: " + k);
      }
      return firebase("PATCH", basis + "global", body);
    }
  }
  if (art === "listen" && teile.length === 2 && methode === "GET") return firebase("GET", basis + "listen");
  if (art === "listen" && teile.length === 4 && NAME.test(a) && ID.test(b)) {
    eigen(b);
    if (methode === "DELETE") return firebase("DELETE", basis + `listen/${a}/${b}`);
    if (methode === "PUT") {
      if (!body || typeof body.p !== "number" || !isFinite(body.p)) throw new Fehler(400, "Punkte fehlen");
      const max = await firebase("GET", `esphub_admin/hoechstpunkte/${spiel}/${a}`);
      if (typeof max === "number" && (body.p > max || body.p < 0)) throw new Fehler(422, "Punkte unplausibel (max. " + max + ")");
      // Eintrag neu aufbauen - nur diese Felder kommen in die Datenbank
      return firebase("PUT", basis + `listen/${a}/${b}`, { n: String(body.n || "").slice(0, 10), p: body.p, t: { ".sv": "timestamp" } });
    }
  }
  throw new Fehler(403, "nicht erlaubt");
}

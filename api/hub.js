// ESP-Hub-Backend auf Vercel - die Bruecke zwischen den Boards und Firebase.
// Die Firebase-Zugangsdaten liegen nur in den Vercel-Umgebungsvariablen;
// weder die Boards noch der Browser bekommen sie je zu sehen.
//
//   Fuer die Boards (immer mit ?board=<ID>, optional &auth=<HUB_TOKEN>):
//     /esphub/<pfad>.json     Online-Speicher (geprueft, mit Limits)
//     /apps, /apps/<id>       App-Store
//     /limits/<board>/<app>   Speicherlimits
//     /melden (POST)          Board meldet Hub-Version, Apps, Speicher
//     /kopplung               Code fuer die Kopplung mit einem Konto
//     /hochladen (POST)       lokale App ins Konto laden / zur Pruefung
//   Fuer Menschen:
//     /                       Portal: App-Galerie, Bestenlisten, Konto, Boards
//     /admin                  Verwaltung (Passwort = ADMIN_TOKEN)
//
// Umgebungsvariablen (Vercel -> Settings -> Environment Variables):
//   FIREBASE_DATABASE_URL     https://<projekt>-default-rtdb.<region>.firebasedatabase.app
//   FIREBASE_SERVICE_ACCOUNT  Inhalt der Dienstkonto-JSON (Firebase -> Projekteinstellungen
//                             -> Dienstkonten -> Neuen privaten Schluessel generieren)
//   ADMIN_TOKEN               Passwort fuer /admin (mind. 8 Zeichen)
//   HUB_TOKEN                 (optional) Passwort, das die Boards als "auth" mitschicken
//   GITHUB_REPO / GITHUB_BRANCH / GITHUB_TOKEN   (optional) Quelle des App-Stores
import { Fehler, koerper, koerperRoh, senden, ID, NAME, MAX_BODY } from "../lib/basis.js";
import { katalogFuer } from "../lib/store.js";
import { gesperrt, limitsFuer, melden, speicher, boardPruefen, kopplungFuerBoard, veraendertRegel } from "../lib/boards.js";
import { adminApi, anmelden, abmeldenCookie } from "../lib/admin.js";
import * as portal from "../lib/konten.js";
import { ADMIN_SEITE } from "../lib/admin-seite.js";
import { PORTAL_SEITE } from "../lib/portal-seite.js";
import { firmwareAktuell, firmwareRelease } from "../lib/firmware.js";
import { simulatorRoute } from "../lib/simulator.js";

const CORS = { "Access-Control-Allow-Origin": "*" };

async function boardRoute(req, res, url, p, methode) {
  if (process.env.HUB_TOKEN && url.searchParams.get("auth") !== process.env.HUB_TOKEN) throw new Fehler(401, "Permission denied");
  const board = url.searchParams.get("board") || "";
  if (!ID.test(board)) throw new Fehler(400, "board fehlt - Hub zu alt?");
  const sperre = await gesperrt(board);
  if (sperre) throw new Fehler(403, "Board gesperrt" + (sperre.grund ? ": " + sperre.grund : ""));
  const bekannt = await boardPruefen(board, url.searchParams.get("t") || "");
  if (!bekannt && p !== "melden") throw new Fehler(403, "Board noch nicht angemeldet");
  // Recovery must remain reachable for an authenticated board even if old firmware hashes differ.
  if (p === "firmware" && methode === "GET") return senden(res, 200, { firmware: await firmwareAktuell() });
  if (p.startsWith("firmware/") && methode === "GET") {
    const parts = p.split("/");
    const release = await firmwareRelease(parts[1]);
    const file = parts.length === 3 && release.inhalt.find((f) => f.name === parts[2]);
    if (!file) throw new Fehler(404, "Firmware-Datei unbekannt");
    return senden(res, 200, Buffer.from(file.daten, "base64"), "application/octet-stream");
  }
  if (bekannt && p !== "melden") {
    const regel = await veraendertRegel(board);
    if (regel === "sperren") throw new Fehler(403, "Hub veraendert - Board gesperrt (Original-Hub aufspielen)");
    if (regel === "lesen" && methode !== "GET") throw new Fehler(403, "Hub veraendert - nur Lesen erlaubt");
  }

  if (p === "apps" && methode === "GET") {
    return senden(res, 200, { apps: Object.values(await katalogFuer(board)).map((a) => a.eintrag) }, undefined, CORS);
  }
  if (p.startsWith("apps/") && methode === "GET") {
    const app = (await katalogFuer(board))[p.slice(5)];
    if (!app) throw new Fehler(404, "App unbekannt");
    const name = url.searchParams.get("datei");
    if (name) {
      const raw = app.dateien?.[name];
      if (!raw) throw new Fehler(404, "Projektdatei unbekannt");
      if (url.searchParams.get("paket") !== app.eintrag.paket) throw new Fehler(409, "App wurde aktualisiert; Katalog neu laden");
      return senden(res, 200, raw, "application/octet-stream", CORS);
    }
    return senden(res, 200, app.roh, "text/plain; charset=utf-8", CORS);
  }
  if (p === "melden" && methode === "POST") {
    return senden(res, 200, await melden(board, await koerper(req, 16384), bekannt), undefined, CORS);
  }
  if (p === "kopplung" && methode === "GET") {
    return senden(res, 200, await kopplungFuerBoard(board), undefined, CORS);
  }
  if (p === "hochladen" && methode === "POST") {
    const code = (await koerperRoh(req, 210 * 1024)).toString("utf8");
    return senden(res, 200, await portal.vomBoard(board, url.searchParams.get("ziel"), url.searchParams.get("datei") || "", code), undefined, CORS);
  }
  if (p.startsWith("limits/") && methode === "GET") {
    const [b, spiel] = p.slice(7).split("/");
    if (b !== board || !NAME.test(spiel || "")) throw new Fehler(400, "ungueltig");
    return senden(res, 200, await limitsFuer(board, spiel), undefined, CORS);
  }
  if (p.startsWith("esphub/") && p.endsWith(".json")) {
    const body = methode === "PUT" || methode === "PATCH" ? await koerper(req, MAX_BODY) : undefined;
    return senden(res, 200, await speicher(methode, p.slice(7, -5).split("/"), body, board), undefined, CORS);
  }
  throw new Fehler(404, "unbekannt");
}

export default async function handler(req, res) {
  const url = new URL(req.url, "http://x");
  const p = (url.searchParams.get("p") ?? url.pathname.replace(/^\/(api\/hub\/?)?/, "")).replace(/^\/+|\/+$/g, "");
  const methode = req.method;
  const mensch = p === "admin" || p.startsWith("admin/") || p === "" || p.startsWith("portal/");   // Browser, keine Boards
  try {
    if (methode === "OPTIONS" && !mensch) {
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type");
      res.statusCode = 204;
      return res.end();
    }
    if (p === "" && methode === "GET") return senden(res, 200, PORTAL_SEITE, "text/html; charset=utf-8", { "X-Frame-Options": "DENY" });
    if (p === "portal/galerie" && methode === "GET") return senden(res, 200, await portal.galerie());
    if (p.startsWith("portal/simulator/") && methode === "GET") return senden(res, 200, await simulatorRoute(req, p.slice(17), url), undefined, { "Access-Control-Allow-Origin": "*", "Vary": "Cookie" });
    if (p === "portal/registrieren" && methode === "POST") return senden(res, 200, { ok: true }, undefined, { "Set-Cookie": await portal.registrieren(req) });
    if (p === "portal/anmelden" && methode === "POST") return senden(res, 200, { ok: true }, undefined, { "Set-Cookie": await portal.anmelden(req) });
    if (p === "portal/abmelden" && methode === "POST") return senden(res, 200, { ok: true }, undefined, { "Set-Cookie": portal.abmelden });
    if (p.startsWith("portal/api/")) return senden(res, 200, await portal.portalApi(req, methode, p.slice(11)));
    if (p === "admin" || p.startsWith("admin/")) {
      const sicher = { "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer" };
      if (p === "admin" && methode === "GET") return senden(res, 200, ADMIN_SEITE, "text/html; charset=utf-8", sicher);
      if (p === "admin/login" && methode === "POST") return senden(res, 200, { ok: true }, undefined, { ...sicher, "Set-Cookie": await anmelden(req) });
      if (p === "admin/logout" && methode === "POST") return senden(res, 200, { ok: true }, undefined, { ...sicher, "Set-Cookie": abmeldenCookie });
      if (p.startsWith("admin/api/")) return senden(res, 200, await adminApi(req, methode, p.slice(10)), undefined, sicher);
      throw new Fehler(404, "unbekannt");
    }
    return await boardRoute(req, res, url, p, methode);
  } catch (e) {
    const code = e instanceof Fehler ? e.code : e instanceof SyntaxError ? 400 : 500;
    if (code === 500) console.error(e);
    return senden(res, code, { error: code === 500 ? "Serverfehler" : e.message }, undefined, mensch ? {} : CORS);
  }
}

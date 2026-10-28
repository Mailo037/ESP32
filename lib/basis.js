// Gemeinsames: Fehler, Pruefmuster, Firebase-Zugang (nur hier im Server).
import crypto from "node:crypto";

export const DB = (process.env.FIREBASE_DATABASE_URL || "").replace(/\/+$/, "");
export const ID = /^[0-9a-f]{12}$/;              // Board-ID = eFuse-MAC
export const NAME = /^[A-Za-z0-9_]{1,40}$/;      // Spiel / Liste / App
export const SCHLUESSEL = /^[A-Za-z0-9_-]{1,40}$/;
export const MAX_BODY = 4096;

export class Fehler extends Error {
  constructor(code, text) { super(text); this.code = code; }
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ------------------------------------------------------------------
//  Firebase per REST. Das OAuth-Token kommt aus dem Dienstkonto
//  (FIREBASE_SERVICE_ACCOUNT) und verlaesst diesen Server nie.
// ------------------------------------------------------------------
let token = { wert: "", bis: 0 };

const b64url = (x) => Buffer.from(x).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");

async function zugang() {
  if (process.env.FIREBASE_SECRET) return "auth=" + encodeURIComponent(process.env.FIREBASE_SECRET);
  if (token.bis > Date.now() + 60000) return "access_token=" + token.wert;
  let sa;
  try { sa = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || "null"); } catch { sa = null; }
  if (!sa || !sa.private_key || !sa.client_email) throw new Fehler(503, "FIREBASE_SERVICE_ACCOUNT fehlt oder ist ungueltig");
  const jetzt = Math.floor(Date.now() / 1000);
  const kopf = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const inhalt = b64url(JSON.stringify({
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/userinfo.email",
    aud: "https://oauth2.googleapis.com/token",
    iat: jetzt,
    exp: jetzt + 3600,
  }));
  const signatur = b64url(crypto.sign("RSA-SHA256", Buffer.from(kopf + "." + inhalt), sa.private_key));
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=" + kopf + "." + inhalt + "." + signatur,
  });
  if (!r.ok) throw new Fehler(502, "Google-Anmeldung fehlgeschlagen (" + r.status + ")");
  const d = await r.json();
  token = { wert: d.access_token, bis: Date.now() + d.expires_in * 1000 };
  return "access_token=" + token.wert;
}

export async function firebase(methode, pfad, daten, extra = "") {
  if (!DB) throw new Fehler(503, "FIREBASE_DATABASE_URL fehlt");
  const r = await fetch(`${DB}/${pfad}.json?${extra}${await zugang()}`, {
    method: methode,
    headers: { "Content-Type": "application/json" },
    body: daten === undefined ? undefined : JSON.stringify(daten),
  });
  const text = await r.text();
  // Fehlertext von Firebase nicht durchreichen - nur den Status
  if (!r.ok) throw new Fehler(502, "Firebase antwortet mit " + r.status);
  return text ? JSON.parse(text) : null;
}

export async function koerper(req, max = MAX_BODY) {
  if (req.body !== undefined && req.body !== null && !Buffer.isBuffer(req.body)) {
    const b = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    if (Buffer.byteLength(b) > max) throw new Fehler(413, "zu gross");
    return b ? JSON.parse(b) : null;
  }
  const teile = [];
  let n = 0;
  for await (const s of req) {
    n += s.length;
    if (n > max) throw new Fehler(413, "zu gross");
    teile.push(s);
  }
  const text = Buffer.concat(teile).toString("utf8");
  return text ? JSON.parse(text) : null;
}

export async function koerperRoh(req, max) {
  if (Buffer.isBuffer(req.body)) return req.body;
  if (typeof req.body === "string") return Buffer.from(req.body, "utf8");
  if (req.body && typeof req.body === "object") return Buffer.from(JSON.stringify(req.body));
  const teile = [];
  let n = 0;
  for await (const s of req) {
    n += s.length;
    if (n > max) throw new Fehler(413, "zu gross");
    teile.push(s);
  }
  return Buffer.concat(teile);
}

export function senden(res, code, inhalt, typ = "application/json; charset=utf-8", extraKopf = {}) {
  const body = Buffer.isBuffer(inhalt) ? inhalt : Buffer.from(typeof inhalt === "string" ? inhalt : JSON.stringify(inhalt));
  res.statusCode = code;
  res.setHeader("Content-Type", typ);
  res.setHeader("Content-Length", body.length);     // kein "chunked": das kann urequests nicht
  res.setHeader("Cache-Control", "no-store");
  for (const [k, v] of Object.entries(extraKopf)) res.setHeader(k, v);
  res.end(body);
}

// ------------------------------------------------------------------
//  Sitzungen (signierte Cookies) und Passwoerter
// ------------------------------------------------------------------
function geheim(zweck) {
  const p = process.env.ADMIN_TOKEN || "";
  if (p.length < 8) throw new Fehler(503, "ADMIN_TOKEN ist in Vercel nicht gesetzt (mind. 8 Zeichen)");
  return "esphub:" + zweck + ":" + p;
}

export function gleich(a, b) {
  const x = crypto.createHash("sha256").update(String(a)).digest();
  const y = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
}

const sig = (zweck, text) => crypto.createHmac("sha256", geheim(zweck)).update(text).digest("base64url");

export function sitzungCookie(name, wer, stunden) {
  const bis = Date.now() + stunden * 3600000;
  const wert = Buffer.from(JSON.stringify({ wer, bis })).toString("base64url");
  return `${name}=${wert}.${sig(name, wert)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${stunden * 3600}`;
}

export function sitzungLesen(req, name) {
  const m = new RegExp("(?:^|;\\s*)" + name + "=([^;]+)").exec(String(req.headers.cookie || ""));
  if (!m) return null;
  const [wert, s] = decodeURIComponent(m[1]).split(".");
  if (!wert || !s || !gleich(s, sig(name, wert))) return null;
  try {
    const d = JSON.parse(Buffer.from(wert, "base64url").toString("utf8"));
    return d.bis > Date.now() ? d.wer : null;
  } catch {
    return null;
  }
}

export const cookieLoeschen = (name) => `${name}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`;

export function passwortHash(pw, salz = crypto.randomBytes(16).toString("hex")) {
  return { salz, hash: crypto.scryptSync(String(pw), salz, 32).toString("hex") };
}

export function passwortPruefen(pw, gespeichert) {
  if (!gespeichert || !gespeichert.salz) return false;
  return gleich(passwortHash(pw, gespeichert.salz).hash, gespeichert.hash);
}

export const sha256 = (x) => crypto.createHash("sha256").update(String(x)).digest("hex");
export const zufall = (n) => crypto.randomBytes(n).toString("hex");
export const bremse = () => new Promise((r) => setTimeout(r, 700));

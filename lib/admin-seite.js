// Die Admin-Oberflaeche (eine Seite, ohne externe Skripte).
// Enthaelt keine Daten - alles kommt nach der Anmeldung von /admin/api.
import { UI_KOPF, UI_SYMBOLE, UI_SKRIPT } from "./ui.js";

export const ADMIN_SEITE = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#09090b">
<title>ESP-Hub Admin</title>
${UI_KOPF}
</head>
<body>
${UI_SYMBOLE}
<div id="login" class="mitte" hidden>
  <form id="login-form" class="karte formular anmelde-karte">
    <span class="mark"><svg class="ic"><use href="#i-chip"/></svg></span>
    <div><h1 style="font-size:22px">ESP-Hub Admin</h1>
    <p class="leise" style="margin:6px 0 0;font-size:14px">Nur für die Verwaltung. Das Passwort ist <code>ADMIN_TOKEN</code> aus Vercel.</p></div>
    <label class="etikett">Passwort<input class="feld" id="pw" type="password" autocomplete="current-password" required></label>
    <button class="btn" type="submit">Anmelden</button>
    <p id="login-fehler" class="fehlertext"></p>
  </form>
</div>

<div id="app" class="rahmen" hidden>
  <aside class="seite">
    <a class="logo" href="/admin"><span class="mark"><svg class="ic"><use href="#i-chip"/></svg></span>ESP-Hub <small>Admin</small></a>
    <nav class="nav" id="tabs">
      <button data-tab="uebersicht" class="an"><svg class="ic"><use href="#i-haus"/></svg>Übersicht</button>
      <button data-tab="boards"><svg class="ic"><use href="#i-chip"/></svg>Boards<span class="zahl" id="zahl-boards"></span></button>
      <button data-tab="apps"><svg class="ic"><use href="#i-grid"/></svg>Apps</button>
      <button data-tab="firmware"><svg class="ic"><use href="#i-firmware"/></svg>Firmware</button>
      <button data-tab="einreichungen"><svg class="ic"><use href="#i-eingang"/></svg>Einreichungen<span class="zahl ge" id="zahl-einr"></span></button>
      <button data-tab="konten"><svg class="ic"><use href="#i-leute"/></svg>Konten</button>
      <button data-tab="speicher"><svg class="ic"><use href="#i-speicher"/></svg>Speicher</button>
      <button data-tab="listen"><svg class="ic"><use href="#i-pokal"/></svg>Bestenlisten</button>
    </nav>
    <div class="unten">
      <nav class="nav"><a href="/"><svg class="ic"><use href="#i-grid"/></svg>Zum Portal<svg class="ic rechts" style="width:14px;height:14px"><use href="#i-ext"/></svg></a></nav>
      <div class="user"><span class="ava">A</span><span><b>Admin</b><small id="stand-zeit"></small></span>
        <button class="btn geist icon klein" id="neu-laden" title="Aktualisieren" aria-label="Aktualisieren"><svg class="ic"><use href="#i-neu"/></svg></button>
        <button class="btn geist icon klein" id="abmelden" title="Abmelden" aria-label="Abmelden"><svg class="ic"><use href="#i-raus"/></svg></button></div>
    </div>
  </aside>
  <main class="main">
    <section id="uebersicht"></section>
    <section id="boards" hidden></section>
    <section id="apps" hidden></section>
    <section id="firmware" hidden></section>
    <section id="einreichungen" hidden></section>
    <section id="konten" hidden></section>
    <section id="speicher" hidden></section>
    <section id="listen" hidden></section>
  </main>
</div>
${UI_SKRIPT}
<script>
"use strict";
var S = null;
var $ = function (s) { return document.querySelector(s); };
var meldung = UI.meldung;
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function kb(n) { n = +n || 0; return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : (n / 1024).toFixed(1) + " KB"; }
function vor(t) {
  if (!t) return "nie";
  var s = Math.round((Date.now() - t) / 1000);
  if (s < 90) return "gerade eben";
  if (s < 5400) return "vor " + Math.round(s / 60) + " min";
  if (s < 129600) return "vor " + Math.round(s / 3600) + " h";
  return "vor " + Math.round(s / 86400) + " Tagen";
}
function neuer(a, b) {
  var x = String(a || "").split(".").map(function (t) { return parseInt(t, 10) || 0; });
  var y = String(b || "").split(".").map(function (t) { return parseInt(t, 10) || 0; });
  for (var i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  return false;
}
async function api(methode, pfad, body) {
  var r = await fetch("/admin/api/" + pfad, {
    method: methode,
    headers: { "Content-Type": "application/json", "X-Hub-Admin": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  var d = await r.json().catch(function () { return {}; });
  if (r.status === 401) { zeigeLogin(); throw new Error("Bitte neu anmelden"); }
  if (!r.ok) throw new Error(d.error || ("Fehler " + r.status));
  return d;
}
function zeigeLogin() { $("#app").hidden = true; $("#login").hidden = false; $("#pw").focus(); }
function zeigeApp() { $("#login").hidden = true; $("#app").hidden = false; }
function kopf(titel, text, rechts) { return '<div class="kopf"><div><h1>' + titel + '</h1>' + (text ? '<p>' + text + '</p>' : "") + '</div>' + (rechts ? '<div class="kopf-rechts">' + rechts + '</div>' : "") + '</div>'; }
function leer(icon, titel, text) { return '<div class="leer">' + UI.icon(icon) + '<h3>' + titel + '</h3><p>' + text + '</p></div>'; }
function nr(b, id) { return b && b.nr != null ? "#" + String(b.nr).padStart(4, "0") : id; }

// ---------------------------------------------------------------- Anmelden
$("#login-form").addEventListener("submit", async function (e) {
  e.preventDefault();
  $("#login-fehler").textContent = "";
  var r = await fetch("/admin/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ passwort: $("#pw").value }), credentials: "same-origin" });
  var d = await r.json().catch(function () { return {}; });
  $("#pw").value = "";
  if (!r.ok) { $("#login-fehler").textContent = d.error || "Anmeldung fehlgeschlagen"; return; }
  await laden();
});
$("#abmelden").onclick = async function () { await fetch("/admin/logout", { method: "POST", credentials: "same-origin" }); S = null; zeigeLogin(); };
$("#neu-laden").onclick = async function () { await laden(); meldung("Aktualisiert"); };
$("#tabs").addEventListener("click", function (e) {
  var b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("an", x === b); });
  document.querySelectorAll(".main > section").forEach(function (s) { s.hidden = s.id !== b.dataset.tab; });
  window.scrollTo(0, 0);
});

async function laden() {
  try {
    S = await api("GET", "stand");
    zeigeApp();
    zeichnen();
  } catch (e) {
    if (S === null && /anmelden/i.test(e.message)) return;
    meldung(e.message, true);
  }
}

// ---------------------------------------------------------------- Auswertung
function belegtVon(id) { var b = S.belegt[id] || {}; return Object.keys(b).reduce(function (s, k) { return s + (+b[k] || 0); }, 0); }
function boardLimit(id) { return S.limits.boards[id] != null ? S.limits.boards[id] : S.limits.standard.board; }
function appNach(id) { for (var i = 0; i < S.apps.length; i++) if (S.apps[i].id === id) return S.apps[i]; return null; }
function boardIds() {
  var ids = {};
  Object.keys(S.boards).concat(Object.keys(S.belegt), Object.keys(S.gesperrt), Object.keys(S.limits.boards)).forEach(function (k) { ids[k] = 1; });
  return Object.keys(ids).sort(function (a, b) { return ((S.boards[b] || {}).zuletzt || 0) - ((S.boards[a] || {}).zuletzt || 0); });
}
function veraltet(info) {
  var n = 0, apps = (info && info.apps) || {};
  Object.keys(apps).forEach(function (k) { var a = appNach(k); if (a && neuer(a.version, apps[k])) n++; });
  return n;
}

function zeichnen() {
  $("#stand-zeit").textContent = "Stand " + new Date(S.zeit).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  $("#zahl-boards").textContent = boardIds().length || "";
  zeichneUebersicht(); zeichneBoards(); zeichneApps(); zeichneFirmware(); zeichneEinreichungen(); zeichneKonten(); zeichneSpeicher(); zeichneListen();
}

function zeichneUebersicht() {
  var ids = boardIds(), aktiv = 0, gesperrt = Object.keys(S.gesperrt).length, belegt = 0;
  ids.forEach(function (id) {
    var b = S.boards[id];
    if (b && b.zuletzt && Date.now() - b.zuletzt < 86400000) aktiv++;
    belegt += belegtVon(id);
  });
  var sichtbar = S.apps.filter(function (a) { return !a.versteckt; }).length;
  var offen = S.einreichungen.filter(function (e) { return e.status === "offen"; }).length;
  var h = kopf("Übersicht", "Zustand aller Boards, Apps und Konten auf einen Blick.") + '<div class="kacheln">' +
    '<div class="kachel"><span>Boards</span><b>' + ids.length + '</b><small>' + aktiv + ' in den letzten 24 h</small></div>' +
    '<div class="kachel"><span>Gesperrt</span><b>' + gesperrt + '</b><small>Boards ohne Online-Dienste</small></div>' +
    '<div class="kachel"><span>Apps im Store</span><b>' + sichtbar + '</b><small>' + (S.apps.length - sichtbar) + ' ausgeblendet</small></div>' +
    '<div class="kachel"><span>Online-Speicher</span><b>' + kb(belegt) + '</b><small>alle Boards zusammen</small></div>' +
    '<div class="kachel"><span>Konten</span><b>' + Object.keys(S.konten).length + '</b><small>registriert</small></div>' +
    '<div class="kachel"><span>Einreichungen offen</span><b>' + offen + '</b><small>' + (offen ? '<span class="pill ge">Prüfung nötig</span>' : "nichts zu tun") + '</small></div>' +
    '</div>';
  if (S.appsFehler) h += '<div class="hinweis">App-Store: ' + esc(S.appsFehler) + '</div>';
  h += '<div class="karte"><div class="karte-kopf"><h2>Zuletzt aktiv</h2></div>';
  if (ids.length) {
    h += '<div class="tabelle"><table><tr><th>Board</th><th>Zuletzt</th><th>Hub</th><th>Apps</th><th>Updates offen</th></tr>';
    ids.slice(0, 8).forEach(function (id) {
      var b = S.boards[id] || {}, v = veraltet(b);
      h += '<tr><td>' + boardName(id) + '</td><td class="leise">' + vor(b.zuletzt) + '</td><td><code>' + esc(b.hub || "–") + '</code></td><td>' + Object.keys(b.apps || {}).length + '</td><td>' + (v ? '<span class="pill ge">' + v + '</span>' : '<span class="leise">–</span>') + '</td></tr>';
    });
    h += '</table></div>';
  } else h += '<p class="leise" style="margin:0">Noch kein Board gemeldet. Boards melden sich beim nächsten Online-Abgleich.</p>';
  $("#uebersicht").innerHTML = h + '</div>';
}

function boardName(id) {
  var b = S.boards[id] || {};
  var an = b.zuletzt && Date.now() - b.zuletzt < 600000;
  return '<span class="status ' + (S.gesperrt[id] ? "rot" : an ? "an" : "") + '"></span><b style="font-weight:500">' + esc(nr(b, "Board")) + '</b><small><code>' + esc(id) + '</code></small>' +
    (b.konto ? '<small>Konto: ' + esc(b.konto) + '</small>' : "") +
    (b.veraendert ? '<span class="pill ge" title="' + esc([].concat(b.veraendert).join(", ")) + '" style="margin-top:4px">Hub verändert</span>' : b.veraendert === false ? '<span class="pill" style="margin-top:4px">Original-Hub</span>' : "");
}

function zeichneBoards() {
  var ids = boardIds();
  var h = kopf("Boards", "Gelb = Update verfügbar. Gesperrte Boards bekommen keinen Online-Speicher und keinen App-Store mehr.",
    '<button class="btn" data-limits-speichern>Limits speichern</button>');
  if (!ids.length) { $("#boards").innerHTML = h + leer("chip", "Noch keine Boards", "Boards erscheinen hier nach ihrem ersten Online-Abgleich."); return; }
  h += '<div class="karte"><div class="tabelle"><table style="min-width:980px"><tr><th>Board</th><th>Zuletzt</th><th>Hub</th><th>Installiert</th><th>Flash frei</th><th>Online belegt</th><th>Limit (Bytes)</th><th></th></tr>';
  ids.forEach(function (id) {
    var b = S.boards[id] || {}, sp = S.gesperrt[id], bel = belegtVon(id), lim = boardLimit(id);
    var apps = Object.keys(b.apps || {}).sort().map(function (k) {
      var a = appNach(k), alt = a && neuer(a.version, b.apps[k]);
      return '<span class="pill' + (alt ? " ge" : "") + '" title="' + (alt ? "Update auf " + esc(a.version) + " verfügbar" : "") + '" style="margin:2px 2px 2px 0">' + esc(k.replace(/_/g, " ")) + " " + esc(b.apps[k] || "?") + '</span>';
    }).join("") || '<span class="leise">–</span>';
    var pct = lim ? Math.min(100, bel * 100 / lim) : 0;
    h += '<tr class="' + (sp ? "gesperrt" : "") + '"><td>' + boardName(id) + (sp ? '<small style="color:var(--rt)">gesperrt' + (sp.grund ? ": " + esc(sp.grund) : "") + '</small>' : "") + '</td>' +
      '<td class="leise">' + vor(b.zuletzt) + (b.erstes ? '<small>seit ' + new Date(b.erstes).toLocaleDateString("de-DE") + '</small>' : "") + '</td>' +
      '<td><code>' + esc(b.hub || "–") + '</code></td><td style="max-width:260px">' + apps + '</td>' +
      '<td><code>' + (b.frei != null ? kb(b.frei) : "–") + '</code>' + (b.ram != null ? '<small>RAM ' + kb(b.ram) + '</small>' : "") + '</td>' +
      '<td><code>' + kb(bel) + '</code><div class="balken"><i class="' + (pct >= 90 ? "voll" : "") + '" style="width:' + pct + '%"></i></div></td>' +
      '<td><input class="feld zahl-feld" type="number" min="0" data-limit-board="' + esc(id) + '" value="' + (S.limits.boards[id] != null ? S.limits.boards[id] : "") + '" placeholder="' + S.limits.standard.board + '"></td>' +
      '<td><div class="aktionen">' +
      '<button class="btn zweit klein" data-sperren="' + esc(id) + '">' + (sp ? "Entsperren" : "Sperren") + '</button>' +
      '<button class="btn gefahr klein" data-daten-weg="' + esc(id) + '">Daten löschen</button>' +
      '<button class="btn gefahr klein" data-board-weg="' + esc(id) + '" title="Board vergessen inkl. Schlüssel - es meldet sich neu an">Zurücksetzen</button>' +
      '</div></td></tr>';
  });
  h += '</table></div><p class="fussnote">Leeres Limit = Standard aus dem Bereich Speicher.</p></div>';
  $("#boards").innerHTML = h;
}

function installiertAuf(id) {
  var n = 0, alt = 0, a = appNach(id);
  Object.keys(S.boards).forEach(function (b) {
    var v = (S.boards[b].apps || {})[id];
    if (v != null) { n++; if (a && neuer(a.version, v)) alt++; }
  });
  return n + (alt ? ' <span class="pill ge">' + alt + ' veraltet</span>' : "");
}

function zeichneApps() {
  var h = kopf("Apps", "Store-Inhalte aus GitHub und Uploads. Gleiche ID = neue Version, die Boards sehen dann das Update-Zeichen.",
    '<button class="btn zweit" data-limits-speichern>Limits speichern</button>');
  h += '<div class="karte"><div class="karte-kopf"><h2>App hochladen</h2>' +
    '<p>Eine <code>.zip</code> mit <code>main.py</code>, Modulen und Assets (max. 512 KB entpackt). Identische Hub-Treiber werden gemeinsam genutzt. Name, Version und Beschreibung kommen aus den Kopfzeilen <code># HUB-NAME:</code>, <code># HUB-VERSION:</code>, <code># HUB-INFO:</code>.</p></div>' +
    '<div class="zeile">' + UI.datei("upload-datei", "App-ZIP wählen") + '<input class="feld mono" id="upload-id" placeholder="App-ID (optional)" spellcheck="false"><button class="btn" id="upload-los">Hochladen</button></div></div>';
  h += '<div class="karte"><div class="tabelle"><table style="min-width:900px"><tr><th>App</th><th>Version</th><th>Quelle</th><th>Größe</th><th>Installiert auf</th><th>Limit/Board (Bytes)</th><th></th></tr>';
  S.apps.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (a) {
    h += '<tr' + (a.versteckt ? ' class="blass"' : "") + '><td>' + esc(a.name) + '<small><code>' + esc(a.id) + '</code></small>' + (a.info ? '<small>' + esc(a.info) + '</small>' : "") + '</td>' +
      '<td><code>' + esc(a.version || "–") + '</code></td>' +
      '<td>' + (a.quelle === "upload" ? '<span class="pill">Upload</span>' + (a.hochgeladen ? '<small>' + new Date(a.hochgeladen).toLocaleString("de-DE") + '</small>' : "") : '<span class="pill">GitHub</span>') + (a.versteckt ? '<small style="color:var(--ge)">ausgeblendet</small>' : "") + '</td>' +
      '<td class="leise">' + kb(a.groesse) + '</td><td>' + installiertAuf(a.id) + '</td>' +
      '<td><input class="feld zahl-feld" type="number" min="0" data-limit-app="' + esc(a.id) + '" value="' + (S.limits.apps[a.id] != null ? S.limits.apps[a.id] : "") + '" placeholder="' + S.limits.standard.app + '"></td>' +
      '<td><div class="aktionen"><button class="btn zweit klein" data-code="' + esc(a.id) + '">' + UI.icon("code") + 'Code</button>' +
      '<button class="btn zweit klein" data-verstecken="' + esc(a.id) + '" data-wert="' + (a.versteckt ? "0" : "1") + '">' + (a.versteckt ? "Einblenden" : "Ausblenden") + '</button>' +
      (a.quelle === "upload" ? '<button class="btn gefahr klein" data-app-weg="' + esc(a.id) + '">Löschen</button>' : "") +
      '</div></td></tr>';
  });
  h += '</table></div>' + (S.apps.length ? "" : '<p class="leise">Noch keine Apps.</p>') + '</div>';
  $("#apps").innerHTML = h;
  $("#upload-los").onclick = async function () {
    var f = $("#upload-datei").files[0];
    if (!f) { meldung("Erst eine Datei wählen", true); return; }
    this.disabled = true;
    try {
      var r = await api("POST", "apps", { id: $("#upload-id").value.trim(), dateiname: f.name, daten: await zipDaten(f) });
      meldung(r.name + " " + r.version + " hochgeladen");
      await laden();
    } catch (e) { meldung(e.message, true); } finally { this.disabled = false; }
  };
}

async function zipDaten(f) {
  if (!f.name.toLowerCase().endsWith(".zip")) throw new Error("Bitte eine ZIP-Datei wählen");
  if (f.size > 1024 * 1024) throw new Error("ZIP größer als 1 MB");
  var bytes = new Uint8Array(await f.arrayBuffer()), bin = "";
  for (var i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
  return btoa(bin);
}
function zeichneFirmware() {
  var fw = S.firmware || {}, active = fw.aktiv;
  var h = kopf("Firmware", "Firmware-ZIP hochladen und danach bewusst veröffentlichen. Online-Boards erhalten den Update-Bildschirm, offline bleiben sie nutzbar.",
    '<span class="pill ' + (active ? "gr punkt" : "") + '">Aktiv: ' + esc(active ? active.version : "kein Release") + '</span>');
  h += '<div class="karte"><div class="karte-kopf"><h2>Release erstellen</h2></div><div class="formular">' +
    '<div class="zeile"><label class="etikett" style="width:12em">Version<input class="feld mono" id="fw-version" placeholder="z. B. 2.1.1" spellcheck="false"></label>' + UI.datei("fw-datei", "Firmware-ZIP wählen") + '</div>' +
    '<label class="etikett">Versionshinweise<textarea class="feld" id="fw-notizen" placeholder="Was ist neu?" maxlength="2000"></textarea></label>' +
    '<div><button id="fw-upload" class="btn">Release erstellen</button></div></div></div>';
  var rel = (fw.releases || []).slice().sort(function (a, b) { return neuer(a.version, b.version) ? -1 : 1; });
  h += '<div class="karte"><div class="karte-kopf"><h2>Releases</h2></div>';
  if (rel.length) {
    h += '<div class="tabelle"><table><tr><th>Version</th><th>Hinweise</th><th>Größe</th><th style="text-align:right">Status</th></tr>';
    rel.forEach(function (r) {
      h += '<tr><td><code style="color:var(--tx)">' + esc(r.version) + '</code></td><td style="white-space:pre-wrap" class="leise">' + esc(r.notizen) + '</td><td class="leise">' + kb(r.groesse) + '</td><td><div class="aktionen">' +
        (active && active.id === r.id ? '<span class="pill gr punkt">Aktiv</span>' : (!active || neuer(r.version, active.version) ? '<button class="btn klein" data-fw="' + esc(r.id) + '">Veröffentlichen</button>' : '<span class="pill">Archiv</span>')) + '</div></td></tr>';
    });
    h += '</table></div>';
  } else h += '<p class="leise" style="margin:0">Noch keine Releases.</p>';
  $("#firmware").innerHTML = h + '</div>';
  $("#fw-upload").onclick = async function () {
    var f = $("#fw-datei").files[0];
    if (!f) { meldung("Firmware-ZIP wählen", true); return; }
    this.disabled = true;
    try {
      var r = await api("POST", "firmware", { version: $("#fw-version").value.trim(), notizen: $("#fw-notizen").value, dateiname: f.name, daten: await zipDaten(f) });
      meldung("Firmware " + r.version + " erstellt. Noch nicht veröffentlicht.");
      await laden();
    } catch (e) { meldung(e.message, true); } finally { this.disabled = false; }
  };
  $("#firmware").querySelectorAll("[data-fw]").forEach(function (button) {
    button.onclick = async function () {
      if (!await UI.frage({ titel: "Firmware veröffentlichen?", text: "Alle Online-Boards bekommen beim nächsten Abgleich den Update-Bildschirm.", ok: "Veröffentlichen" })) return;
      this.disabled = true;
      try { await api("POST", "firmware/" + this.dataset.fw + "/veroeffentlichen", {}); meldung("Firmware veröffentlicht"); await laden(); }
      catch (e) { meldung(e.message, true); } finally { this.disabled = false; }
    };
  });
}

function zeichneEinreichungen() {
  var offen = S.einreichungen.filter(function (e) { return e.status === "offen"; }).length;
  $("#zahl-einr").textContent = offen || "";
  var h = kopf("Einreichungen", "Annehmen = die App kommt in den Store. Gleiche ID ersetzt die alte Version, Boards sehen ein Update.");
  if (!S.einreichungen.length) { $("#einreichungen").innerHTML = h + leer("eingang", "Keine Einreichungen", "Neue Apps aus dem Portal landen hier zur Prüfung."); return; }
  h += '<div class="karte"><div class="tabelle"><table style="min-width:860px"><tr><th>App</th><th>Version</th><th>Von</th><th>Größe</th><th>Status</th><th>Wann</th><th></th></tr>';
  S.einreichungen.forEach(function (e) {
    var vorh = appNach(e.id), c = e.status === "angenommen" ? "gr" : e.status === "abgelehnt" ? "rt" : "ge";
    h += '<tr><td>' + esc(e.name) + '<small><code>' + esc(e.id) + '</code></small>' + (e.info ? '<small>' + esc(e.info) + '</small>' : "") + '</td>' +
      '<td><code>' + esc(e.version) + '</code>' + (vorh ? '<small>im Store: ' + esc(vorh.version) + '</small>' : "") + '</td>' +
      '<td>' + esc(e.konto) + '</td><td class="leise">' + kb(e.groesse) + '</td>' +
      '<td><span class="pill ' + c + '">' + esc(e.status) + '</span>' + (e.grund ? '<small>' + esc(e.grund) + '</small>' : "") + '</td><td class="leise">' + vor(e.zeit) + '</td>' +
      '<td><div class="aktionen"><button class="btn zweit klein" data-ecode="' + esc(e.sid) + '">' + UI.icon("code") + 'Code</button>' +
      (e.status === "offen" ? '<button class="btn klein" data-annehmen="' + esc(e.sid) + '">Annehmen</button><button class="btn gefahr klein" data-ablehnen="' + esc(e.sid) + '">Ablehnen</button>' : "") +
      '<button class="btn geist klein" data-einr-weg="' + esc(e.sid) + '">Löschen</button></div></td></tr>';
  });
  $("#einreichungen").innerHTML = h + '</table></div></div>';
}

function zeichneKonten() {
  var namen = Object.keys(S.konten).sort();
  var h = kopf("Konten", "Registrierte Portal-Konten und ihre gekoppelten Boards.");
  if (!namen.length) { $("#konten").innerHTML = h + leer("leute", "Noch keine Konten", "Konten entstehen über die Registrierung im Portal."); return; }
  h += '<div class="karte"><div class="tabelle"><table><tr><th>Name</th><th>Seit</th><th>Boards</th><th></th></tr>';
  namen.forEach(function (n) {
    var k = S.konten[n];
    h += '<tr' + (k.gesperrt ? ' class="gesperrt"' : "") + '><td><span class="ava" style="display:inline-grid;width:26px;height:26px;font-size:12px;margin-right:10px;vertical-align:middle">' + esc(n.charAt(0)) + '</span>' + esc(n) + (k.gesperrt ? ' <span class="pill rt">gesperrt</span>' : "") + '</td>' +
      '<td class="leise">' + (k.erstellt ? new Date(k.erstellt).toLocaleDateString("de-DE") : "–") + '</td>' +
      '<td>' + (k.boards.map(function (b) { return '<span class="pill mono" style="margin:2px 2px 2px 0">' + esc(nr(S.boards[b], b)) + '</span>'; }).join("") || '<span class="leise">–</span>') + '</td>' +
      '<td><div class="aktionen"><button class="btn zweit klein" data-konto-sperren="' + esc(n) + '" data-wert="' + (k.gesperrt ? "0" : "1") + '">' + (k.gesperrt ? "Entsperren" : "Sperren") + '</button>' +
      '<button class="btn gefahr klein" data-konto-weg="' + esc(n) + '">Löschen</button></div></td></tr>';
  });
  $("#konten").innerHTML = h + '</table></div></div>';
}

function zeichneSpeicher() {
  $("#speicher").innerHTML = kopf("Speicher", "Online-Speicher-Limits und der Umgang mit veränderten Hubs.") +
    '<div class="karte"><div class="karte-kopf"><h2>Standard-Limits</h2><p>Wie viel Online-Speicher ein Board nutzen darf. Ausnahmen für einzelne Boards und Apps trägst du in den Bereichen Boards und Apps ein (leer = Standard).</p></div>' +
    '<div class="zeile" style="align-items:flex-end"><label class="etikett">Pro App und Board (Bytes)<input class="feld zahl-feld" type="number" min="0" id="std-app" value="' + S.limits.standard.app + '"></label>' +
    '<label class="etikett">Pro Board gesamt (Bytes)<input class="feld zahl-feld" type="number" min="0" id="std-board" value="' + S.limits.standard.board + '"></label>' +
    '<button class="btn" data-limits-speichern>Alle Limits speichern</button></div></div>' +
    '<div class="karte"><div class="karte-kopf"><h2>Veränderte Hubs</h2><p>Jedes Board meldet Prüfsummen seiner Hub-Dateien; der Server vergleicht sie mit dem Original aus GitHub. Wer gezielt betrügt, kann die Prüfsummen fälschen – das erkennt also Basteleien, nicht jeden Betrug. Daten prüft der Server ohnehin selbst (Limits, eigene ID, Höchstpunkte).</p></div>' +
    '<div class="zeile">' + UI.auswahl("regel", [["erlauben", "Erlauben (nur markieren)"], ["lesen", "Nur lesen (kein Speichern, keine Bestenlisten)"], ["sperren", "Sperren"]], S.einstellungen.veraendert, "Regel für veränderte Hubs") +
    '<button class="btn zweit" id="regel-speichern">Speichern</button></div></div>';
  $("#regel-speichern").onclick = async function () {
    try { await api("PUT", "einstellungen", { veraendert: $(".regel").dataset.wert }); meldung("Gespeichert"); await laden(); } catch (e) { meldung(e.message, true); }
  };
}

async function limitsSpeichern() {
  var l = { standard: { app: +$("#std-app").value, board: +$("#std-board").value }, boards: {}, apps: {} };
  document.querySelectorAll("[data-limit-board]").forEach(function (i) { if (i.value !== "") l.boards[i.dataset.limitBoard] = +i.value; });
  document.querySelectorAll("[data-limit-app]").forEach(function (i) { if (i.value !== "") l.apps[i.dataset.limitApp] = +i.value; });
  try { await api("PUT", "limits", l); meldung("Limits gespeichert"); await laden(); } catch (e) { meldung(e.message, true); }
}

function zeichneListen() {
  var h = kopf("Bestenlisten", "Globale Werte, Bestenlisten und Höchstpunkte je Spiel."), karten = "";
  Object.keys(S.spiele).sort().forEach(function (s) {
    var sp = S.spiele[s];
    karten += '<div class="karte"><div class="karte-kopf"><h2>' + esc(s.replace(/_/g, " ")) + '</h2></div>';
    var g = Object.keys(sp.global || {});
    if (g.length) karten += '<div class="kv">' + g.map(function (k) { return '<div><span>' + esc(k) + '</span><b>' + esc(JSON.stringify(sp.global[k])) + '</b></div>'; }).join("") + '</div>';
    Object.keys(sp.listen || {}).sort().forEach(function (l) {
      var e = sp.listen[l] || {};
      var z = Object.keys(e).filter(function (b) { return e[b] && typeof e[b] === "object"; }).sort(function (a, b) { return e[b].p - e[a].p; });
      var mx = (S.hoechstpunkte[s] || {})[l];
      karten += '<div class="unterkopf"><span class="pill">' + esc(l) + '</span><span class="rechts zeile" style="gap:8px"><label class="leise" style="font-size:13px">Höchstpunkte</label><input class="feld zahl-feld" type="number" min="0" data-max="' + esc(s) + "/" + esc(l) + '" value="' + (mx != null ? mx : "") + '" placeholder="keine"><button class="btn zweit klein" data-max-speichern="' + esc(s) + "/" + esc(l) + '">Setzen</button></span></div>';
      if (!z.length) { karten += '<p class="leise" style="margin:8px 0 0;font-size:14px">Noch keine Einträge.</p>'; return; }
      karten += '<div class="tabelle"><table><tr><th>#</th><th>Name</th><th style="text-align:right">Punkte</th><th>Board</th><th>Wann</th><th></th></tr>';
      z.forEach(function (b, i) {
        karten += '<tr class="r' + (i + 1) + '"><td style="width:40px"><span class="rang">' + (i + 1) + '</span></td><td>' + esc(e[b].n) + '</td><td class="punkte">' + esc(e[b].p) + '</td><td><code>' + esc(b) + '</code></td><td class="leise">' + vor(e[b].t) + '</td>' +
          '<td><div class="aktionen"><button class="btn geist klein" data-eintrag-weg="' + esc(s) + "/" + esc(l) + "/" + esc(b) + '">Entfernen</button></div></td></tr>';
      });
      karten += '</table></div>';
    });
    karten += '</div>';
  });
  $("#listen").innerHTML = h + (karten || leer("pokal", "Noch keine Bestenlisten", "Sobald Boards online spielen, erscheinen hier die Listen."));
}

// ---------------------------------------------------------------- Aktionen
function wirklich(titel, text, ok) { return UI.frage({ titel: titel, text: text, ok: ok, gefahr: true }); }
document.addEventListener("click", async function (e) {
  var b = e.target.closest("button"); if (!b) return;
  var d = b.dataset;
  try {
    if (d.limitsSpeichern !== undefined) { await limitsSpeichern(); return; }
    else if (d.sperren) {
      var an = !S.gesperrt[d.sperren], grund = "";
      if (an) { grund = await UI.frage({ titel: "Board sperren", text: "Gesperrte Boards bekommen keinen Online-Speicher und keinen App-Store mehr.", eingabe: true, platzhalter: "Grund (optional)", ok: "Sperren" }); if (grund === null) return; }
      await api("POST", "board/" + d.sperren + "/sperren", { gesperrt: an, grund: grund });
      meldung(an ? "Board gesperrt" : "Board entsperrt");
    } else if (d.datenWeg) {
      if (!await wirklich("Daten löschen?", "Alle Online-Spielstände und Bestenlisten-Einträge dieses Boards werden gelöscht.", "Daten löschen")) return;
      await api("DELETE", "board/" + d.datenWeg + "?daten=1");
      meldung("Daten gelöscht");
    } else if (d.boardWeg) {
      if (!await wirklich("Board zurücksetzen?", "Es wird vergessen (inkl. Board-Schlüssel und Kopplung) und meldet sich beim nächsten Abgleich neu an. Spielstände bleiben.", "Zurücksetzen")) return;
      await api("DELETE", "board/" + d.boardWeg);
      meldung("Board entfernt");
    } else if (d.code) {
      var c = await api("GET", "apps/" + d.code + "/code");
      UI.frage({ titel: c.id + " · " + (c.quelle === "upload" ? "Upload" : "GitHub"), code: c.code });
      return;
    } else if (d.verstecken) {
      await api("POST", "apps/" + d.verstecken + "/versteckt", { versteckt: d.wert === "1" });
      meldung(d.wert === "1" ? "App ausgeblendet" : "App eingeblendet");
    } else if (d.appWeg) {
      if (!await wirklich("App löschen?", "Die hochgeladene App verschwindet aus dem Store. Installierte Kopien auf Boards bleiben.", "Löschen")) return;
      await api("DELETE", "apps/" + d.appWeg);
      meldung("App gelöscht");
    } else if (d.maxSpeichern) {
      var inp = document.querySelector('[data-max="' + d.maxSpeichern + '"]');
      await api("PUT", "hoechstpunkte/" + d.maxSpeichern, { max: inp.value === "" ? null : +inp.value });
      meldung("Höchstpunkte gespeichert – höhere Einträge werden ab jetzt abgelehnt");
    } else if (d.ecode) {
      var c2 = await api("GET", "einreichung/" + d.ecode + "/code");
      UI.frage({ titel: c2.id + " · " + c2.quelle, code: c2.code });
      return;
    } else if (d.annehmen) {
      if (!await UI.frage({ titel: "App annehmen?", text: "Die App kommt in den Store und ist für alle Boards sichtbar.", ok: "Annehmen" })) return;
      await api("POST", "einreichung/" + d.annehmen + "/annehmen");
      meldung("Angenommen – die App ist im Store");
    } else if (d.ablehnen) {
      var g = await UI.frage({ titel: "Einreichung ablehnen", text: "Den Grund sieht der Einreicher im Portal.", eingabe: true, platzhalter: "Grund", ok: "Ablehnen", gefahr: true });
      if (g === null) return;
      await api("POST", "einreichung/" + d.ablehnen + "/ablehnen", { grund: g });
      meldung("Abgelehnt");
    } else if (d.einrWeg) {
      if (!await wirklich("Einreichung löschen?", "Die Einreichung wird endgültig entfernt.", "Löschen")) return;
      await api("DELETE", "einreichung/" + d.einrWeg);
      meldung("Gelöscht");
    } else if (d.kontoSperren) {
      await api("POST", "konto/" + d.kontoSperren + "/sperren", { gesperrt: d.wert === "1" });
      meldung(d.wert === "1" ? "Konto gesperrt" : "Konto entsperrt");
    } else if (d.kontoWeg) {
      if (!await wirklich("Konto " + d.kontoWeg + " löschen?", "Gekoppelte Boards werden vom Konto gelöst.", "Konto löschen")) return;
      await api("DELETE", "konto/" + d.kontoWeg);
      meldung("Konto gelöscht");
    } else if (d.eintragWeg) {
      if (!await wirklich("Eintrag entfernen?", "Der Eintrag verschwindet aus der Bestenliste.", "Entfernen")) return;
      await api("DELETE", "listen/" + d.eintragWeg);
      meldung("Eintrag entfernt");
    } else {
      return;
    }
    await laden();
  } catch (err) { meldung(err.message, true); }
});

// Schon angemeldet? (Cookie noch gueltig)
api("GET", "stand").then(function (d) { S = d; zeigeApp(); zeichnen(); }).catch(function () { zeigeLogin(); });
</script>
</body>
</html>`;

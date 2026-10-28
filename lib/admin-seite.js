// Die Admin-Oberflaeche (eine Seite, ohne externe Skripte).
// Enthaelt keine Daten - alles kommt nach der Anmeldung von /admin/api.
export const ADMIN_SEITE = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>ESP-Hub Admin</title>
<style>
:root{--bg:#0d141c;--karte:#152030;--karte2:#1b2a3d;--linie:#26384d;--text:#e8f1ff;--leise:#8fa3b8;--blau:#4c9ef0;--gruen:#3fcf8e;--gelb:#f0b43c;--rot:#f06464}
*{box-sizing:border-box}
body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
button,input,select{font:inherit;color:inherit}
button{background:var(--karte2);border:1px solid var(--linie);border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{border-color:var(--blau)}
button.haupt{background:var(--blau);border-color:var(--blau);color:#fff}
button.gefahr{color:var(--rot)}
button.klein{padding:3px 8px;font-size:13px}
input{background:#0f1925;border:1px solid var(--linie);border-radius:8px;padding:7px 10px}
input[type=number]{width:7.5em}
code,pre{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.leise{color:var(--leise)}
#login{min-height:100vh;display:grid;place-items:center;padding:16px}
#login form{background:var(--karte);border:1px solid var(--linie);border-radius:14px;padding:28px;width:100%;max-width:340px;display:grid;gap:12px}
#login h1{margin:0;font-size:22px}
#app{display:none;max-width:1200px;margin:0 auto;padding:16px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
header h1{font-size:20px;margin:0;flex:1}
nav{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:16px;border-bottom:1px solid var(--linie)}
nav button{border:0;border-radius:8px 8px 0 0;background:none;padding:8px 14px;color:var(--leise)}
nav button.an{background:var(--karte);color:var(--text)}
.kacheln{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:16px}
.kachel{background:var(--karte);border:1px solid var(--linie);border-radius:12px;padding:12px 14px}
.kachel b{display:block;font-size:26px}
.karte{background:var(--karte);border:1px solid var(--linie);border-radius:12px;padding:14px;margin-bottom:14px;overflow-x:auto}
.karte h2{margin:0 0 10px;font-size:17px}
table{border-collapse:collapse;width:100%;min-width:640px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--linie);vertical-align:top}
th{color:var(--leise);font-weight:600;font-size:13px}
tr.gesperrt td{background:rgba(240,100,100,.08)}
.chip{display:inline-block;background:var(--karte2);border:1px solid var(--linie);border-radius:99px;padding:1px 8px;margin:1px 2px;font-size:12px;white-space:nowrap}
.chip.alt{border-color:var(--gelb);color:var(--gelb)}
.punkt{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--leise)}
.punkt.an{background:var(--gruen)}.punkt.rot{background:var(--rot)}
.aktionen{display:flex;gap:4px;flex-wrap:wrap}
#meldung{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--karte2);border:1px solid var(--linie);border-radius:10px;padding:10px 16px;display:none;max-width:calc(100% - 32px)}
#meldung.fehler{border-color:var(--rot)}
dialog{background:var(--karte);color:var(--text);border:1px solid var(--linie);border-radius:12px;width:min(900px,calc(100% - 32px));padding:0}
dialog pre{margin:0;padding:14px;max-height:70vh;overflow:auto;white-space:pre}
dialog header{padding:10px 14px;margin:0;border-bottom:1px solid var(--linie)}
.zeile{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.balken{height:6px;background:var(--karte2);border-radius:3px;overflow:hidden;margin-top:4px;min-width:80px}
.balken i{display:block;height:100%;background:var(--blau)}
.balken i.voll{background:var(--rot)}
</style>
</head>
<body>
<div id="login">
  <form id="login-form">
    <h1>ESP-Hub Admin</h1>
    <p class="leise" style="margin:0">Nur für die Verwaltung. Das Passwort ist <code>ADMIN_TOKEN</code> aus Vercel.</p>
    <input id="pw" type="password" placeholder="Passwort" autocomplete="current-password" required>
    <button class="haupt" type="submit">Anmelden</button>
    <p id="login-fehler" style="color:var(--rot);margin:0;min-height:1.4em"></p>
  </form>
</div>

<div id="app">
  <header>
    <h1>ESP-Hub Admin</h1>
    <span class="leise" id="stand-zeit"></span>
    <button id="neu-laden">Aktualisieren</button>
    <button id="abmelden">Abmelden</button>
  </header>
  <nav id="tabs">
    <button data-tab="uebersicht" class="an">Übersicht</button>
    <button data-tab="boards">Boards</button>
    <button data-tab="apps">Apps</button>
    <button data-tab="einreichungen" id="tab-einr">Einreichungen</button>
    <button data-tab="konten">Konten</button>
    <button data-tab="speicher">Speicher</button>
    <button data-tab="listen">Bestenlisten</button>
  </nav>
  <section id="uebersicht"></section>
  <section id="boards" hidden></section>
  <section id="apps" hidden></section>
  <section id="einreichungen" hidden></section>
  <section id="konten" hidden></section>
  <section id="speicher" hidden></section>
  <section id="listen" hidden></section>
</div>

<dialog id="code-dialog"><header class="zeile"><b id="code-titel" style="flex:1"></b><button id="code-zu">Schließen</button></header><pre id="code-text"></pre></dialog>
<div id="meldung"></div>

<script>
"use strict";
var S = null;
var $ = function (s) { return document.querySelector(s); };
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
function meldung(text, fehler) {
  var m = $("#meldung");
  m.textContent = text;
  m.className = fehler ? "fehler" : "";
  m.style.display = "block";
  clearTimeout(meldung.t);
  meldung.t = setTimeout(function () { m.style.display = "none"; }, 3500);
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
function zeigeLogin() { $("#app").style.display = "none"; $("#login").style.display = "grid"; $("#pw").focus(); }
function zeigeApp() { $("#login").style.display = "none"; $("#app").style.display = "block"; }

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
$("#neu-laden").onclick = function () { laden(); };
$("#tabs").addEventListener("click", function (e) {
  var b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("an", x === b); });
  document.querySelectorAll("#app > section").forEach(function (s) { s.hidden = s.id !== b.dataset.tab; });
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
  $("#stand-zeit").textContent = "Stand " + new Date(S.zeit).toLocaleTimeString("de-DE");
  zeichneUebersicht(); zeichneBoards(); zeichneApps(); zeichneEinreichungen(); zeichneKonten(); zeichneSpeicher(); zeichneListen();
}

function zeichneUebersicht() {
  var ids = boardIds(), aktiv = 0, gesperrt = Object.keys(S.gesperrt).length, belegt = 0, upd = [];
  ids.forEach(function (id) {
    var b = S.boards[id];
    if (b && b.zuletzt && Date.now() - b.zuletzt < 86400000) aktiv++;
    belegt += belegtVon(id);
    var v = veraltet(b); if (v) upd.push([id, v]);
  });
  var sichtbar = S.apps.filter(function (a) { return !a.versteckt; }).length;
  var h = '<div class="kacheln">' +
    '<div class="kachel"><span class="leise">Boards</span><b>' + ids.length + '</b><span class="leise">' + aktiv + ' in den letzten 24 h</span></div>' +
    '<div class="kachel"><span class="leise">Gesperrt</span><b>' + gesperrt + '</b></div>' +
    '<div class="kachel"><span class="leise">Apps im Store</span><b>' + sichtbar + '</b><span class="leise">' + (S.apps.length - sichtbar) + ' ausgeblendet</span></div>' +
    '<div class="kachel"><span class="leise">Online-Speicher</span><b>' + kb(belegt) + '</b><span class="leise">alle Boards zusammen</span></div>' +
    '<div class="kachel"><span class="leise">Konten</span><b>' + Object.keys(S.konten).length + '</b></div>' +
    '<div class="kachel"><span class="leise">Einreichungen offen</span><b>' + S.einreichungen.filter(function (e) { return e.status === "offen"; }).length + '</b></div>' +
    '</div>';
  if (S.appsFehler) h += '<div class="karte" style="border-color:var(--gelb)">App-Store: ' + esc(S.appsFehler) + '</div>';
  h += '<div class="karte"><h2>Zuletzt aktiv</h2><table><tr><th>Board</th><th>Zuletzt</th><th>Hub</th><th>Apps</th><th>Updates offen</th></tr>';
  ids.slice(0, 8).forEach(function (id) {
    var b = S.boards[id] || {};
    h += '<tr><td>' + boardName(id) + '</td><td>' + vor(b.zuletzt) + '</td><td>' + esc(b.hub || "–") + '</td><td>' + Object.keys(b.apps || {}).length + '</td><td>' + (veraltet(b) || "–") + '</td></tr>';
  });
  h += '</table>' + (ids.length ? "" : '<p class="leise">Noch kein Board gemeldet. Boards melden sich beim nächsten Online-Abgleich.</p>') + '</div>';
  $("#uebersicht").innerHTML = h;
}

function boardName(id) {
  var b = S.boards[id] || {};
  var an = b.zuletzt && Date.now() - b.zuletzt < 600000;
  return '<span class="punkt ' + (S.gesperrt[id] ? "rot" : an ? "an" : "") + '"></span><b>' + (b.nr != null ? "#" + String(b.nr).padStart(4, "0") : "Board") + '</b><br><code class="leise">' + esc(id) + '</code>' +
    (b.konto ? '<br><small>Konto: ' + esc(b.konto) + '</small>' : "") +
    (b.veraendert ? '<br><span class="chip alt" title="' + esc([].concat(b.veraendert).join(", ")) + '">Hub verändert</span>' : b.veraendert === false ? '<br><span class="chip">Original-Hub</span>' : "");
}

function zeichneBoards() {
  var h = '<div class="karte"><h2>Boards</h2><table><tr><th>Board</th><th>Zuletzt</th><th>Hub</th><th>Installiert</th><th>Flash frei</th><th>Online belegt</th><th>Limit (Bytes)</th><th>Aktionen</th></tr>';
  boardIds().forEach(function (id) {
    var b = S.boards[id] || {}, sp = S.gesperrt[id], bel = belegtVon(id), lim = boardLimit(id);
    var apps = Object.keys(b.apps || {}).sort().map(function (k) {
      var a = appNach(k), alt = a && neuer(a.version, b.apps[k]);
      return '<span class="chip' + (alt ? " alt" : "") + '" title="' + (alt ? "Update auf " + esc(a.version) + " verfügbar" : "") + '">' + esc(k.replace(/_/g, " ")) + " " + esc(b.apps[k] || "?") + '</span>';
    }).join("") || '<span class="leise">–</span>';
    var pct = lim ? Math.min(100, bel * 100 / lim) : 0;
    h += '<tr class="' + (sp ? "gesperrt" : "") + '"><td>' + boardName(id) + (sp ? '<br><small style="color:var(--rot)">gesperrt' + (sp.grund ? ": " + esc(sp.grund) : "") + '</small>' : "") + '</td>' +
      '<td>' + vor(b.zuletzt) + (b.erstes ? '<br><small class="leise">seit ' + new Date(b.erstes).toLocaleDateString("de-DE") + '</small>' : "") + '</td>' +
      '<td>' + esc(b.hub || "–") + '</td><td>' + apps + '</td>' +
      '<td>' + (b.frei != null ? kb(b.frei) : "–") + (b.ram != null ? '<br><small class="leise">RAM ' + kb(b.ram) + '</small>' : "") + '</td>' +
      '<td>' + kb(bel) + '<div class="balken"><i class="' + (pct >= 90 ? "voll" : "") + '" style="width:' + pct + '%"></i></div></td>' +
      '<td><input type="number" min="0" data-limit-board="' + esc(id) + '" value="' + (S.limits.boards[id] != null ? S.limits.boards[id] : "") + '" placeholder="' + S.limits.standard.board + '"></td>' +
      '<td><div class="aktionen">' +
      '<button class="klein" data-sperren="' + esc(id) + '">' + (sp ? "Entsperren" : "Sperren") + '</button>' +
      '<button class="klein gefahr" data-daten-weg="' + esc(id) + '">Daten löschen</button>' +
      '<button class="klein gefahr" data-board-weg="' + esc(id) + '" title="Board vergessen inkl. Schlüssel - es meldet sich neu an">Zurücksetzen</button>' +
      '</div></td></tr>';
  });
  h += '</table><p class="leise">Gelb = Update verfügbar. Gesperrte Boards bekommen keinen Online-Speicher und keinen App-Store mehr. Limits speicherst du im Tab <b>Speicher</b>.</p></div>';
  $("#boards").innerHTML = h;
}

function installiertAuf(id) {
  var n = 0, alt = 0, a = appNach(id);
  Object.keys(S.boards).forEach(function (b) {
    var v = (S.boards[b].apps || {})[id];
    if (v != null) { n++; if (a && neuer(a.version, v)) alt++; }
  });
  return n + (alt ? ' <span class="chip alt">' + alt + ' veraltet</span>' : "");
}

function zeichneApps() {
  var h = '<div class="karte"><h2>App hochladen</h2>' +
    '<p class="leise" style="margin-top:0">Eine <code>.py</code>-Datei (ein normales <code>main.py</code>). Name, Version und Beschreibung kommen aus den Kopfzeilen <code># HUB-NAME:</code>, <code># HUB-VERSION:</code>, <code># HUB-INFO:</code>. Gleiche ID = neue Version, die Boards sehen dann das Update-Zeichen.</p>' +
    '<div class="zeile"><input type="file" id="upload-datei" accept=".py,text/x-python,text/plain"><input id="upload-id" placeholder="App-ID (optional)"><button class="haupt" id="upload-los">Hochladen</button></div>' +
    '<p id="upload-vorschau" class="leise"></p></div>';
  h += '<div class="karte"><h2>Apps</h2><table><tr><th>App</th><th>Version</th><th>Quelle</th><th>Größe</th><th>Installiert auf</th><th>Limit/Board (Bytes)</th><th>Aktionen</th></tr>';
  S.apps.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (a) {
    h += '<tr' + (a.versteckt ? ' style="opacity:.55"' : "") + '><td><b>' + esc(a.name) + '</b><br><code class="leise">' + esc(a.id) + '</code>' + (a.info ? '<br><small class="leise">' + esc(a.info) + '</small>' : "") + '</td>' +
      '<td>' + esc(a.version || "–") + '</td>' +
      '<td>' + (a.quelle === "upload" ? "Upload" + (a.hochgeladen ? '<br><small class="leise">' + new Date(a.hochgeladen).toLocaleString("de-DE") + '</small>' : "") : "GitHub") + (a.versteckt ? '<br><small style="color:var(--gelb)">ausgeblendet</small>' : "") + '</td>' +
      '<td>' + kb(a.groesse) + '</td><td>' + installiertAuf(a.id) + '</td>' +
      '<td><input type="number" min="0" data-limit-app="' + esc(a.id) + '" value="' + (S.limits.apps[a.id] != null ? S.limits.apps[a.id] : "") + '" placeholder="' + S.limits.standard.app + '"></td>' +
      '<td><div class="aktionen"><button class="klein" data-code="' + esc(a.id) + '">Code</button>' +
      '<button class="klein" data-verstecken="' + esc(a.id) + '" data-wert="' + (a.versteckt ? "0" : "1") + '">' + (a.versteckt ? "Einblenden" : "Ausblenden") + '</button>' +
      (a.quelle === "upload" ? '<button class="klein gefahr" data-app-weg="' + esc(a.id) + '">Löschen</button>' : "") +
      '</div></td></tr>';
  });
  h += '</table></div>';
  $("#apps").innerHTML = h;
  $("#upload-datei").onchange = async function () {
    var f = this.files[0]; if (!f) return;
    var text = await f.text(), k = {};
    text.split("\\n").slice(0, 40).forEach(function (z) { var m = /^#\\s*HUB-(NAME|VERSION|INFO):\\s*(.*)$/.exec(z.trim()); if (m) k[m[1]] = m[2]; });
    if (!$("#upload-id").value) $("#upload-id").value = f.name.replace(/^gal_/, "").replace(/\\.py$/, "").replace(/[^A-Za-z0-9]/g, "_");
    $("#upload-vorschau").textContent = (k.NAME || f.name) + " · Version " + (k.VERSION || "1.0 (keine HUB-VERSION)") + " · " + kb(f.size) + (k.INFO ? " · " + k.INFO : "");
  };
  $("#upload-los").onclick = async function () {
    var f = $("#upload-datei").files[0];
    if (!f) { meldung("Erst eine Datei wählen", true); return; }
    try {
      var r = await api("POST", "apps", { id: $("#upload-id").value.trim(), code: await f.text() });
      meldung(r.name + " " + r.version + " hochgeladen");
      await laden();
    } catch (e) { meldung(e.message, true); }
  };
}

function zeichneEinreichungen() {
  var offen = S.einreichungen.filter(function (e) { return e.status === "offen"; }).length;
  $("#tab-einr").textContent = "Einreichungen" + (offen ? " (" + offen + ")" : "");
  var h = '<div class="karte"><h2>Eingereichte Apps</h2><p class="leise" style="margin-top:0">Annehmen = die App kommt in den Store (gleiche ID ersetzt die alte Version, Boards sehen ein Update).</p><table><tr><th>App</th><th>Version</th><th>Von</th><th>Größe</th><th>Status</th><th>Wann</th><th>Aktionen</th></tr>';
  S.einreichungen.forEach(function (e) {
    var vorh = appNach(e.id);
    h += '<tr><td><b>' + esc(e.name) + '</b><br><code class="leise">' + esc(e.id) + '</code>' + (e.info ? '<br><small class="leise">' + esc(e.info) + '</small>' : "") + '</td>' +
      '<td>' + esc(e.version) + (vorh ? '<br><small class="leise">im Store: ' + esc(vorh.version) + '</small>' : "") + '</td>' +
      '<td>' + esc(e.konto) + '</td><td>' + kb(e.groesse) + '</td>' +
      '<td>' + esc(e.status) + (e.grund ? '<br><small class="leise">' + esc(e.grund) + '</small>' : "") + '</td><td>' + vor(e.zeit) + '</td>' +
      '<td><div class="aktionen"><button class="klein" data-ecode="' + esc(e.sid) + '">Code</button>' +
      (e.status === "offen" ? '<button class="klein haupt" data-annehmen="' + esc(e.sid) + '">Annehmen</button><button class="klein gefahr" data-ablehnen="' + esc(e.sid) + '">Ablehnen</button>' : "") +
      '<button class="klein gefahr" data-einr-weg="' + esc(e.sid) + '">Löschen</button></div></td></tr>';
  });
  h += '</table>' + (S.einreichungen.length ? "" : '<p class="leise">Keine Einreichungen.</p>') + '</div>';
  $("#einreichungen").innerHTML = h;
}

function zeichneKonten() {
  var h = '<div class="karte"><h2>Konten</h2><table><tr><th>Name</th><th>Seit</th><th>Boards</th><th>Aktionen</th></tr>';
  Object.keys(S.konten).sort().forEach(function (n) {
    var k = S.konten[n];
    h += '<tr' + (k.gesperrt ? ' class="gesperrt"' : "") + '><td><b>' + esc(n) + '</b>' + (k.gesperrt ? ' <small style="color:var(--rot)">gesperrt</small>' : "") + '</td>' +
      '<td>' + (k.erstellt ? new Date(k.erstellt).toLocaleDateString("de-DE") : "–") + '</td>' +
      '<td>' + (k.boards.map(function (b) { var x = S.boards[b] || {}; return '<span class="chip">' + (x.nr != null ? "#" + String(x.nr).padStart(4, "0") : esc(b)) + '</span>'; }).join("") || '<span class="leise">–</span>') + '</td>' +
      '<td><div class="aktionen"><button class="klein" data-konto-sperren="' + esc(n) + '" data-wert="' + (k.gesperrt ? "0" : "1") + '">' + (k.gesperrt ? "Entsperren" : "Sperren") + '</button>' +
      '<button class="klein gefahr" data-konto-weg="' + esc(n) + '">Löschen</button></div></td></tr>';
  });
  h += '</table>' + (Object.keys(S.konten).length ? "" : '<p class="leise">Noch keine Konten.</p>') + '</div>';
  $("#konten").innerHTML = h;
}

function zeichneSpeicher() {
  $("#speicher").innerHTML = '<div class="karte"><h2>Standard-Limits</h2>' +
    '<p class="leise" style="margin-top:0">Wie viel Online-Speicher ein Board nutzen darf. Ausnahmen für einzelne Boards und Apps trägst du in den Tabs <b>Boards</b> und <b>Apps</b> ein (leer = Standard).</p>' +
    '<div class="zeile"><label>Pro App und Board <input type="number" min="0" id="std-app" value="' + S.limits.standard.app + '"> Bytes</label>' +
    '<label>Pro Board gesamt <input type="number" min="0" id="std-board" value="' + S.limits.standard.board + '"> Bytes</label></div>' +
    '<p><button class="haupt" id="limits-speichern">Alle Limits speichern</button></p></div>' +
    '<div class="karte"><h2>Veränderte Hubs</h2>' +
    '<p class="leise" style="margin-top:0">Jedes Board meldet Prüfsummen seiner Hub-Dateien; der Server vergleicht sie mit dem Original aus GitHub. Wer gezielt betrügt, kann die Prüfsummen fälschen - das erkennt also Basteleien, nicht jeden Betrug. Daten prüft der Server ohnehin selbst (Limits, eigene ID, Höchstpunkte).</p>' +
    '<div class="zeile"><select id="regel">' +
    [["erlauben", "Erlauben (nur markieren)"], ["lesen", "Nur lesen (kein Speichern, keine Bestenlisten)"], ["sperren", "Sperren"]].map(function (o) { return '<option value="' + o[0] + '"' + (S.einstellungen.veraendert === o[0] ? " selected" : "") + '>' + o[1] + '</option>'; }).join("") +
    '</select><button id="regel-speichern">Speichern</button></div></div>';
  $("#limits-speichern").onclick = limitsSpeichern;
  $("#regel-speichern").onclick = async function () {
    try { await api("PUT", "einstellungen", { veraendert: $("#regel").value }); meldung("Gespeichert"); await laden(); } catch (e) { meldung(e.message, true); }
  };
}

async function limitsSpeichern() {
  var l = { standard: { app: +$("#std-app").value, board: +$("#std-board").value }, boards: {}, apps: {} };
  document.querySelectorAll("[data-limit-board]").forEach(function (i) { if (i.value !== "") l.boards[i.dataset.limitBoard] = +i.value; });
  document.querySelectorAll("[data-limit-app]").forEach(function (i) { if (i.value !== "") l.apps[i.dataset.limitApp] = +i.value; });
  try { await api("PUT", "limits", l); meldung("Limits gespeichert"); await laden(); } catch (e) { meldung(e.message, true); }
}

function zeichneListen() {
  var h = "";
  Object.keys(S.spiele).sort().forEach(function (s) {
    var sp = S.spiele[s];
    h += '<div class="karte"><h2>' + esc(s.replace(/_/g, " ")) + '</h2>';
    var g = Object.keys(sp.global || {});
    if (g.length) h += '<p>' + g.map(function (k) { return esc(k) + ": <b>" + esc(JSON.stringify(sp.global[k])) + "</b>"; }).join(" · ") + '</p>';
    Object.keys(sp.listen || {}).sort().forEach(function (l) {
      var e = sp.listen[l] || {};
      var z = Object.keys(e).filter(function (b) { return e[b] && typeof e[b] === "object"; }).sort(function (a, b) { return e[b].p - e[a].p; });
      var mx = (S.hoechstpunkte[s] || {})[l];
      h += '<div class="zeile" style="margin:12px 0 6px"><h3 style="font-size:15px;margin:0;flex:1">' + esc(l) + '</h3><label class="leise">Höchstpunkte <input type="number" min="0" data-max="' + esc(s) + "/" + esc(l) + '" value="' + (mx != null ? mx : "") + '" placeholder="keine"></label><button class="klein" data-max-speichern="' + esc(s) + "/" + esc(l) + '">Setzen</button></div>' +
        '<table><tr><th>#</th><th>Name</th><th>Punkte</th><th>Board</th><th>Wann</th><th></th></tr>';
      z.forEach(function (b, i) {
        h += '<tr><td>' + (i + 1) + '</td><td>' + esc(e[b].n) + '</td><td><b>' + esc(e[b].p) + '</b></td><td><code class="leise">' + esc(b) + '</code></td><td>' + vor(e[b].t) + '</td>' +
          '<td><button class="klein gefahr" data-eintrag-weg="' + esc(s) + "/" + esc(l) + "/" + esc(b) + '">Entfernen</button></td></tr>';
      });
      h += '</table>';
    });
    h += '</div>';
  });
  $("#listen").innerHTML = h || '<div class="karte leise">Noch keine Bestenlisten.</div>';
}

// ---------------------------------------------------------------- Aktionen
document.addEventListener("click", async function (e) {
  var b = e.target.closest("button"); if (!b) return;
  var d = b.dataset;
  try {
    if (d.sperren) {
      var an = !S.gesperrt[d.sperren], grund = "";
      if (an) { grund = prompt("Board sperren - Grund (optional):", ""); if (grund === null) return; }
      await api("POST", "board/" + d.sperren + "/sperren", { gesperrt: an, grund: grund });
      meldung(an ? "Board gesperrt" : "Board entsperrt");
    } else if (d.datenWeg) {
      if (!confirm("Alle Online-Spielstände und Bestenlisten-Einträge dieses Boards löschen?")) return;
      await api("DELETE", "board/" + d.datenWeg + "?daten=1");
      meldung("Daten gelöscht");
    } else if (d.boardWeg) {
      if (!confirm("Board zurücksetzen? Es wird vergessen (inkl. Board-Schlüssel und Kopplung) und meldet sich beim nächsten Abgleich neu an. Spielstände bleiben.")) return;
      await api("DELETE", "board/" + d.boardWeg);
      meldung("Board entfernt");
    } else if (d.code) {
      var c = await api("GET", "apps/" + d.code + "/code");
      $("#code-titel").textContent = c.id + " (" + (c.quelle === "upload" ? "Upload" : "GitHub") + ")";
      $("#code-text").textContent = c.code;
      $("#code-dialog").showModal();
      return;
    } else if (d.verstecken) {
      await api("POST", "apps/" + d.verstecken + "/versteckt", { versteckt: d.wert === "1" });
      meldung(d.wert === "1" ? "App ausgeblendet" : "App eingeblendet");
    } else if (d.appWeg) {
      if (!confirm("Hochgeladene App löschen? Installierte Kopien auf Boards bleiben.")) return;
      await api("DELETE", "apps/" + d.appWeg);
      meldung("App gelöscht");
    } else if (d.maxSpeichern) {
      var inp = document.querySelector('[data-max="' + d.maxSpeichern + '"]');
      await api("PUT", "hoechstpunkte/" + d.maxSpeichern, { max: inp.value === "" ? null : +inp.value });
      meldung("Höchstpunkte gespeichert - höhere Einträge werden ab jetzt abgelehnt");
    } else if (d.ecode) {
      var c2 = await api("GET", "einreichung/" + d.ecode + "/code");
      $("#code-titel").textContent = c2.id + " (" + c2.quelle + ")";
      $("#code-text").textContent = c2.code;
      $("#code-dialog").showModal();
      return;
    } else if (d.annehmen) {
      if (!confirm("App annehmen und in den Store stellen?")) return;
      await api("POST", "einreichung/" + d.annehmen + "/annehmen");
      meldung("Angenommen - die App ist im Store");
    } else if (d.ablehnen) {
      var g = prompt("Grund für die Ablehnung (sieht der Einreicher):", "");
      if (g === null) return;
      await api("POST", "einreichung/" + d.ablehnen + "/ablehnen", { grund: g });
      meldung("Abgelehnt");
    } else if (d.einrWeg) {
      if (!confirm("Einreichung löschen?")) return;
      await api("DELETE", "einreichung/" + d.einrWeg);
      meldung("Gelöscht");
    } else if (d.kontoSperren) {
      await api("POST", "konto/" + d.kontoSperren + "/sperren", { gesperrt: d.wert === "1" });
      meldung(d.wert === "1" ? "Konto gesperrt" : "Konto entsperrt");
    } else if (d.kontoWeg) {
      if (!confirm("Konto " + d.kontoWeg + " löschen? Gekoppelte Boards werden gelöst.")) return;
      await api("DELETE", "konto/" + d.kontoWeg);
      meldung("Konto gelöscht");
    } else if (d.eintragWeg) {
      if (!confirm("Eintrag aus der Bestenliste entfernen?")) return;
      await api("DELETE", "listen/" + d.eintragWeg);
      meldung("Eintrag entfernt");
    } else {
      return;
    }
    await laden();
  } catch (err) { meldung(err.message, true); }
});
$("#code-zu").onclick = function () { $("#code-dialog").close(); };

// Schon angemeldet? (Cookie noch gueltig)
api("GET", "stand").then(function (d) { S = d; zeigeApp(); zeichnen(); }).catch(function () { zeigeLogin(); });
</script>
</body>
</html>`;

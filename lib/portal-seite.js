// Das oeffentliche Portal: App-Galerie, Bestenlisten, Konto und eigene Boards.
// Die Seite selbst enthaelt keine Daten - alles kommt ueber /portal/...
export const PORTAL_SEITE = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP-Hub</title>
<style>
:root{--bg:#0d141c;--karte:#152030;--karte2:#1b2a3d;--linie:#26384d;--text:#e8f1ff;--leise:#8fa3b8;--blau:#4c9ef0;--gruen:#3fcf8e;--gelb:#f0b43c;--rot:#f06464}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
button,input,select{font:inherit;color:inherit}
button{background:var(--karte2);border:1px solid var(--linie);border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{border-color:var(--blau)}
button.haupt{background:var(--blau);border-color:var(--blau);color:#fff}
button.gefahr{color:var(--rot)}
button.klein{padding:3px 8px;font-size:13px}
input,select{background:#0f1925;border:1px solid var(--linie);border-radius:8px;padding:7px 10px}
code{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.leise{color:var(--leise)}
.seite{max-width:1100px;margin:0 auto;padding:16px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}
header h1{font-size:22px;margin:0;flex:1}
nav{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:16px;border-bottom:1px solid var(--linie)}
nav button{border:0;border-radius:8px 8px 0 0;background:none;padding:8px 14px;color:var(--leise)}
nav button.an{background:var(--karte);color:var(--text)}
.raster{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.karte{background:var(--karte);border:1px solid var(--linie);border-radius:12px;padding:14px;margin-bottom:14px;overflow-x:auto}
.karte h2,.karte h3{margin:0 0 6px;font-size:17px}
.app .kopf{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.chip{display:inline-block;background:var(--karte2);border:1px solid var(--linie);border-radius:99px;padding:1px 8px;margin:1px 2px;font-size:12px;white-space:nowrap}
.chip.alt{border-color:var(--gelb);color:var(--gelb)}
.chip.gruen{border-color:var(--gruen);color:var(--gruen)}
.chip.rot{border-color:var(--rot);color:var(--rot)}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--linie);vertical-align:top}
th{color:var(--leise);font-weight:600;font-size:13px}
.zeile{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.formular{display:grid;gap:10px;max-width:360px}
#meldung{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--karte2);border:1px solid var(--linie);border-radius:10px;padding:10px 16px;display:none;max-width:calc(100% - 32px)}
#meldung.fehler{border-color:var(--rot)}
.code{font:700 34px ui-monospace,Consolas,monospace;letter-spacing:.2em}
</style>
</head>
<body>
<div class="seite">
  <header>
    <h1>ESP-Hub</h1>
    <span id="wer" class="leise"></span>
    <button id="abmelden" hidden>Abmelden</button>
  </header>
  <nav id="tabs">
    <button data-tab="galerie" class="an">App-Galerie</button>
    <button data-tab="listen">Bestenlisten</button>
    <button data-tab="boards">Meine Boards</button>
    <button data-tab="apps">Meine Apps</button>
    <button data-tab="konto" id="tab-konto">Anmelden</button>
  </nav>
  <section id="galerie"></section>
  <section id="listen" hidden></section>
  <section id="boards" hidden></section>
  <section id="apps" hidden></section>
  <section id="konto" hidden>
    <div class="raster">
      <form class="karte formular" id="f-anmelden"><h2>Anmelden</h2>
        <input name="name" placeholder="Name" autocomplete="username" required>
        <input name="passwort" type="password" placeholder="Passwort" autocomplete="current-password" required>
        <button class="haupt">Anmelden</button></form>
      <form class="karte formular" id="f-registrieren"><h2>Neues Konto</h2>
        <input name="name" placeholder="Name (a-z, 0-9, _ -)" autocomplete="username" required>
        <input name="passwort" type="password" placeholder="Passwort (mind. 8 Zeichen)" autocomplete="new-password" required minlength="8">
        <button class="haupt">Konto anlegen</button></form>
    </div>
  </section>
</div>
<div id="meldung"></div>

<script>
"use strict";
var G = null, ICH = null;
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
  m.textContent = text; m.className = fehler ? "fehler" : ""; m.style.display = "block";
  clearTimeout(meldung.t); meldung.t = setTimeout(function () { m.style.display = "none"; }, 4000);
}
async function anfrage(methode, pfad, body) {
  var r = await fetch(pfad, { method: methode, headers: { "Content-Type": "application/json", "X-Hub-Konto": "1" }, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin" });
  var d = await r.json().catch(function () { return {}; });
  if (!r.ok) { var e = new Error(d.error || ("Fehler " + r.status)); e.status = r.status; throw e; }
  return d;
}
function tab(name) {
  document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("an", x.dataset.tab === name); });
  document.querySelectorAll(".seite > section").forEach(function (s) { s.hidden = s.id !== name; });
}
$("#tabs").addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) tab(b.dataset.tab); });

// ---------------------------------------------------------------- Laden
async function laden() {
  try { G = await anfrage("GET", "/portal/galerie"); } catch (e) { meldung(e.message, true); G = { apps: [], listen: {} }; }
  try { ICH = await anfrage("GET", "/portal/api/ich"); } catch (e) { ICH = null; }
  $("#wer").textContent = ICH ? "Angemeldet als " + ICH.name : "";
  $("#abmelden").hidden = !ICH;
  $("#tab-konto").hidden = !!ICH;
  zeichneGalerie(); zeichneListen(); zeichneBoards(); zeichneApps();
}
function app(id) { for (var i = 0; i < G.apps.length; i++) if (G.apps[i].id === id) return G.apps[i]; if (ICH) for (var j = 0; j < ICH.privat.length; j++) if (ICH.privat[j].id === id) return ICH.privat[j]; return null; }
function boardWahl() {
  var ids = ICH ? Object.keys(ICH.boards) : [];
  if (!ids.length) return "";
  return '<select class="board-wahl">' + ids.map(function (id) { var b = ICH.boards[id]; return '<option value="' + esc(id) + '">' + (b.nr != null ? "#" + String(b.nr).padStart(4, "0") : esc(id)) + '</option>'; }).join("") + '</select>';
}

function zeichneGalerie() {
  var h = '<p class="leise">Alle freigegebenen Apps für den ESP-Hub. Mit einem gekoppelten Board kannst du sie von hier aus installieren - das Board holt sie beim nächsten Abgleich.</p><div class="raster">';
  G.apps.slice().sort(function (a, b) { return b.installs - a.installs || a.name.localeCompare(b.name); }).forEach(function (a) {
    h += '<div class="karte app"><div class="kopf"><h3>' + esc(a.name) + '</h3><span class="chip">v' + esc(a.version || "?") + '</span></div>' +
      '<p class="leise" style="margin:4px 0 10px">' + esc(a.info || "Keine Beschreibung") + '</p>' +
      '<p class="leise" style="margin:0 0 10px;font-size:13px">' + kb(a.groesse) + ' · auf ' + a.installs + ' Board' + (a.installs === 1 ? "" : "s") + '</p>' +
      (ICH && Object.keys(ICH.boards).length ? '<div class="zeile">' + boardWahl() + '<button class="klein haupt" data-install="' + esc(a.id) + '">Installieren</button></div>' : "") +
      '</div>';
  });
  h += '</div>';
  if (!G.apps.length) h = '<div class="karte leise">Noch keine Apps.</div>';
  $("#galerie").innerHTML = h;
}

function zeichneListen() {
  var h = "";
  Object.keys(G.listen).sort().forEach(function (s) {
    var ls = G.listen[s];
    if (!Object.keys(ls).length) return;
    h += '<div class="karte"><h2>' + esc(s.replace(/_/g, " ")) + '</h2>';
    Object.keys(ls).sort().forEach(function (l) {
      h += '<h3 style="font-size:15px;margin:10px 0 4px">' + esc(l) + '</h3><table><tr><th>#</th><th>Name</th><th>Punkte</th><th>Wann</th></tr>' +
        ls[l].map(function (e, i) { return '<tr><td>' + (i + 1) + '</td><td>' + esc(e.n) + '</td><td><b>' + esc(e.p) + '</b></td><td class="leise">' + vor(e.t) + '</td></tr>'; }).join("") + '</table>';
    });
    h += '</div>';
  });
  $("#listen").innerHTML = h || '<div class="karte leise">Noch keine Bestenlisten.</div>';
}

function nutzungChips(n) {
  if (!n) return '<span class="leise">?</span>';
  var c = [];
  if (n.hub) c.push('<span class="chip">Hub-Speicher</span>');
  if (n.web) c.push('<span class="chip">Internet</span>');
  if (n.funk) c.push('<span class="chip">Funk</span>');
  return c.join("") || '<span class="leise">keine Dienste</span>';
}

function zeichneBoards() {
  if (!ICH) { $("#boards").innerHTML = '<div class="karte">Bitte erst <a href="#" onclick="tab(\\'konto\\');return false" style="color:var(--blau)">anmelden</a>.</div>'; return; }
  var h = '<div class="karte"><h2>Board koppeln</h2>' +
    '<ol class="leise" style="margin-top:0"><li>Am Board: Galerie → <b>Board-Info</b>, dort steht die ID.</li><li>ID hier eingeben und „Code anfordern“.</li><li>Am Board: Board-Info → <b>Koppeln</b>. Das Board zeigt einen 6-stelligen Code.</li><li>Code hier eingeben.</li></ol>' +
    '<div class="zeile"><input id="k-board" placeholder="Board-ID (12 Zeichen)" maxlength="12" style="width:13em"><button id="k-start">Code anfordern</button>' +
    '<input id="k-code" placeholder="Code vom Display" maxlength="6" style="width:9em" inputmode="numeric"><button class="haupt" id="k-ok">Koppeln</button></div></div>';
  var ids = Object.keys(ICH.boards);
  ids.forEach(function (id) {
    var b = ICH.boards[id];
    h += '<div class="karte"><div class="zeile"><h2 style="flex:1">Board ' + (b.nr != null ? "#" + String(b.nr).padStart(4, "0") : "") + ' <code class="leise">' + esc(id) + '</code></h2>' +
      (b.gesperrt ? '<span class="chip rot">gesperrt</span>' : "") +
      '<span class="leise">zuletzt ' + vor(b.zuletzt) + ' · Hub ' + esc(b.hub || "?") + ' · Flash frei ' + (b.frei != null ? kb(b.frei) : "?") + '</span>' +
      '<button class="klein gefahr" data-entkoppeln="' + esc(id) + '">Entkoppeln</button></div>';
    h += '<table><tr><th>App</th><th>Version</th><th>Nutzt</th><th></th></tr>';
    Object.keys(b.apps || {}).sort().forEach(function (k) {
      var a = app(k), alt = a && neuer(a.version, b.apps[k]), weg = b.auftraege.deinstall.indexOf(k) >= 0;
      h += '<tr><td>' + esc(a ? a.name : k.replace(/_/g, " ")) + (a ? "" : ' <span class="chip">lokal</span>') + '</td>' +
        '<td>' + esc(b.apps[k] || "?") + (alt ? ' <span class="chip alt">Update ' + esc(a.version) + '</span>' : "") + '</td>' +
        '<td>' + nutzungChips((b.nutzung || {})[k]) + '</td><td><div class="zeile">' +
        (alt ? '<button class="klein" data-auftrag="install" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Updaten</button>' : "") +
        (weg ? '<span class="chip alt">wird entfernt</span> <button class="klein" data-zurueck="deinstall" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Abbrechen</button>'
          : '<button class="klein gefahr" data-auftrag="deinstall" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Deinstallieren</button>') +
        '</div></td></tr>';
    });
    b.auftraege.install.forEach(function (k) {
      if ((b.apps || {})[k] !== undefined) return;
      h += '<tr><td>' + esc((app(k) || { name: k }).name) + '</td><td colspan="2"><span class="chip gruen">wird installiert</span></td><td><button class="klein" data-zurueck="install" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Abbrechen</button></td></tr>';
    });
    h += '</table><p class="leise" style="margin-bottom:0">Aufträge holt das Board beim nächsten Abgleich (Spielstart, Spielende oder Board-Info → Jetzt abgleichen).</p></div>';
  });
  if (!ids.length) h += '<div class="karte leise">Noch kein Board gekoppelt.</div>';
  $("#boards").innerHTML = h;
  $("#k-start").onclick = async function () {
    try { var r = await anfrage("POST", "/portal/api/koppeln", { board: $("#k-board").value.trim() }); meldung("Jetzt am Board: Board-Info → Koppeln (gültig " + r.minuten + " min)"); } catch (e) { meldung(e.message, true); }
  };
  $("#k-ok").onclick = async function () {
    try { await anfrage("POST", "/portal/api/koppeln/bestaetigen", { board: $("#k-board").value.trim(), code: $("#k-code").value.trim() }); meldung("Board gekoppelt!"); await laden(); } catch (e) { meldung(e.message, true); }
  };
}

function zeichneApps() {
  if (!ICH) { $("#apps").innerHTML = '<div class="karte leise">Bitte erst anmelden.</div>'; return; }
  var h = '<div class="karte"><h2>App hochladen</h2>' +
    '<p class="leise" style="margin-top:0">Eine <code>.py</code>-Datei oder eine <code>.zip</code> mit <code>main.py</code>. Oben in die Datei: <code># HUB-NAME: Mein Spiel</code>, <code># HUB-VERSION: 1.0</code>, <code># HUB-INFO: kurze Beschreibung</code>.</p>' +
    '<div class="zeile"><input type="file" id="u-datei" accept=".py,.zip"><select id="u-ziel"><option value="privat">Privat (nur meine Boards, sofort)</option><option value="pruefung">Zur Prüfung (für alle, nach Freigabe)</option></select><button class="haupt" id="u-los">Hochladen</button></div></div>';
  h += '<div class="karte"><h2>Private Apps</h2><table><tr><th>App</th><th>Version</th><th>Größe</th><th></th></tr>' +
    (ICH.privat.map(function (a) {
      return '<tr><td><b>' + esc(a.name) + '</b><br><code class="leise">' + esc(a.id) + '</code></td><td>' + esc(a.version) + '</td><td>' + kb(a.groesse) + '</td><td><div class="zeile">' +
        boardWahl() + (Object.keys(ICH.boards).length ? '<button class="klein" data-install="' + esc(a.id) + '">Installieren</button>' : "") +
        '<button class="klein" data-pruefen="' + esc(a.id) + '">Zur Prüfung</button><button class="klein gefahr" data-privat-weg="' + esc(a.id) + '">Löschen</button></div></td></tr>';
    }).join("") || '<tr><td colspan="4" class="leise">Keine.</td></tr>') + '</table></div>';
  h += '<div class="karte"><h2>Eingereicht</h2><table><tr><th>App</th><th>Version</th><th>Status</th><th>Wann</th></tr>' +
    (ICH.einreichungen.map(function (e) {
      var c = e.status === "angenommen" ? "gruen" : e.status === "abgelehnt" ? "rot" : "alt";
      return '<tr><td>' + esc(e.name) + '</td><td>' + esc(e.version) + '</td><td><span class="chip ' + c + '">' + esc(e.status) + '</span>' + (e.grund ? '<br><small class="leise">' + esc(e.grund) + '</small>' : "") + '</td><td class="leise">' + vor(e.zeit) + '</td></tr>';
    }).join("") || '<tr><td colspan="4" class="leise">Noch nichts eingereicht.</td></tr>') + '</table></div>';
  $("#apps").innerHTML = h;
  $("#u-los").onclick = async function () {
    var f = $("#u-datei").files[0];
    if (!f) { meldung("Erst eine Datei wählen", true); return; }
    if (f.size > 400 * 1024) { meldung("Datei zu groß", true); return; }
    var bytes = new Uint8Array(await f.arrayBuffer()), bin = "";
    for (var i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
    try {
      var r = await anfrage("POST", "/portal/api/einreichen", { dateiname: f.name, daten: btoa(bin), ziel: $("#u-ziel").value });
      meldung(r.ziel === "privat" ? r.id + " " + r.version + " liegt in deinem Konto" : r.id + " " + r.version + " wartet auf Freigabe");
      await laden();
    } catch (e) { meldung(e.message, true); }
  };
}

// ---------------------------------------------------------------- Aktionen
document.addEventListener("click", async function (e) {
  var b = e.target.closest("button"); if (!b || !b.dataset) return;
  var d = b.dataset;
  try {
    if (d.install) {
      var sel = b.parentElement.querySelector(".board-wahl");
      if (!sel) return;
      await anfrage("POST", "/portal/api/board/" + sel.value + "/auftrag", { art: "install", app: d.install });
      meldung("Auftrag gespeichert - das Board installiert beim nächsten Abgleich");
    } else if (d.auftrag) {
      await anfrage("POST", "/portal/api/board/" + d.board + "/auftrag", { art: d.auftrag, app: d.app });
      meldung("Auftrag gespeichert");
    } else if (d.zurueck) {
      await anfrage("DELETE", "/portal/api/board/" + d.board + "/auftrag", { art: d.zurueck, app: d.app });
      meldung("Auftrag abgebrochen");
    } else if (d.entkoppeln) {
      if (!confirm("Board vom Konto lösen?")) return;
      await anfrage("POST", "/portal/api/board/" + d.entkoppeln + "/entkoppeln");
      meldung("Board entkoppelt");
    } else if (d.pruefen) {
      await anfrage("POST", "/portal/api/privat/" + d.pruefen + "/pruefen");
      meldung("Zur Prüfung eingereicht");
    } else if (d.privatWeg) {
      if (!confirm("Private App löschen? Installierte Kopien bleiben.")) return;
      await anfrage("DELETE", "/portal/api/privat/" + d.privatWeg);
      meldung("Gelöscht");
    } else return;
    await laden();
  } catch (err) { meldung(err.message, true); }
});

function formular(id, pfad) {
  $(id).addEventListener("submit", async function (e) {
    e.preventDefault();
    var f = new FormData(this);
    try {
      await anfrage("POST", pfad, { name: f.get("name"), passwort: f.get("passwort") });
      this.reset();
      await laden();
      tab("boards");
    } catch (err) { meldung(err.message, true); }
  });
}
formular("#f-anmelden", "/portal/anmelden");
formular("#f-registrieren", "/portal/registrieren");
$("#abmelden").onclick = async function () { await fetch("/portal/abmelden", { method: "POST", credentials: "same-origin" }); await laden(); tab("galerie"); };
laden();
</script>
</body>
</html>`;

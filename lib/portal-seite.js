// Das oeffentliche Portal: App-Galerie, Bestenlisten, Konto und eigene Boards.
// Die Seite selbst enthaelt keine Daten - alles kommt ueber /portal/...
import { UI_KOPF, UI_SYMBOLE, UI_SKRIPT } from "./ui.js";

export const PORTAL_SEITE = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP-Hub</title>
<meta name="theme-color" content="#09090b">
${UI_KOPF}
</head>
<body>
${UI_SYMBOLE}
<div class="rahmen">
  <aside class="seite">
    <a class="logo" href="/"><span class="mark"><svg class="ic"><use href="#i-chip"/></svg></span>ESP-Hub</a>
    <nav class="nav" id="tabs">
      <button data-tab="galerie" class="an"><svg class="ic"><use href="#i-grid"/></svg>App-Galerie</button>
      <button data-tab="listen"><svg class="ic"><use href="#i-pokal"/></svg>Bestenlisten</button>
      <button data-tab="boards"><svg class="ic"><use href="#i-chip"/></svg>Meine Boards<span class="zahl" id="zahl-boards"></span></button>
      <button data-tab="apps"><svg class="ic"><use href="#i-paket"/></svg>Meine Apps</button>
    </nav>
    <div class="unten">
      <nav class="nav"><a href="/simulator/"><svg class="ic"><use href="#i-play"/></svg>Simulator<svg class="ic rechts" style="width:14px;height:14px"><use href="#i-ext"/></svg></a></nav>
      <div class="user" id="user"></div>
    </div>
  </aside>

  <main class="main">
    <section id="galerie"></section>
    <section id="listen" hidden></section>
    <section id="boards" hidden></section>
    <section id="apps" hidden></section>
    <section id="konto" hidden>
      <div class="kopf"><div><h1>Anmelden</h1><p>Mit einem Konto koppelst du Boards, installierst Apps aus der Ferne und lädst eigene Projekte hoch.</p></div></div>
      <div class="zwei" style="max-width:760px">
        <form class="karte formular" id="f-anmelden"><h2>Anmelden</h2>
          <label class="etikett">Name<input class="feld" name="name" autocomplete="username" required></label>
          <label class="etikett">Passwort<input class="feld" name="passwort" type="password" autocomplete="current-password" required></label>
          <button class="btn">Anmelden</button></form>
        <form class="karte formular" id="f-registrieren"><h2>Neues Konto</h2>
          <label class="etikett">Name<input class="feld" name="name" placeholder="a-z, 0-9, _ -" autocomplete="username" required></label>
          <label class="etikett">Passwort<input class="feld" name="passwort" type="password" placeholder="mindestens 8 Zeichen" autocomplete="new-password" required minlength="8"></label>
          <button class="btn zweit">Konto anlegen</button></form>
      </div>
    </section>
  </main>
</div>
${UI_SKRIPT}
<script>
"use strict";
var G = null, ICH = null, SUCHE = "";
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
async function anfrage(methode, pfad, body) {
  var r = await fetch(pfad, { method: methode, headers: { "Content-Type": "application/json", "X-Hub-Konto": "1" }, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin" });
  var d = await r.json().catch(function () { return {}; });
  if (!r.ok) { var e = new Error(d.error || ("Fehler " + r.status)); e.status = r.status; throw e; }
  return d;
}
function tab(name) {
  document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("an", x.dataset.tab === name); });
  document.querySelectorAll(".main > section").forEach(function (s) { s.hidden = s.id !== name; });
  window.scrollTo(0, 0);
}
$("#tabs").addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) tab(b.dataset.tab); });
function kopf(titel, text, rechts) { return '<div class="kopf"><div><h1>' + titel + '</h1>' + (text ? '<p>' + text + '</p>' : "") + '</div>' + (rechts ? '<div class="kopf-rechts">' + rechts + '</div>' : "") + '</div>'; }
function leer(icon, titel, text, knopf) { return '<div class="leer">' + UI.icon(icon) + '<h3>' + titel + '</h3><p>' + text + '</p>' + (knopf || "") + '</div>'; }
var ANMELDEN = '<button class="btn" data-zu="konto">Anmelden</button>';
function nr(b, id) { return b && b.nr != null ? "#" + String(b.nr).padStart(4, "0") : id; }

// ---------------------------------------------------------------- Laden
async function laden() {
  try { G = await anfrage("GET", "/portal/galerie"); } catch (e) { meldung(e.message, true); G = { apps: [], listen: {} }; }
  try { ICH = await anfrage("GET", "/portal/api/ich"); } catch (e) { ICH = null; }
  var n = ICH ? Object.keys(ICH.boards).length : 0;
  $("#user").innerHTML = ICH
    ? '<span class="ava">' + esc(ICH.name.charAt(0)) + '</span><span><b>' + esc(ICH.name) + '</b><small>' + n + ' Board' + (n === 1 ? "" : "s") + ' gekoppelt</small></span><button class="btn geist icon klein" id="abmelden" title="Abmelden" aria-label="Abmelden">' + UI.icon("raus") + '</button>'
    : '<button class="btn zweit" style="width:100%" data-zu="konto">' + UI.icon("person") + 'Anmelden</button>';
  $("#zahl-boards").textContent = n || "";
  if (ICH && !$("#konto").hidden) tab("boards");
  zeichneGalerie(); zeichneListen(); zeichneBoards(); zeichneApps();
}
function app(id) { for (var i = 0; i < G.apps.length; i++) if (G.apps[i].id === id) return G.apps[i]; if (ICH) for (var j = 0; j < ICH.privat.length; j++) if (ICH.privat[j].id === id) return ICH.privat[j]; return null; }
function boardWahl() {
  var ids = ICH ? Object.keys(ICH.boards) : [];
  if (!ids.length) return "";
  return UI.auswahl("board-wahl", ids.map(function (id) { return [id, "Board " + nr(ICH.boards[id], id)]; }), ids[0], "Board wählen");
}
// Vorschau im OLED-Format: bekannte Spiele bekommen ein Bild, sonst die Initialen
function vorschau(a) {
  var n = String(a.name || a.id).toLowerCase();
  var t = /pong/.test(n) ? "pong" : /dodge|space/.test(n) ? "dodge" : /dash/.test(n) ? "dash" : /3d|render|cube|würfel/.test(n) ? "cube" : "";
  if (t) return '<div class="bild"><svg viewBox="0 0 128 64"><use href="#t-' + t + '"/></svg></div>';
  var w = String(a.name || a.id).split(/[^A-Za-z0-9ÄÖÜäöü]+/).filter(Boolean);
  return '<div class="bild"><b>' + esc((w.length > 1 ? w[0].charAt(0) + w[1].charAt(0) : String(w[0] || "?").slice(0, 2)).toUpperCase()) + '</b></div>';
}

function zeichneGalerie() {
  var hatBoards = ICH && Object.keys(ICH.boards).length;
  var apps = G.apps.slice().sort(function (a, b) { return b.installs - a.installs || a.name.localeCompare(b.name); });
  var h = kopf("App-Galerie", "Alle freigegebenen Apps für den ESP-Hub. Mit einem gekoppelten Board installierst du sie von hier aus – das Board holt sie beim nächsten Abgleich.",
    '<label class="suche">' + UI.icon("suche") + '<input id="suche" placeholder="Apps suchen" value="' + esc(SUCHE) + '"><kbd>/</kbd></label>');
  if (!apps.length) { $("#galerie").innerHTML = h + leer("grid", "Noch keine Apps", "Sobald Apps freigegeben sind, erscheinen sie hier."); return; }
  h += '<div class="raster" id="app-raster">';
  apps.forEach(function (a) {
    h += '<article class="app" data-suche="' + esc((a.name + " " + (a.info || "")).toLowerCase()) + '">' + vorschau(a) +
      '<div class="inhalt"><div class="app-kopf"><h3>' + esc(a.name) + '</h3><span class="pill mono">v' + esc(a.version || "?") + '</span></div>' +
      '<p>' + esc(a.info || "Keine Beschreibung") + '</p>' +
      '<span class="meta">' + kb(a.groesse) + ' · ' + a.installs + ' Board' + (a.installs === 1 ? "" : "s") + '</span>' +
      (hatBoards ? '<div class="fuss">' + boardWahl() + '<button class="btn" data-install="' + esc(a.id) + '">Installieren</button></div>' : "") +
      '</div></article>';
  });
  h += '</div><div class="leer" id="keine-treffer" hidden>' + UI.icon("suche") + '<h3>Keine Treffer</h3><p>Keine App passt zu deiner Suche.</p></div>';
  if (!ICH) h += '<p class="fussnote">Zum Installieren <a href="#" data-zu="konto">anmelden</a> und ein Board koppeln.</p>';
  else if (!hatBoards) h += '<p class="fussnote">Zum Installieren erst unter <a href="#" data-zu="boards">Meine Boards</a> ein Board koppeln.</p>';
  $("#galerie").innerHTML = h;
  filtern();
}
function filtern() {
  var n = 0;
  document.querySelectorAll("#app-raster .app").forEach(function (k) { var an = !SUCHE || k.dataset.suche.indexOf(SUCHE.toLowerCase()) >= 0; k.hidden = !an; if (an) n++; });
  var kt = $("#keine-treffer"); if (kt) kt.hidden = n > 0;
}
document.addEventListener("input", function (e) { if (e.target.id === "suche") { SUCHE = e.target.value.trim(); filtern(); } });
document.addEventListener("keydown", function (e) {
  if (e.key === "/" && !/INPUT|TEXTAREA/.test(e.target.tagName) && !$("#galerie").hidden) { e.preventDefault(); $("#suche").focus(); }
});

function zeichneListen() {
  var h = kopf("Bestenlisten", "Die besten Ergebnisse aller Boards, live aus dem Online-Speicher."), karten = "";
  Object.keys(G.listen).sort().forEach(function (s) {
    var ls = G.listen[s];
    if (!Object.keys(ls).length) return;
    karten += '<div class="karte"><div class="karte-kopf"><h2>' + esc(s.replace(/_/g, " ")) + '</h2></div>';
    Object.keys(ls).sort().forEach(function (l) {
      karten += '<div class="unterkopf"><span class="pill">' + esc(l) + '</span></div><div class="tabelle"><table>' +
        ls[l].map(function (e, i) { return '<tr class="r' + (i + 1) + '"><td style="width:40px"><span class="rang">' + (i + 1) + '</span></td><td>' + esc(e.n) + '</td><td class="punkte">' + esc(e.p) + '</td><td class="wann">' + vor(e.t) + '</td></tr>'; }).join("") + '</table></div>';
    });
    karten += '</div>';
  });
  $("#listen").innerHTML = h + (karten ? '<div class="zwei">' + karten + '</div>' : leer("pokal", "Noch keine Bestenlisten", "Sobald jemand online spielt, erscheinen hier die Ergebnisse."));
}

function nutzungChips(n) {
  if (!n) return '<span class="leise">–</span>';
  var c = [];
  if (n.hub) c.push('<span class="pill">Hub-Speicher</span>');
  if (n.web) c.push('<span class="pill">Internet</span>');
  if (n.funk) c.push('<span class="pill">Funk</span>');
  return c.join(" ") || '<span class="leise">keine Dienste</span>';
}

function zeichneBoards() {
  var h = kopf("Meine Boards", "Gekoppelte Boards, ihre Apps und offene Aufträge.");
  if (!ICH) { $("#boards").innerHTML = h + leer("chip", "Nicht angemeldet", "Melde dich an, um Boards zu koppeln und Apps aus der Ferne zu installieren.", ANMELDEN); return; }
  h += '<div class="karte"><div class="karte-kopf"><h2>Board koppeln</h2></div>' +
    '<ol class="schritte"><li><span>Am Board: Galerie → <b>Board-Info</b>, dort steht die ID.</span></li><li><span>ID hier eingeben und <b>Code anfordern</b>.</span></li><li><span>Am Board: Board-Info → <b>Koppeln</b>. Das Board zeigt einen 6-stelligen Code.</span></li><li><span>Code hier eingeben und <b>Koppeln</b>.</span></li></ol>' +
    '<div class="zeile"><input class="feld mono" id="k-board" placeholder="Board-ID (12 Zeichen)" maxlength="12" style="width:15em" spellcheck="false"><button class="btn zweit" id="k-start">Code anfordern</button>' +
    '<input class="feld mono" id="k-code" placeholder="Code vom Display" maxlength="6" style="width:10em" inputmode="numeric"><button class="btn" id="k-ok">Koppeln</button></div></div>';
  var ids = Object.keys(ICH.boards);
  ids.forEach(function (id) {
    var b = ICH.boards[id], online = b.zuletzt && Date.now() - b.zuletzt < 600000;
    h += '<div class="karte"><div class="karte-kopf"><h2>Board ' + esc(nr(b, "")) + '</h2>' +
      (b.gesperrt ? '<span class="pill rt">Gesperrt</span>' : online ? '<span class="pill gr punkt">Online</span>' : '<span class="pill punkt">Offline</span>') +
      '<code>' + esc(id) + '</code><button class="btn gefahr klein rechts" data-entkoppeln="' + esc(id) + '">Entkoppeln</button></div>' +
      '<div class="kv"><div><span>Zuletzt gesehen</span><b>' + vor(b.zuletzt) + '</b></div><div><span>Hub-Version</span><b>' + esc(b.hub || "?") + '</b></div><div><span>Flash frei</span><b>' + (b.frei != null ? kb(b.frei) : "?") + '</b></div></div>';
    var zeilen = "";
    Object.keys(b.apps || {}).sort().forEach(function (k) {
      var a = app(k), alt = a && neuer(a.version, b.apps[k]), weg = b.auftraege.deinstall.indexOf(k) >= 0;
      zeilen += '<tr><td>' + esc(a ? a.name : k.replace(/_/g, " ")) + (a ? "" : ' <span class="pill">lokal</span>') + '</td>' +
        '<td><code>' + esc(b.apps[k] || "?") + '</code>' + (alt ? ' <span class="pill ge">Update ' + esc(a.version) + '</span>' : "") + '</td>' +
        '<td>' + nutzungChips((b.nutzung || {})[k]) + '</td><td><div class="aktionen">' +
        (alt ? '<button class="btn klein" data-auftrag="install" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Updaten</button>' : "") +
        (weg ? '<span class="pill ge">Wird entfernt</span><button class="btn zweit klein" data-zurueck="deinstall" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Abbrechen</button>'
          : '<button class="btn gefahr klein" data-auftrag="deinstall" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Deinstallieren</button>') +
        '</div></td></tr>';
    });
    b.auftraege.install.forEach(function (k) {
      if ((b.apps || {})[k] !== undefined) return;
      zeilen += '<tr><td>' + esc((app(k) || { name: k }).name) + '</td><td colspan="2"><span class="pill gr">Wird installiert …</span></td><td><div class="aktionen"><button class="btn zweit klein" data-zurueck="install" data-app="' + esc(k) + '" data-board="' + esc(id) + '">Abbrechen</button></div></td></tr>';
    });
    h += zeilen ? '<div class="tabelle"><table><tr><th>App</th><th>Version</th><th>Nutzt</th><th></th></tr>' + zeilen + '</table></div>' : '<p class="leise" style="margin:0">Noch keine Apps auf diesem Board.</p>';
    h += '<p class="fussnote">Aufträge holt das Board beim nächsten Abgleich (Spielstart, Spielende oder Board-Info → Jetzt abgleichen).</p></div>';
  });
  if (!ids.length) h += leer("chip", "Noch kein Board gekoppelt", "Folge den Schritten oben, um dein erstes Board mit dem Konto zu verbinden.");
  $("#boards").innerHTML = h;
  $("#k-start").onclick = async function () {
    try { var r = await anfrage("POST", "/portal/api/koppeln", { board: $("#k-board").value.trim() }); meldung("Jetzt am Board: Board-Info → Koppeln (gültig " + r.minuten + " min)"); } catch (e) { meldung(e.message, true); }
  };
  $("#k-ok").onclick = async function () {
    try { await anfrage("POST", "/portal/api/koppeln/bestaetigen", { board: $("#k-board").value.trim(), code: $("#k-code").value.trim() }); meldung("Board gekoppelt"); await laden(); } catch (e) { meldung(e.message, true); }
  };
}

function zeichneApps() {
  var h = kopf("Meine Apps", "Eigene Projekte hochladen, privat nutzen oder für alle einreichen.");
  if (!ICH) { $("#apps").innerHTML = h + leer("paket", "Nicht angemeldet", "Melde dich an, um eigene Apps hochzuladen.", ANMELDEN); return; }
  var hatBoards = Object.keys(ICH.boards).length;
  h += '<div class="karte"><div class="karte-kopf"><h2>App hochladen</h2><p>Eine <code>.zip</code> mit <code>main.py</code>, Modulen und Assets (max. 512 KB entpackt). Identische Hub-Treiber belegen keinen zusätzlichen App-Speicher. Oben in die Datei: <code># HUB-NAME: Mein Spiel</code>, <code># HUB-VERSION: 1.0</code>, <code># HUB-INFO: kurze Beschreibung</code>.</p></div>' +
    '<div class="zeile">' + UI.datei("u-datei", "ZIP-Datei wählen") +
    UI.auswahl("u-ziel", [["privat", "Privat – nur meine Boards, sofort"], ["pruefung", "Zur Prüfung – für alle, nach Freigabe"]], "privat", "Ziel") +
    '<button class="btn" id="u-los">Hochladen</button></div></div>';
  h += '<div class="karte"><div class="karte-kopf"><h2>Private Apps</h2></div>' + (ICH.privat.length ? '<div class="tabelle"><table><tr><th>App</th><th>Version</th><th>Größe</th><th></th></tr>' +
    ICH.privat.map(function (a) {
      return '<tr><td>' + esc(a.name) + '<small><code>' + esc(a.id) + '</code></small></td><td><code>' + esc(a.version) + '</code></td><td class="leise">' + kb(a.groesse) + '</td><td><div class="aktionen">' +
        (hatBoards ? boardWahl() + '<button class="btn klein" data-install="' + esc(a.id) + '">Installieren</button>' : "") +
        '<button class="btn zweit klein" data-pruefen="' + esc(a.id) + '">Zur Prüfung</button><button class="btn gefahr klein" data-privat-weg="' + esc(a.id) + '">Löschen</button></div></td></tr>';
    }).join("") + '</table></div>' : '<p class="leise" style="margin:0">Noch keine privaten Apps.</p>') + '</div>';
  h += '<div class="karte"><div class="karte-kopf"><h2>Eingereicht</h2></div>' + (ICH.einreichungen.length ? '<div class="tabelle"><table><tr><th>App</th><th>Version</th><th>Status</th><th style="text-align:right">Wann</th></tr>' +
    ICH.einreichungen.map(function (e) {
      var c = e.status === "angenommen" ? "gr" : e.status === "abgelehnt" ? "rt" : "ge";
      return '<tr><td>' + esc(e.name) + '</td><td><code>' + esc(e.version) + '</code></td><td><span class="pill ' + c + '">' + esc(e.status) + '</span>' + (e.grund ? '<small>' + esc(e.grund) + '</small>' : "") + '</td><td class="wann">' + vor(e.zeit) + '</td></tr>';
    }).join("") + '</table></div>' : '<p class="leise" style="margin:0">Noch nichts eingereicht.</p>') + '</div>';
  $("#apps").innerHTML = h;
  $("#u-los").onclick = async function () {
    var f = $("#u-datei").files[0];
    if (!f) { meldung("Erst eine Datei wählen", true); return; }
    if (!f.name.toLowerCase().endsWith(".zip")) { meldung("Bitte eine ZIP-Datei wählen", true); return; }
    if (f.size > 1024 * 1024) { meldung("Datei zu groß (max. 1 MB)", true); return; }
    var bytes = new Uint8Array(await f.arrayBuffer()), bin = "";
    for (var i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
    this.disabled = true;
    try {
      var r = await anfrage("POST", "/portal/api/einreichen", { dateiname: f.name, daten: btoa(bin), ziel: $(".u-ziel").dataset.wert });
      meldung(r.ziel === "privat" ? r.id + " " + r.version + " liegt in deinem Konto" : r.id + " " + r.version + " wartet auf Freigabe");
      await laden();
    } catch (e) { meldung(e.message, true); } finally { this.disabled = false; }
  };
}

// ---------------------------------------------------------------- Aktionen
document.addEventListener("click", async function (e) {
  var zu = e.target.closest("[data-zu]");
  if (zu) { e.preventDefault(); tab(zu.dataset.zu); return; }
  if (e.target.closest("#abmelden")) { await fetch("/portal/abmelden", { method: "POST", credentials: "same-origin" }); await laden(); tab("galerie"); meldung("Abgemeldet"); return; }
  var b = e.target.closest("button"); if (!b || !b.dataset) return;
  var d = b.dataset;
  try {
    if (d.install) {
      var sel = b.parentElement.querySelector(".board-wahl");
      if (!sel) return;
      await anfrage("POST", "/portal/api/board/" + sel.dataset.wert + "/auftrag", { art: "install", app: d.install });
      meldung("Auftrag gespeichert – das Board installiert beim nächsten Abgleich");
    } else if (d.auftrag) {
      await anfrage("POST", "/portal/api/board/" + d.board + "/auftrag", { art: d.auftrag, app: d.app });
      meldung("Auftrag gespeichert");
    } else if (d.zurueck) {
      await anfrage("DELETE", "/portal/api/board/" + d.board + "/auftrag", { art: d.zurueck, app: d.app });
      meldung("Auftrag abgebrochen");
    } else if (d.entkoppeln) {
      if (!await UI.frage({ titel: "Board entkoppeln?", text: "Das Board wird von deinem Konto gelöst. Installierte Apps bleiben auf dem Board.", ok: "Entkoppeln", gefahr: true })) return;
      await anfrage("POST", "/portal/api/board/" + d.entkoppeln + "/entkoppeln");
      meldung("Board entkoppelt");
    } else if (d.pruefen) {
      await anfrage("POST", "/portal/api/privat/" + d.pruefen + "/pruefen");
      meldung("Zur Prüfung eingereicht");
    } else if (d.privatWeg) {
      if (!await UI.frage({ titel: "Private App löschen?", text: "Installierte Kopien auf deinen Boards bleiben erhalten.", ok: "Löschen", gefahr: true })) return;
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
laden();
</script>
</body>
</html>`;

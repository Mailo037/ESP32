// Gemeinsames Aussehen fuer Portal und Admin ("Graphit", siehe design.md).
// Nur eigene Bedienelemente: Auswahl-Menue, Dialoge, Datei-Feld und Meldungen
// ersetzen <select>, confirm(), prompt() und den nativen Datei-Knopf.

export const UI_KOPF = `<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">
<style>
:root{color-scheme:dark;--bg:#09090b;--fl:#111113;--fl2:#18181b;--li:#232327;--li2:#1c1c20;--hov:#3a3a40;--tx:#fafafa;--tx2:#d4d4d8;--le:#8b8b94;
  --ak:#fafafa;--ak-tx:#09090b;--ak-hov:#e4e4e7;--ring:rgba(250,250,250,.22);--gr:#4ade80;--ge:#fbbf24;--rt:#f87171;--oled:#e4e4e7;--r:10px;
  --f:"Geist",system-ui,-apple-system,"Segoe UI",sans-serif;--fm:"Geist Mono",ui-monospace,Consolas,monospace}
*{box-sizing:border-box}
html{scrollbar-color:var(--li) transparent}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--li);border-radius:99px;border:2px solid var(--bg)}
::-webkit-scrollbar-track{background:transparent}
::selection{background:rgba(250,250,250,.18)}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 var(--f);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
button,input,textarea{font:inherit;color:inherit}
[hidden]{display:none!important}
.sym{position:absolute;width:0;height:0;overflow:hidden}
.ic{width:18px;height:18px;flex:none}
.leise{color:var(--le)}
code,pre{font-family:var(--fm);font-size:12.5px}
code{color:var(--le)}
p a,td a{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--hov)}

/* ---- Rahmen: Seitenleiste + Inhalt */
.rahmen{display:grid;grid-template-columns:244px minmax(0,1fr);min-height:100vh}
.seite{background:var(--bg);border-right:1px solid var(--li);padding:18px 12px;display:flex;flex-direction:column;gap:4px;position:sticky;top:0;height:100vh}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:17px;letter-spacing:-.01em;padding:4px 8px 20px}
.logo small{font-weight:500;color:var(--le);font-size:13px}
.mark{width:28px;height:28px;border-radius:8px;background:var(--ak);color:var(--ak-tx);display:grid;place-items:center;flex:none}
.mark .ic{width:16px;height:16px}
.nav{display:grid;gap:2px}
.nav button,.nav a{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;color:var(--le);font-weight:500;font-size:14.5px;cursor:pointer;transition:color .15s,background .15s}
.nav button:hover,.nav a:hover{color:var(--tx);background:var(--fl)}
.nav button.an{background:var(--fl2);color:var(--tx)}
.nav button:focus-visible,.nav a:focus-visible{box-shadow:0 0 0 2px var(--ring)}
.zahl{margin-left:auto;font:500 12px var(--fm);color:var(--le)}
.zahl.ge{color:var(--ge)}
.unten{margin-top:auto;display:grid;gap:4px}
.user{display:flex;gap:10px;align-items:center;padding:12px 4px 2px 10px;border-top:1px solid var(--li);margin-top:8px;font-size:14px;min-width:0}
.user>span:nth-child(2){flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.user small{display:block;color:var(--le);font-size:12.5px}
.ava{width:30px;height:30px;border-radius:50%;background:var(--fl2);border:1px solid var(--li);color:var(--tx2);display:grid;place-items:center;font-weight:600;font-size:13px;flex:none;text-transform:uppercase}
.main{padding:32px clamp(16px,3.2vw,44px) 100px;max-width:1240px;width:100%;min-width:0}

/* ---- Kopf, Karten, Raster */
.kopf{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:24px}
h1{font-weight:700;font-size:28px;line-height:1.2;letter-spacing:-.025em;margin:0}
.kopf p{margin:6px 0 0;color:var(--le);max-width:62ch}
.kopf-rechts{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
h2{font-weight:600;font-size:17px;letter-spacing:-.01em;margin:0}
h3{font-weight:600;font-size:15px;margin:0}
.karte{background:var(--fl);border:1px solid var(--li);border-radius:var(--r);padding:20px;margin-bottom:16px;min-width:0}
.karte-kopf{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.karte-kopf p{margin:0;color:var(--le);font-size:14px;flex-basis:100%}
.rechts{margin-left:auto}
.leer{border:1px dashed var(--li);border-radius:var(--r);padding:40px 20px;text-align:center;color:var(--le);margin-bottom:16px}
.leer .ic{width:26px;height:26px;margin-bottom:6px}
.leer h3{color:var(--tx);margin-bottom:4px}
.leer p{margin:0}
.leer .btn{margin-top:16px}
.raster{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.zwei{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px;align-items:start}
.unterkopf{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:22px 0 8px}
.unterkopf:first-of-type{margin-top:4px}

/* ---- App-Karte */
.app{background:var(--fl);border:1px solid var(--li);border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column;transition:border-color .15s}
.app:hover{border-color:var(--hov)}
.bild{background:#000;aspect-ratio:2/1;display:grid;place-items:center;padding:18px 24px;border-bottom:1px solid var(--li);color:var(--oled)}
.bild svg{width:100%;height:100%}
.bild b{font:500 30px var(--fm);letter-spacing:.12em}
.inhalt{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.app-kopf{display:flex;justify-content:space-between;align-items:center;gap:8px}
.app h3{font-size:16px;letter-spacing:-.01em}
.app p{margin:0;color:var(--le);font-size:14px}
.meta{font:400 12px var(--fm);color:var(--le)}
.fuss{display:flex;align-items:center;gap:8px;margin-top:auto;padding-top:12px}
.fuss .auswahl{flex:1}

/* ---- Pillen, Status */
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;line-height:1.5;border-radius:99px;padding:1px 9px;background:var(--fl2);border:1px solid var(--li);color:var(--tx2);white-space:nowrap;vertical-align:middle}
.pill.mono{font-family:var(--fm);font-size:11.5px}
.pill.gr{color:var(--gr);background:color-mix(in srgb,var(--gr) 10%,transparent);border-color:color-mix(in srgb,var(--gr) 22%,transparent)}
.pill.ge{color:var(--ge);background:color-mix(in srgb,var(--ge) 10%,transparent);border-color:color-mix(in srgb,var(--ge) 22%,transparent)}
.pill.rt{color:var(--rt);background:color-mix(in srgb,var(--rt) 10%,transparent);border-color:color-mix(in srgb,var(--rt) 22%,transparent)}
.pill.punkt::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.status{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--hov);margin-right:8px;vertical-align:middle;flex:none}
.status.an{background:var(--gr)}
.status.rot{background:var(--rt)}

/* ---- Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-size:14px;font-weight:500;line-height:1.4;background:var(--ak);color:var(--ak-tx);border:1px solid var(--ak);border-radius:7px;padding:7px 14px;cursor:pointer;white-space:nowrap;transition:background .15s,border-color .15s,color .15s}
.btn:hover{background:var(--ak-hov);border-color:var(--ak-hov)}
.btn.zweit{background:var(--fl2);color:var(--tx);border-color:var(--li)}
.btn.zweit:hover{border-color:var(--hov)}
.btn.geist{background:transparent;border-color:transparent;color:var(--le)}
.btn.geist:hover{background:var(--fl);color:var(--tx)}
.btn.gefahr{background:transparent;color:var(--rt);border-color:color-mix(in srgb,var(--rt) 30%,transparent)}
.btn.gefahr:hover{background:color-mix(in srgb,var(--rt) 10%,transparent)}
.btn.gefahr-voll{background:var(--rt);border-color:var(--rt);color:#1c0606}
.btn.gefahr-voll:hover{background:#fca5a5;border-color:#fca5a5}
.btn.klein{padding:4px 10px;font-size:13px}
.btn.icon{padding:7px}
.btn.icon.klein{padding:5px}
.btn .ic{width:16px;height:16px}
.btn:disabled{opacity:.5;cursor:wait}
.btn:focus-visible{outline:0;box-shadow:0 0 0 3px var(--ring)}

/* ---- Felder */
.feld{background:var(--bg);border:1px solid var(--li);border-radius:7px;padding:7px 11px;font-size:14px;line-height:1.45;color:var(--tx);outline:0;transition:border-color .15s,box-shadow .15s;min-width:0}
.feld::placeholder{color:var(--le)}
.feld:hover{border-color:var(--hov)}
.feld:focus{border-color:var(--hov);box-shadow:0 0 0 3px var(--ring)}
.feld.mono{font-family:var(--fm);font-size:13px}
.feld.zahl-feld{width:8.5em;font-family:var(--fm);font-size:13px}
textarea.feld{display:block;width:100%;min-height:96px;resize:vertical}
input[type=number]{-moz-appearance:textfield;appearance:textfield}
input[type=number]::-webkit-inner-spin-button,input[type=number]::-webkit-outer-spin-button{-webkit-appearance:none;margin:0}
input:-webkit-autofill{-webkit-box-shadow:0 0 0 40px var(--bg) inset;-webkit-text-fill-color:var(--tx)}
.etikett{display:grid;gap:6px;font-size:13px;color:var(--le);font-weight:500}
.formular{display:grid;gap:14px}
.zeile{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.suche{display:flex;align-items:center;gap:8px;background:var(--fl);border:1px solid var(--li);border-radius:8px;padding:0 10px 0 12px;width:min(300px,100%)}
.suche:hover{border-color:var(--hov)}
.suche:focus-within{border-color:var(--hov);box-shadow:0 0 0 3px var(--ring)}
.suche .ic{width:16px;height:16px;color:var(--le)}
.suche input{border:0;outline:0;padding:8px 0;background:none;flex:1;min-width:0;font-size:14px}
.suche input::placeholder{color:var(--le)}
.suche kbd{font:500 11px var(--fm);color:var(--le);border:1px solid var(--li);border-radius:5px;padding:1px 6px}

/* ---- Auswahl-Menue (statt <select>) */
.auswahl{position:relative;display:inline-block;min-width:0;vertical-align:middle}
.auswahl-knopf{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;background:var(--bg);border:1px solid var(--li);border-radius:7px;padding:7px 9px 7px 11px;font-size:14px;line-height:1.45;cursor:pointer;text-align:left;color:var(--tx);transition:border-color .15s,box-shadow .15s}
.auswahl-knopf span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.auswahl-knopf .ic{width:15px;height:15px;color:var(--le);transition:transform .15s}
.auswahl-knopf:hover{border-color:var(--hov)}
.auswahl-knopf:focus-visible,.auswahl.offen .auswahl-knopf{outline:0;border-color:var(--hov);box-shadow:0 0 0 3px var(--ring)}
.auswahl.offen .auswahl-knopf .ic{transform:rotate(180deg)}
.auswahl-liste{display:none;position:fixed;z-index:60;background:var(--fl2);border:1px solid var(--li);border-radius:9px;padding:4px;box-shadow:0 16px 40px rgba(0,0,0,.55);max-height:300px;overflow:auto;max-width:min(380px,calc(100vw - 16px))}
.auswahl.offen .auswahl-liste{display:grid;gap:1px}
.auswahl-liste button{all:unset;box-sizing:border-box;display:block;position:relative;padding:7px 12px 7px 30px;border-radius:6px;font-size:14px;cursor:pointer;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.auswahl-liste button:hover,.auswahl-liste button:focus{background:var(--li);color:var(--tx)}
.auswahl-liste button[aria-selected=true]{color:var(--tx)}
.auswahl-liste button[aria-selected=true]::before{content:"";position:absolute;left:11px;top:50%;width:8px;height:4px;border-left:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-75%) rotate(-45deg)}

/* ---- Datei-Feld (statt nativem Datei-Knopf) */
.datei{display:flex;align-items:center;gap:12px;border:1px dashed var(--hov);border-radius:var(--r);padding:14px 16px;cursor:pointer;background:var(--bg);transition:border-color .15s,background .15s;min-width:min(100%,260px);flex:1;position:relative}
.datei:hover,.datei.ziehen{border-color:var(--tx2);background:var(--fl2)}
.datei:focus-within{box-shadow:0 0 0 3px var(--ring)}
.datei input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
.datei .ic{width:22px;height:22px;color:var(--le)}
.datei.gewaehlt .ic{color:var(--gr)}
.datei b{display:block;font-weight:500;font-size:14px}
.datei small{display:block;color:var(--le);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ---- Tabellen und Werte */
.tabelle{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-weight:500;font-size:12.5px;color:var(--le);padding:0 10px 8px;border-bottom:1px solid var(--li);white-space:nowrap}
td{padding:11px 10px;border-bottom:1px solid var(--li2);vertical-align:middle}
tr:last-child td{border-bottom:0}
td small{display:block;color:var(--le);font-size:12.5px}
td.leise{color:var(--le)}
.aktionen{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
tr.gesperrt td{background:color-mix(in srgb,var(--rt) 6%,transparent)}
tr.blass td{opacity:.5}
.rang{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:7px;background:var(--fl2);color:var(--le);font:500 12px var(--fm)}
.r1 .rang{color:#fbbf24;background:rgba(251,191,36,.12)}
.r2 .rang{color:#d4d4d8;background:rgba(212,212,216,.1)}
.r3 .rang{color:#fb923c;background:rgba(251,146,60,.12)}
.punkte{text-align:right;font:500 14px var(--fm);white-space:nowrap;font-variant-numeric:tabular-nums}
.wann{color:var(--le);font-size:13px;white-space:nowrap;text-align:right}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;background:var(--li);border:1px solid var(--li);border-radius:8px;overflow:hidden;margin-bottom:18px}
.kv div{background:var(--fl);padding:10px 14px}
.kv span{display:block;font-size:12px;color:var(--le)}
.kv b{font:500 14.5px var(--fm)}
.kacheln{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:16px}
.kachel{background:var(--fl);border:1px solid var(--li);border-radius:var(--r);padding:16px 18px}
.kachel span{font-size:13px;color:var(--le)}
.kachel b{display:block;font-weight:600;font-size:28px;line-height:1.25;letter-spacing:-.02em;margin:6px 0 2px;font-variant-numeric:tabular-nums}
.kachel small{font-size:12.5px;color:var(--le)}
.balken{height:4px;background:var(--li);border-radius:99px;overflow:hidden;margin-top:6px;min-width:80px}
.balken i{display:block;height:100%;background:var(--tx2);border-radius:99px}
.balken i.voll{background:var(--rt)}
.schritte{margin:0 0 18px;padding:0;list-style:none;counter-reset:s;display:grid;gap:8px}
.schritte li{counter-increment:s;display:flex;gap:10px;align-items:flex-start;color:var(--le);font-size:14px}
.schritte li::before{content:counter(s);flex:none;width:22px;height:22px;border-radius:50%;border:1px solid var(--li);display:grid;place-items:center;font:500 11.5px var(--fm);color:var(--tx2)}
.schritte b{color:var(--tx);font-weight:500}
.hinweis{border:1px solid color-mix(in srgb,var(--ge) 30%,transparent);background:color-mix(in srgb,var(--ge) 7%,transparent);color:var(--tx2);border-radius:var(--r);padding:12px 16px;margin-bottom:16px;font-size:14px}
.fussnote{color:var(--le);font-size:13px;margin:14px 0 0}

/* ---- Meldung (Toast) */
#meldung{position:fixed;right:24px;bottom:24px;display:flex;gap:10px;align-items:center;background:var(--fl2);border:1px solid var(--li);border-radius:var(--r);padding:11px 16px;font-size:14px;box-shadow:0 12px 32px rgba(0,0,0,.5);max-width:min(460px,calc(100% - 32px));z-index:80;opacity:0;transform:translateY(8px);transition:opacity .2s,transform .2s;pointer-events:none}
#meldung.zeigen{opacity:1;transform:none}
#meldung .ic{color:var(--gr)}
#meldung.fehler .ic{color:var(--rt)}

/* ---- Dialog (statt confirm/prompt) */
.modal{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.62);display:grid;place-items:center;padding:16px;animation:ein .15s ease-out}
.modal-karte{background:var(--fl);border:1px solid var(--li);border-radius:12px;padding:22px;width:min(420px,100%);box-shadow:0 24px 60px rgba(0,0,0,.6);display:grid;gap:12px;max-height:calc(100vh - 32px);animation:hoch .15s ease-out}
.modal-karte.breit{width:min(940px,100%);grid-template-rows:auto minmax(0,1fr) auto}
.modal-karte p{margin:0;color:var(--le);font-size:14px}
.modal-aktionen{display:flex;justify-content:flex-end;gap:8px;margin-top:6px}
.code-box{margin:0;background:var(--bg);border:1px solid var(--li);border-radius:8px;padding:14px;overflow:auto;white-space:pre;color:var(--tx2);line-height:1.6;min-height:0}
@keyframes ein{from{opacity:0}}
@keyframes hoch{from{transform:translateY(6px) scale(.99)}}

/* ---- Anmeldung */
.mitte{min-height:100vh;display:grid;place-items:center;padding:16px}
.anmelde-karte{width:100%;max-width:360px;margin:0}
.anmelde-karte .mark{margin-bottom:6px}
.fehlertext{color:var(--rt);font-size:13.5px;margin:0;min-height:1.4em}

@media (max-width:860px){
  .rahmen{grid-template-columns:minmax(0,1fr)}
  .seite{position:sticky;top:0;z-index:20;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center;border-right:0;border-bottom:1px solid var(--li);padding:10px 16px;min-width:0}
  .logo{padding:0;margin-right:auto}
  .nav{display:flex;overflow-x:auto;width:100%;order:3;scrollbar-width:none}
  .nav button,.nav a{white-space:nowrap}
  .unten{margin:0;display:flex;align-items:center;gap:4px}
  .unten .nav{display:none}
  .user{border:0;margin:0;padding:0}
  .user>span:nth-child(2){display:none}
  .main{padding-top:24px}
  #meldung{left:16px;right:16px;max-width:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>`;

// Linien-Icons (24px, currentColor). Verwendung: <svg class="ic"><use href="#i-name"/></svg>
export const UI_SYMBOLE = `<svg class="sym" aria-hidden="true">
<symbol id="i-chip" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx=".6"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/></g></symbol>
<symbol id="i-grid" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></g></symbol>
<symbol id="i-pokal" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 16v5M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 6h3v1.5a3 3 0 0 1-3 3M7 6H4v1.5a3 3 0 0 0 3 3"/></g></symbol>
<symbol id="i-paket" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M20.5 7.5 12 3 3.5 7.5 12 12z"/><path d="M3.5 7.5v9L12 21l8.5-4.5v-9M12 12v9"/></g></symbol>
<symbol id="i-play" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M10 9v6l5-3z"/></g></symbol>
<symbol id="i-ext" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M9 7h8v8"/></g></symbol>
<symbol id="i-suche" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></g></symbol>
<symbol id="i-ok" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/></g></symbol>
<symbol id="i-fehler" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.01"/></g></symbol>
<symbol id="i-runter" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="i-hoch" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/></g></symbol>
<symbol id="i-raus" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15M10 16l4-4-4-4M14 12H4"/></g></symbol>
<symbol id="i-rein" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15M10 16l4-4-4-4M14 12H4"/></g></symbol>
<symbol id="i-neu" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/></g></symbol>
<symbol id="i-haus" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z"/></g></symbol>
<symbol id="i-firmware" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v11M7.5 9.5 12 14l4.5-4.5"/><rect x="3.5" y="16" width="17" height="5" rx="1.5"/><path d="M7 18.5h.01"/></g></symbol>
<symbol id="i-eingang" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3.5 13.5 6 5h12l2.5 8.5V19a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1z"/><path d="M3.5 13.5H8.5l1 2.5h5l1-2.5h5"/></g></symbol>
<symbol id="i-leute" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 5.2a3.5 3.5 0 0 1 0 6.6M18.5 14.5a6.5 6.5 0 0 1 3 5.5"/></g></symbol>
<symbol id="i-speicher" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></g></symbol>
<symbol id="i-person" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/></g></symbol>
<symbol id="i-code" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8.5 8-4 4 4 4M15.5 8l4 4-4 4"/></g></symbol>
<symbol id="t-dodge" viewBox="0 0 128 64"><g fill="currentColor"><path d="M10 25 27 32 10 39z"/><rect x="33" y="31" width="7" height="2"/><rect x="52" y="31" width="7" height="2"/><rect x="40" y="7" width="2" height="2"/><rect x="118" y="11" width="2" height="2"/><rect x="62" y="19" width="2" height="2"/><rect x="96" y="29" width="2" height="2"/><rect x="22" y="54" width="2" height="2"/><rect x="114" y="57" width="2" height="2"/><rect x="4" y="2" width="30" height="3"/></g><g fill="none" stroke="currentColor" stroke-width="2"><circle cx="86" cy="18" r="7"/><circle cx="104" cy="45" r="9"/><circle cx="72" cy="50" r="4"/><circle cx="17" cy="32" r="13" stroke-dasharray="3 3"/></g></symbol>
<symbol id="t-pong" viewBox="0 0 128 64"><g fill="currentColor"><rect x="6" y="16" width="3" height="16"/><rect x="119" y="30" width="3" height="16"/><rect x="76" y="24" width="4" height="4"/><rect x="69" y="27" width="3" height="3" opacity=".5"/><rect x="63" y="30" width="2" height="2" opacity=".3"/><rect x="48" y="4" width="6" height="2"/><rect x="52" y="4" width="2" height="8"/><rect x="74" y="4" width="6" height="2"/><rect x="74" y="4" width="2" height="4"/><rect x="74" y="7" width="6" height="2"/><rect x="78" y="7" width="2" height="5"/><rect x="74" y="11" width="6" height="2"/></g><line x1="64" y1="0" x2="64" y2="64" stroke="currentColor" stroke-width="2" stroke-dasharray="4 4"/></symbol>
<symbol id="t-dash" viewBox="0 0 128 64"><g fill="currentColor"><rect x="0" y="52" width="128" height="2"/><rect x="22" y="40" width="6" height="6"/><path d="M56 52 62 40 68 52zM68 52 74 40 80 52z"/><rect x="4" y="4" width="46" height="3"/></g><g fill="none" stroke="currentColor" stroke-width="2"><rect x="19" y="37" width="12" height="12"/><rect x="93" y="41" width="30" height="11"/><rect x="4" y="4" width="120" height="3" stroke-width="1"/></g></symbol>
<symbol id="t-cube" viewBox="0 0 128 64"><g fill="none" stroke="currentColor" stroke-width="1.6"><path d="M42 22h28v28H42zM58 10h28v28H58zM42 22l16-12M70 22l16-12M70 50l16-12M42 50l16-12"/></g><g fill="currentColor"><rect x="4" y="54" width="20" height="2"/><rect x="4" y="58" width="12" height="2"/></g></symbol>
</svg>
<div id="meldung" role="status" aria-live="polite"><svg class="ic"><use href="#i-ok"/></svg><span></span></div>`;

// Bedienelemente als globales UI-Objekt. Bewusst ES5 wie die Seiten selbst.
export const UI_SKRIPT = `<script>
"use strict";
var UI = (function () {
  var offen = null;
  function e(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function icon(name) { return '<svg class="ic"><use href="#i-' + name + '"/></svg>'; }

  // ---- Auswahl-Menue: UI.auswahl("klasse", [[wert, text], ...], wert) -> HTML; Wert steht in data-wert
  function auswahl(klasse, optionen, wert, label) {
    var akt = optionen.filter(function (o) { return String(o[0]) === String(wert); })[0] || optionen[0] || ["", ""];
    return '<div class="auswahl ' + e(klasse) + '" data-wert="' + e(akt[0]) + '"><button type="button" class="auswahl-knopf" aria-haspopup="listbox" aria-expanded="false"' + (label ? ' aria-label="' + e(label) + '"' : "") + '><span>' + e(akt[1]) + '</span>' + icon("runter") + '</button>' +
      '<div class="auswahl-liste" role="listbox">' + optionen.map(function (o) {
        return '<button type="button" role="option" data-w="' + e(o[0]) + '" aria-selected="' + (o[0] === akt[0]) + '">' + e(o[1]) + '</button>';
      }).join("") + '</div></div>';
  }
  function zu() {
    if (!offen) return;
    offen.classList.remove("offen");
    offen.querySelector(".auswahl-knopf").setAttribute("aria-expanded", "false");
    offen = null;
  }
  function auf(a) {
    zu();
    offen = a;
    a.classList.add("offen");
    var k = a.querySelector(".auswahl-knopf"), l = a.querySelector(".auswahl-liste"), r = k.getBoundingClientRect();
    k.setAttribute("aria-expanded", "true");
    l.style.minWidth = r.width + "px";
    l.style.left = Math.max(8, Math.min(r.left, innerWidth - l.offsetWidth - 8)) + "px";
    var oben = r.bottom + 6;
    if (oben + l.offsetHeight > innerHeight - 8 && r.top - 6 - l.offsetHeight > 8) oben = r.top - 6 - l.offsetHeight;
    l.style.top = oben + "px";
    var s = l.querySelector('[aria-selected="true"]') || l.querySelector("button");
    if (s) s.focus();
  }
  function setzen(a, w) {
    a.dataset.wert = w;
    a.querySelectorAll(".auswahl-liste button").forEach(function (b) {
      var an = b.dataset.w === w;
      b.setAttribute("aria-selected", an);
      if (an) a.querySelector(".auswahl-knopf span").textContent = b.textContent;
    });
    a.dispatchEvent(new CustomEvent("wahl", { bubbles: true, detail: w }));
  }
  document.addEventListener("click", function (ev) {
    var k = ev.target.closest(".auswahl-knopf");
    if (k) { if (offen === k.parentElement) zu(); else auf(k.parentElement); return; }
    var o = ev.target.closest(".auswahl-liste [data-w]");
    if (o) { var a = o.closest(".auswahl"); zu(); setzen(a, o.dataset.w); a.querySelector(".auswahl-knopf").focus(); return; }
    if (offen && !ev.target.closest(".auswahl")) zu();
  });
  document.addEventListener("keydown", function (ev) {
    var k = ev.target.closest && ev.target.closest(".auswahl-knopf");
    if (k && !offen && (ev.key === "ArrowDown" || ev.key === "ArrowUp")) { ev.preventDefault(); auf(k.parentElement); return; }
    if (!offen) return;
    var knoepfe = Array.prototype.slice.call(offen.querySelectorAll(".auswahl-liste button")), i = knoepfe.indexOf(document.activeElement);
    if (ev.key === "Escape") { ev.preventDefault(); var kk = offen.querySelector(".auswahl-knopf"); zu(); kk.focus(); }
    else if (ev.key === "ArrowDown") { ev.preventDefault(); knoepfe[Math.min(knoepfe.length - 1, i + 1)].focus(); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); knoepfe[Math.max(0, i - 1)].focus(); }
    else if (ev.key === "Home") { ev.preventDefault(); knoepfe[0].focus(); }
    else if (ev.key === "End") { ev.preventDefault(); knoepfe[knoepfe.length - 1].focus(); }
    else if (ev.key === "Tab") zu();
  });
  addEventListener("scroll", function (ev) { if (offen && !offen.contains(ev.target)) zu(); }, true);
  addEventListener("resize", zu);

  // ---- Dialog: UI.frage({titel, text, ok, gefahr, eingabe, platzhalter, code}) -> Promise
  //      Ergebnis: true/false, bei eingabe der Text oder null
  function frage(o) {
    return new Promise(function (fertig) {
      var m = document.createElement("div"), code = o.code != null;
      m.className = "modal";
      m.innerHTML = '<div class="modal-karte' + (code ? " breit" : "") + '" role="dialog" aria-modal="true" aria-labelledby="modal-titel">' +
        '<h2 id="modal-titel"></h2>' + (o.text ? '<p></p>' : "") + (o.eingabe ? '<input class="feld" maxlength="200">' : "") + (code ? '<pre class="code-box"></pre>' : "") +
        '<div class="modal-aktionen">' + (code ? "" : '<button type="button" class="btn zweit" data-x="nein">Abbrechen</button>') +
        '<button type="button" class="btn' + (o.gefahr ? " gefahr-voll" : "") + '" data-x="ja">' + e(o.ok || (code ? "Schließen" : "OK")) + '</button></div></div>';
      m.querySelector("h2").textContent = o.titel || "";
      if (o.text) m.querySelector("p").textContent = o.text;
      if (code) m.querySelector("pre").textContent = o.code;
      var feld = m.querySelector("input");
      if (feld) { feld.placeholder = o.platzhalter || ""; feld.value = o.wert || ""; }
      var vorher = document.activeElement;
      document.body.appendChild(m);
      function ende(ja) {
        m.remove();
        document.removeEventListener("keydown", taste, true);
        if (vorher && vorher.focus && document.contains(vorher)) vorher.focus();
        fertig(feld ? (ja ? feld.value : null) : ja);
      }
      function taste(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); ende(false); }
        else if (ev.key === "Enter" && ev.target === feld) { ev.preventDefault(); ende(true); }
        else if (ev.key === "Tab") {
          var f = m.querySelectorAll("button, input"), erst = f[0], letzt = f[f.length - 1];
          if (ev.shiftKey && document.activeElement === erst) { ev.preventDefault(); letzt.focus(); }
          else if (!ev.shiftKey && document.activeElement === letzt) { ev.preventDefault(); erst.focus(); }
        }
      }
      m.addEventListener("mousedown", function (ev) { if (ev.target === m) ende(false); });
      m.addEventListener("click", function (ev) { var b = ev.target.closest("[data-x]"); if (b) { ev.stopPropagation(); ende(b.dataset.x === "ja"); } });
      document.addEventListener("keydown", taste, true);
      (feld || m.querySelector('[data-x="ja"]')).focus();
    });
  }

  // ---- Meldung unten rechts
  function meldung(text, fehler) {
    var m = document.getElementById("meldung");
    m.querySelector("span").textContent = text;
    m.querySelector("use").setAttribute("href", fehler ? "#i-fehler" : "#i-ok");
    m.className = "zeigen" + (fehler ? " fehler" : "");
    clearTimeout(meldung.t);
    meldung.t = setTimeout(function () { m.className = fehler ? "fehler" : ""; }, fehler ? 6000 : 4000);
  }

  // ---- Datei-Feld: UI.datei("id", "Titel") -> HTML mit verstecktem <input type=file>
  function datei(id, titel) {
    return '<label class="datei">' + icon("hoch") + '<span><b>' + e(titel || "ZIP-Datei wählen") + '</b><small>oder hierher ziehen</small></span>' +
      '<input type="file" id="' + e(id) + '" accept=".zip,application/zip"></label>';
  }
  function dateiZeigen(input) {
    var l = input.closest(".datei"), f = input.files[0];
    if (!l) return;
    l.classList.toggle("gewaehlt", !!f);
    l.querySelector("small").textContent = f ? f.name + " · " + (f.size / 1024).toFixed(1) + " KB" : "oder hierher ziehen";
  }
  document.addEventListener("change", function (ev) { if (ev.target.matches(".datei input")) dateiZeigen(ev.target); });
  document.addEventListener("dragover", function (ev) { var l = ev.target.closest && ev.target.closest(".datei"); if (l) { ev.preventDefault(); l.classList.add("ziehen"); } });
  document.addEventListener("dragleave", function (ev) { var l = ev.target.closest && ev.target.closest(".datei"); if (l) l.classList.remove("ziehen"); });
  document.addEventListener("drop", function (ev) {
    var l = ev.target.closest && ev.target.closest(".datei");
    if (!l) return;
    ev.preventDefault();
    l.classList.remove("ziehen");
    var i = l.querySelector("input");
    i.files = ev.dataTransfer.files;
    dateiZeigen(i);
  });

  return { auswahl: auswahl, setzen: setzen, frage: frage, meldung: meldung, datei: datei, dateiZeigen: dateiZeigen, icon: icon };
})();
</script>`;

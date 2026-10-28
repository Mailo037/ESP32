# Online-Speicher fuer den ESP-Hub - laeuft auf jedem PC mit Python 3,
# ohne Zusatzpakete und ohne Konto.
#
#   python Hub/server/hub_server.py                 (Port 8080)
#   python Hub/server/hub_server.py --port 9000 --auth GEHEIM
#
# Spricht dasselbe REST wie die Firebase Realtime Database:
#   GET/PUT/PATCH/DELETE /<pfad>.json   (+ ?auth=...)
#   {".sv": "timestamp"} und {".sv": {"increment": n}} werden ersetzt.
# Alles liegt in hub_daten.json neben diesem Skript.
# http://<PC-IP>:8080/ im Browser zeigt alle Bestenlisten.
import argparse
import html
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DATEI = pathlib.Path(__file__).with_name("hub_daten.json")
MAX_BODY = 16384
sperre = threading.Lock()
daten = {}
auth = ""


def laden():
    global daten
    try:
        daten = json.loads(DATEI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        daten = {}


def sichern():
    tmp = DATEI.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATEI)


def teile(pfad):
    t = [x for x in pfad.strip("/").split("/") if x]
    for x in t:
        if any(c in x for c in ".$#[]") or len(x) > 64:
            raise ValueError("ungueltiger Schluessel: " + x)
    return t


def holen(t):
    k = daten
    for x in t:
        if not isinstance(k, dict) or x not in k:
            return None
        k = k[x]
    return k


def server_werte(neu, alt):
    """.sv-Platzhalter wie bei Firebase auswerten."""
    if isinstance(neu, dict):
        if set(neu) == {".sv"}:
            sv = neu[".sv"]
            if sv == "timestamp":
                return int(time.time() * 1000)
            if isinstance(sv, dict) and "increment" in sv:
                basis = alt if isinstance(alt, (int, float)) and not isinstance(alt, bool) else 0
                return basis + sv["increment"]
            raise ValueError("unbekannter .sv-Wert")
        a = alt if isinstance(alt, dict) else {}
        return {k: server_werte(v, a.get(k)) for k, v in neu.items()}
    return neu


def aufraeumen(w):
    """null-Werte und leere Objekte entfernen (wie Firebase)."""
    if isinstance(w, dict):
        w = {k: aufraeumen(v) for k, v in w.items()}
        w = {k: v for k, v in w.items() if v is not None}
        return w or None
    return w


def setzen(t, wert):
    global daten
    if not t:
        daten = aufraeumen(wert) or {}
        return
    k = daten
    for x in t[:-1]:
        if not isinstance(k.get(x), dict):
            k[x] = {}
        k = k[x]
    wert = aufraeumen(wert)
    if wert is None:
        k.pop(t[-1], None)
    else:
        k[t[-1]] = wert
    daten = aufraeumen(daten) or {}


class Handler(BaseHTTPRequestHandler):
    def antwort(self, code, obj=None, text=None, typ="application/json"):
        body = (text if text is not None else json.dumps(obj)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", typ + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def anfrage(self, methode):
        url = urlparse(self.path)
        if methode == "GET" and url.path in ("/", "/index.html"):
            return self.antwort(200, text=uebersicht(), typ="text/html")
        if not url.path.endswith(".json"):
            return self.antwort(404, {"error": "Pfad muss auf .json enden"})
        if auth and parse_qs(url.query).get("auth", [""])[0] != auth:
            return self.antwort(401, {"error": "Permission denied"})
        try:
            t = teile(url.path[:-5])
            body = None
            if methode in ("PUT", "PATCH"):
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    return self.antwort(413, {"error": "zu gross"})
                body = json.loads(self.rfile.read(n) or b"null")
            with sperre:
                if methode == "GET":
                    return self.antwort(200, holen(t))
                if methode == "PUT":
                    wert = server_werte(body, holen(t))
                    setzen(t, wert)
                elif methode == "PATCH":
                    if not isinstance(body, dict):
                        raise ValueError("PATCH braucht ein Objekt")
                    for k, v in body.items():
                        teile(k)
                        tk = t + teile(k)
                        wert = server_werte(v, holen(tk))
                        setzen(tk, wert)
                    wert = body
                else:                       # DELETE
                    setzen(t, None)
                    wert = None
                sichern()
            self.antwort(200, wert)
        except ValueError as e:
            self.antwort(400, {"error": str(e)})

    def do_GET(self):
        self.anfrage("GET")

    def do_PUT(self):
        self.anfrage("PUT")

    def do_PATCH(self):
        self.anfrage("PATCH")

    def do_DELETE(self):
        self.anfrage("DELETE")

    def log_message(self, fmt, *args):
        print("%s %s" % (self.address_string(), fmt % args))


def uebersicht():
    with sperre:
        spiele = (daten.get("esphub") or {})
        teile_html = []
        for spiel, inhalt in sorted(spiele.items()):
            if not isinstance(inhalt, dict):
                continue
            teile_html.append("<h2>%s</h2>" % html.escape(spiel.replace("_", " ")))
            g = inhalt.get("global") or {}
            if g:
                teile_html.append("<p>" + ", ".join("%s: <b>%s</b>" % (html.escape(k), html.escape(str(v)))
                                                     for k, v in sorted(g.items())) + "</p>")
            for liste, eintraege in sorted((inhalt.get("listen") or {}).items()):
                zeilen = sorted(((e.get("p", 0), e.get("n", "?"), b) for b, e in eintraege.items()
                                 if isinstance(e, dict)), reverse=True)
                teile_html.append("<h3>%s</h3><ol>%s</ol>" % (html.escape(liste), "".join(
                    "<li><b>%s</b> %s <small>%s</small></li>" % (html.escape(str(p)), html.escape(str(n)), b)
                    for p, n, b in zeilen[:20])))
            teile_html.append("<p><small>%d Boards</small></p>" % len(inhalt.get("boards") or {}))
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>ESP-Hub Online</title><style>body{font-family:system-ui;max-width:40em;margin:1em auto;"
            "padding:0 1em;background:#0e1620;color:#e8f1ff}small{color:#8fa3b8}</style>"
            "<h1>ESP-Hub Online-Speicher</h1>" + ("".join(teile_html) or "<p>Noch keine Daten.</p>"))


def main():
    global auth
    ap = argparse.ArgumentParser(description="Online-Speicher fuer den ESP-Hub")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--auth", default="", help="Passwort, das auch in hub_online.json steht")
    a = ap.parse_args()
    auth = a.auth
    laden()
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    print("ESP-Hub-Server auf Port %d - Daten in %s" % (a.port, DATEI))
    print('In hub_online.json: "url": "http://<IP dieses PCs>:%d"' % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

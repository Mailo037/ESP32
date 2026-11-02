# =====================================================================
#  Speicher fuer den ESP-Hub: lokal + optional online
# =====================================================================
#  Spiele bekommen in der Galerie das Modul "hub" (siehe api()). Alles wird
#  sofort lokal in /hubdaten/<Spiel>.json gespeichert. Ist /hub_online.json
#  vorhanden, gleicht der Hub in der ruhenden Galerie mit dem
#  Online-Speicher ab (Firebase Realtime Database oder Hub/server).
#
#  Ablage online (REST, Firebase-kompatibel):
#    esphub/<Spiel>/boards/<Board-ID>   Daten dieses Boards
#    esphub/<Spiel>/global              fuer alle Boards gemeinsam
#    esphub/<Spiel>/listen/<Liste>/<Board-ID>  bester Eintrag je Board
#
#  App-Store: <url>/apps liefert den Katalog (Name, Version, Groesse,
#  SHA-256), <url>/apps/<id> die Datei. Der Katalog wird bei jedem
#  Abgleich mitgeholt, damit die Galerie Updates anzeigen kann.
#
#  Board-ID = MAC aus dem eFuse des ESP32 (machine.unique_id()). Die ist
#  ab Werk eingebrannt und laesst sich per Software nicht aendern.
# =====================================================================
import gc
import json
import os
import sys
import time
import machine

KONFIG = "/hub_online.json"
CACHE = "/hubdaten"
KATALOG = CACHE + "/_katalog.json"
SCHLUESSEL = CACHE + "/_schluessel.txt"   # Board-Schluessel vom Server (geheim)
BOARD = CACHE + "/_board.json"            # Konto, offene Auftraege
MAX_BYTES = 4096            # Board-Daten pro Spiel, damit der Flash nicht vollaeuft
WLAN_TIMEOUT_MS = 3000
DIAGNOSE = CACHE + "/_diagnose.json"
LETZTER_SYNC = None


def diagnose(fehler=None, erfolg=False):
    global LETZTER_SYNC
    d = _json_lesen(DIAGNOSE, {})
    if fehler is not None:
        # Never persist arbitrary exception text: URLs may contain credentials.
        d["fehler"] = str(fehler)[:80] if not any(s in str(fehler).lower() for s in ("http://", "https://", "passwort", "auth=", "?t=", "&t=")) else "Network request failed"
    if erfolg:
        d["sync"] = time.time()
        LETZTER_SYNC = time.ticks_ms()
        d["status"] = "online"
    elif fehler is not None:
        d["status"] = "offline"
    _json_schreiben(DIAGNOSE, d)
    return d


def offene_daten():
    n = 0
    try:
        for name in os.listdir(CACHE):
            if name.endswith(".json") and not name.startswith("_"):
                d = _json_lesen(CACHE + "/" + name, {})
                if any(d.get("offen", {}).values()) or d.get("offen", {}).get("loeschen") is not None or d.get("vorgang"):
                    n += 1
    except OSError:
        pass
    return n


def formular(text):
    def decode(s):
        raw = bytearray()
        s = s.replace("+", " ")
        i = 0
        while i < len(s):
            if s[i] == "%":
                raw.append(int(s[i + 1:i + 3], 16))
                i += 3
            else:
                raw.extend(s[i].encode())
                i += 1
        return raw.decode("utf-8")
    result = {}
    for part in text.split("&"):
        key, _, value = part.partition("=")
        key, value = decode(key), decode(value)
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


SETUP_MS = 300000


def _setup_bildschirm(oled, ssid, password, ip, rest_ms, zeile=""):
    """Live screen: the running countdown shows the board still responds."""
    import hub_apps as ha
    s = max(0, rest_ms) // 1000
    ha.kopfzeile(oled, "WI-FI SETUP", "%d:%02d" % (s // 60, s % 60))
    oled.text(ssid[:16], 0, 13, 1)
    oled.text(("PW " + password)[:16], 0, 23, 1)
    oled.text(ip[:16], 0, 33, 1)
    oled.hline(0, 44, 128, 1)
    oled.text((zeile or "S4 = Cancel")[:16], 0, 52, 1)
    oled.show()


def _setup_antwort(client, status, page):
    try:
        body = ('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP-Hub Wi-Fi</title><style>body{font:18px system-ui;max-width:30rem;margin:2rem auto;padding:1rem}label,input,button{display:block;margin:1rem 0}input,button{font:inherit;padding:.6rem;box-sizing:border-box;max-width:100%}</style>' + page).encode()
        client.sendall(('HTTP/1.1 ' + status + '\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nX-Frame-Options: DENY\r\nContent-Security-Policy: default-src \'none\'; style-src \'unsafe-inline\'; form-action \'self\'; frame-ancestors \'none\'\r\nConnection: close\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode() + body)
    except OSError:
        pass


def _setup_anfrage(client, ip, csrf):
    """Read one request. Returns (page, (wlan, passwort) or None)."""
    client.settimeout(2)
    raw = b""
    while b"\r\n\r\n" not in raw and len(raw) <= 2048:
        part = client.recv(256)
        if not part:
            raise ValueError("Incomplete request")
        raw += part
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep or len(head) > 2048:
        raise ValueError("Request too large")
    lines = head.decode().split("\r\n")
    method, path, protocol = lines[0].split(" ")
    headers = {}
    for line in lines[1:]:
        key, _, value = line.partition(":")
        key = key.lower().strip()
        if key in headers:
            raise ValueError("Duplicate header")
        headers[key] = value.strip()
    if headers.get("host") not in (ip, ip + ":80") or headers.get("origin", "http://" + ip) != "http://" + ip:
        raise ValueError("Request did not come from the setup page")
    if method == "POST" and path == "/":
        size = int(headers.get("content-length", "0"))
        if not 0 < size <= 1024 or "transfer-encoding" in headers or not headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
            raise ValueError("Invalid form")
        while len(body) < size:
            part = client.recv(min(256, size - len(body)))
            if not part:
                raise ValueError("Incomplete form")
            body += part
        form = formular(body[:size].decode())
        if form.get("csrf") != csrf:
            raise ValueError("Form expired")
        wlan, pw = form.get("wlan", ""), form.get("passwort", "")
        if not 0 < len(wlan.encode()) <= 32 or len(pw.encode()) > 63 or any(ord(c) < 32 for c in wlan + pw):
            raise ValueError("Invalid Wi-Fi details")
        # The check runs after this reply: joining the home network moves the
        # setup network to its channel, so the phone may drop off briefly.
        return ("<h1>Checking Wi-Fi ...</h1><p>Watch the board display. If the details work, "
                "the board saves them and restarts. Otherwise reconnect to the setup network "
                "and open this page again.</p>"), (wlan, pw)
    if method == "GET" and path == "/":
        return ('<h1>Set up ESP-Hub</h1><form method="post"><input type="hidden" name="csrf" value="' + csrf + '"><label>Wi-Fi name<input name="wlan" maxlength="32" required autocomplete="off"></label><label>Wi-Fi password<input type="password" name="passwort" maxlength="63" autocomplete="new-password"></label><button>Connect and save</button></form><p>Leave the password blank for open Wi-Fi. Press S4 on the board to cancel.</p>'), None
    raise ValueError("Unknown page")


def wlan_einrichten(oled, ein, fragen=True):
    """Explicit, password-protected AP; credentials stay on this board.
    fragen=False: direkt starten (schlanker Modus nach dem Neustart)."""
    import network
    import socket
    import select
    import binascii
    import hub_apps as ha
    password = binascii.hexlify(os.urandom(6)).decode()
    csrf = binascii.hexlify(os.urandom(16)).decode()
    ssid = "ESP-Hub-" + board_id()[-4:]
    ap = network.WLAN(network.AP_IF)
    server = None
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(False)
        # Switch the AP on before configuring it: MicroPython builds differ
        # in whether config() works while the Wi-Fi driver is stopped.
        ap.active(True)
        ap.config(essid=ssid, password=password, authmode=3)
        ip = ap.ifconfig()[0]
        if fragen and ha.menue(oled, ein, "WI-FI SETUP", [ssid, "PW " + password, ip], ["Start", "Cancel"]) != 0:
            return False
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, 80))
        server.listen(2)
        # accept() with settimeout() can block for good on the ESP32 - then
        # neither S4 nor the five-minute limit react and the board looks
        # frozen. A non-blocking socket plus poll() keeps the loop running.
        server.setblocking(False)
        poller = select.poll()
        poller.register(server, select.POLLIN)
        start = time.ticks_ms()
        shown = None
        ein.warte_los()
        while True:
            rest = SETUP_MS - time.ticks_diff(time.ticks_ms(), start)
            if rest <= 0:
                return False
            if rest // 1000 != shown:
                shown = rest // 1000
                _setup_bildschirm(oled, ssid, password, ip, rest)
            if ein.lesen() == "zurueck":
                return False
            if not poller.poll(30):
                continue
            try:
                client, address = server.accept()
            except OSError:
                continue
            daten = None
            try:
                page, daten = _setup_anfrage(client, ip, csrf)
                status = "200 OK"
            except Exception:
                # No request text or submitted password is reflected into HTML/logs.
                page = '<h1>Setup was not saved</h1><p>Check your Wi-Fi details and connection.</p><a href="/">Try again</a>'
                status = "400 Bad Request"
            _setup_antwort(client, status, page)
            client.close()
            if daten is None:
                continue
            # Verify the new network before replacing the old configuration.
            _setup_bildschirm(oled, ssid, password, ip, rest, "Checking Wi-Fi")
            sta.active(True)
            sta.connect(daten[0], daten[1])
            begonnen = time.ticks_ms()
            while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), begonnen) < 10000:
                if ein.lesen() == "zurueck":
                    return False
                time.sleep_ms(100)
            if sta.isconnected():
                config = konfig_lesen() or {"url": "https://esphub-steel.vercel.app", "auth": ""}
                config.update(wlan=daten[0], passwort=daten[1])
                config.pop("modus", None)
                _json_schreiben(KONFIG, config)
                ha.meldung(oled, "Wi-Fi saved", "Restarting ...")
                time.sleep_ms(800)
                machine.reset()
                return True
            try:
                sta.disconnect()
            except OSError:
                pass
            sta.active(False)
            _setup_bildschirm(oled, ssid, password, ip, rest, "Failed - retry")
            time.sleep_ms(1500)
            shown = None
    except Exception as error:
        ha.fehler_dialog(oled, ein, "Wi-Fi setup", error)
        return False
    finally:
        if server:
            server.close()
        sta.active(False)
        ap.active(False)


def board_id():
    return "".join("%02x" % b for b in machine.unique_id())


def board_nr():
    m = machine.unique_id()
    return ((m[4] << 8) | m[5]) % 10000      # wie in ESP-Pong


def konfig_lesen():
    try:
        with open(KONFIG) as f:
            k = json.load(f)
        return k if k.get("url") else None
    except (OSError, ValueError):
        return None


def _schluessel(k):
    k = str(k)
    if not 0 < len(k) <= 40 or k == "_hub_ops":
        raise ValueError("Key: 1-40 characters")
    for c in k:
        if not (c.isalpha() or c.isdigit() or c in "_-"):
            raise ValueError("Key: only A-Z, 0-9, _ and -")
    return k


def _leer():
    return {"board": {}, "global": {}, "listen": {},
            "offen": {"board": [], "setzen": {}, "plus": {}, "listen": [], "loeschen": None}}


def _json_lesen(datei, standard):
    try:
        with open(datei) as f:
            return json.load(f)
    except (OSError, ValueError):
        return standard


def _json_schreiben(datei, wert):
    try:
        os.mkdir(CACHE)
    except OSError:
        pass
    with open(datei + ".neu", "w") as f:
        json.dump(wert, f)
    getattr(os, "sync", lambda: None)()
    os.rename(datei + ".neu", datei)
    getattr(os, "sync", lambda: None)()


def board_status():
    """{"konto": ..., "auftraege": {"install": [...], "deinstall": [...]}}"""
    return _json_lesen(BOARD, {})


def schluessel():
    try:
        with open(SCHLUESSEL) as f:
            return f.read().strip()
    except OSError:
        return ""


def katalog_lokal():
    """Zuletzt geholter App-Katalog: {id: {...}} (leer, wenn never online)."""
    try:
        with open(KATALOG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------
#  WLAN + HTTP
# ---------------------------------------------------------------------
class Netz:
    def __init__(self, konfig, budget_ms=20000):
        self.k = konfig
        self.sta = None
        self.req = None
        self.bis = time.ticks_add(time.ticks_ms(), budget_ms)

    def rest(self):
        ms = time.ticks_diff(self.bis, time.ticks_ms())
        if ms <= 0:
            raise OSError("Online time budget exceeded")
        return max(1, (ms + 999) // 1000)

    def verbinden(self):
        if self.k.get("modus") == "repeater":
            # Kein eigenes WLAN: Anfragen gehen per ESP-NOW an ein anderes Board
            self.req = RepeaterClient()
            self.req.verbinden(self.rest)
            return
        import network
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        if not self.sta.isconnected():
            self.sta.connect(self.k.get("wlan", ""), self.k.get("passwort", ""))
            start = time.ticks_ms()
            while not self.sta.isconnected():
                self.rest()
                if time.ticks_diff(time.ticks_ms(), start) > WLAN_TIMEOUT_MS:
                    raise OSError("Wi-Fi unavailable")
                time.sleep_ms(100)
        try:
            import requests
        except ImportError:
            import urequests as requests
        self.req = requests

    def trennen(self):
        # WLAN aus und requests/ssl wegraeumen: Spiele wie Pong brauchen
        # danach ESP-NOW auf ihrem eigenen Kanal und den ganzen RAM
        if self.req is not None and hasattr(self.req, "beenden"):
            self.req.beenden()
        self.req = None
        for n in ("requests", "urequests"):
            m = sys.modules.get(n)
            if m is not None and not getattr(m, "SIMULATOR", False):
                del sys.modules[n]
        if self.sta is not None:
            try:
                self.sta.disconnect()
                self.sta.active(False)
            except Exception:
                pass
        self.sta = None
        gc.collect()

    def _url(self, basis, pfad):
        # Jede Anfrage traegt die Board-ID - so kann der Server Limits
        # pruefen und gesperrte Boards abweisen
        url = basis.rstrip("/") + "/" + pfad + "?board=" + board_id()
        t = schluessel()
        if t:
            url += "&t=" + t
        if self.k.get("auth"):
            url += "&auth=" + self.k["auth"]
        return url

    @staticmethod
    def _fehler(r, wer):
        """Fehlermeldung des Servers lesen (z. B. 'Board blocked: ...')."""
        try:
            text = r.json().get("error", "")
        except Exception:
            text = ""
        return OSError("%s: %s" % (wer, text) if text else "%s: HTTP %d" % (wer, r.status_code))

    def melden(self, erledigt=None):
        """Beim Vercel-Server anmelden: Hub version, Apps, Nutzung, Storage
        und Pruefsummen der Hub-Dateien. Back kommen Konto und offene
        Auftraege. Andere Server kennen das nicht (404) - dann passiert nichts."""
        import hub_apps
        apps = {n: hub_apps.kopf(n)["version"] for n in hub_apps.apps()}
        pruef = {d: hub_apps.pruefsumme("/" + d) for d in hub_apps.HUB_DATEIEN}
        gc.collect()
        daten = {"nr": board_nr(), "hub": hub_apps.HUB_VERSION, "apps": apps, "pruef": pruef,
                 "nutzung": hub_apps.nutzung_lesen(), "frei": hub_apps.frei(), "ram": gc.mem_free(),
                 "hardware": hub_apps.hardware(), "protokoll": 2}
        if erledigt:
            daten["erledigt"] = erledigt
        r = self._anfrage("POST", self._url(self.k["url"], "melden"), data=json.dumps(daten),
                          headers={"Content-Type": "application/json"})
        try:
            if r.status_code in (404, 405, 501):     # PC-Server/Firebase: kein /melden
                return None
            if r.status_code >= 300:
                raise self._fehler(r, "Server")
            a = r.json()
        finally:
            r.close()
        if a.get("schluessel"):
            # Erste Anmeldung: Schluessel merken - ab jetzt weist er dieses Board aus
            try:
                os.mkdir(CACHE)
            except OSError:
                pass
            with open(SCHLUESSEL, "w") as f:
                f.write(a["schluessel"])
        _json_schreiben(BOARD, {"konto": a.get("konto"), "auftraege": a.get("auftraege") or {},
                              "jobs": a.get("jobs") or {}, "protokoll": a.get("protokoll", 1)})
        return a

    def kopplung(self):
        r = self._anfrage("GET", self._url(self.k["url"], "kopplung"))
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Server")
            return r.json()
        finally:
            r.close()

    def hochladen(self, name, ziel):
        """Lokale App ins Konto laden (ziel "privat") oder zur Pruefung."""
        import hub_apps
        datei = hub_apps.datei(name)
        if datei.startswith(hub_apps.PAKETE + "/"):
            raise OSError("Upload ZIP projects in the portal")
        with open(datei, "rb") as f:
            code = f.read()
        r = self._anfrage("POST", self._url(self.k["url"], "hochladen") + "&ziel=" + ziel + "&datei=gal_" + name + ".py",
                          data=code, headers={"Content-Type": "text/plain"})
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Server")
            return r.json()
        finally:
            r.close()

    def _anfrage(self, methode, url, **kw):
        try:
            return self.req.request(methode, url, timeout=min(5, self.rest()), **kw)
        except TypeError:           # aeltere urequests ohne timeout
            raise OSError("HTTP driver needs timeout support: update MicroPython")

    def vorgang(self, spiel, daten=None):
        r = self._anfrage("GET" if daten is None else "POST", self._url(self.k["url"], "sync/" + spiel),
                          data=None if daten is None else json.dumps(daten), headers={"Content-Type": "application/json"})
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Sync")
            return r.json()
        finally:
            r.close()

    def auftrag_status(self, art, name, status, fehler=""):
        job = board_status().get("jobs", {}).get(art, {}).get(name)
        if not isinstance(job, dict) or not job.get("id"):
            return
        r = self._anfrage("POST", self._url(self.k["url"], "auftrag"),
                          data=json.dumps({"art": art, "app": name, "id": job["id"], "status": status, "fehler": fehler[:120]}),
                          headers={"Content-Type": "application/json"})
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Auftrag")
        finally:
            r.close()

    def katalog(self):
        """App-Katalog holen und fuer die Galerie merken."""
        r = self._anfrage("GET", self._url(self.k.get("store") or self.k["url"], "apps"))
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Store")
            kat = {}
            for a in r.json().get("apps", []):
                i = str(a.get("id", ""))
                # die ID wird zum Dateinamen gal_<id>.py - nur sichere Zeichen
                if i and len(i) <= 40 and all(c.isalpha() or c.isdigit() or c == "_" for c in i):
                    kat[i] = a
        finally:
            r.close()
        try:
            os.mkdir(CACHE)
        except OSError:
            pass
        with open(KATALOG, "w") as f:
            json.dump(kat, f)
        return kat

    def app_laden(self, app, ziel, fortschritt=None):
        """App-Datei in Stuecken nach 'ziel' schreiben und per SHA-256
        pruefen - die ganze Datei passt nicht unbedingt in den RAM."""
        import hashlib
        import binascii
        return self.datei_laden("apps/" + app["id"], ziel, app, fortschritt)

    def firmware(self):
        r = self._anfrage("GET", self._url(self.k["url"], "firmware"))
        try:
            if r.status_code == 404:
                return None
            if r.status_code >= 300:
                raise self._fehler(r, "Firmware")
            return r.json().get("firmware")
        finally:
            r.close()

    def datei_laden(self, pfad, ziel, app, fortschritt=None, extra=""):
        import hashlib
        import binascii
        basis = self.k["url"] if pfad.startswith("firmware/") else (self.k.get("store") or self.k["url"])
        r = self._anfrage("GET", self._url(basis, pfad) + extra)
        try:
            if r.status_code >= 300:
                raise self._fehler(r, "Store")
            h = hashlib.sha256()
            n = 0
            quelle = getattr(r, "raw", None)
            with open(ziel, "wb") as f:
                if quelle is None:                  # Simulator: alles auf einmal
                    stueck = r.content
                    f.write(stueck)
                    h.update(stueck)
                    n = len(stueck)
                while quelle is not None and n < app["groesse"]:
                    stueck = quelle.read(min(1024, app["groesse"] - n))
                    if not stueck:
                        break
                    f.write(stueck)
                    h.update(stueck)
                    n += len(stueck)
                    if fortschritt:
                        fortschritt(n / app["groesse"])
        finally:
            r.close()
        if n != app["groesse"] or binascii.hexlify(h.digest()).decode() != app["sha256"]:
            os.remove(ziel)
            raise OSError("Download verification failed")

    def limits(self, spiel):
        """Speicherlimits vom Vercel-Server (andere Server: None)."""
        r = self._anfrage("GET", self._url(self.k["url"], "limits/%s/%s" % (board_id(), spiel)))
        try:
            return r.json() if r.status_code == 200 else None
        finally:
            r.close()

    def http(self, methode, pfad, daten=None):
        url = self._url(self.k["url"], "esphub/" + pfad + ".json")
        body = None if daten is None else json.dumps(daten)
        r = self._anfrage(methode, url, data=body, headers={"Content-Type": "application/json"})
        try:
            if r.status_code >= 300:
                e = self._fehler(r, "HTTP %d" % r.status_code)
                raise e
            return r.json() if methode == "GET" else None
        finally:
            r.close()


# ---------------------------------------------------------------------
#  Speicher eines Spiels
# ---------------------------------------------------------------------
class Speicher:
    def __init__(self, spiel):
        self.spiel = spiel
        self.id = board_id()
        self.datei = CACHE + "/" + spiel + ".json"
        self.konfig = konfig_lesen()
        self.status = "aus" if self.konfig is None else "offline"
        self.benutzt = False
        try:
            with open(self.datei) as f:
                self.d = json.load(f)
            for k, v in _leer().items():
                self.d.setdefault(k, v)
        except (OSError, ValueError):
            self.d = _leer()

    def schreiben(self):
        try:
            os.mkdir(CACHE)
        except OSError:
            pass
        with open(self.datei + ".neu", "w") as f:
            json.dump(self.d, f)
        getattr(os, "sync", lambda: None)()
        os.rename(self.datei + ".neu", self.datei)   # nie halb geschriebene Datei
        getattr(os, "sync", lambda: None)()

    def offen(self):
        o = self.d["offen"]
        return bool(self.d.get("vorgang") or o["board"] or o["setzen"] or o["plus"] or o["listen"] or o.get("loeschen") is not None)

    def alles_loeschen(self):
        """Save data dieses Boards loeschen. Online passiert das beim
        naechsten Sync (Board-Daten + eigene Leaderboards-Eintraege)."""
        listen = list(self.d["listen"])
        alt = self.d["offen"].get("loeschen") or []
        self.d = _leer()
        if self.konfig is not None:
            self.d["offen"]["loeschen"] = sorted(set(listen + alt))
            self.schreiben()
        else:
            try:
                os.remove(self.datei)
            except OSError:
                pass

    # ---- Abgleich ----------------------------------------------------
    def abgleichen(self, andere=True, netz=None):
        """Holen, zusammenfuehren, Ausstehendes hochladen (synchron, mit Budget).
        andere=True: auch liegengebliebene Daten anderer Spiele hochladen
        und den App-Katalog (fuer Update-Anzeige) holen."""
        if self.konfig is None:
            return False
        eigen = netz is None
        netz = netz or Netz(self.konfig)
        try:
            if eigen:
                netz.verbinden()
                netz.melden()
            self._abgleich(netz)
            if andere:
                try:
                    netz.katalog()
                except Exception as e:
                    print("Hub Store:", e)
            if andere:
                try:
                    for d in os.listdir(CACHE):
                        if d.endswith(".json") and not d.startswith("_") and d[:-5] != self.spiel:
                            sp = Speicher(d[:-5])
                            if sp.offen():
                                sp._abgleich(netz)
                except Exception as e:
                    print("Hub online (other games):", e)
            diagnose(erfolg=True)
            return True
        except Exception as e:
            print("Hub online:", e)
            diagnose(e)
            self.status = "gesperrt" if any(word in str(e).lower() for word in ("blocked", "gesperrt")) else "offline"
            return False
        finally:
            if eigen:
                netz.trennen()

    def _abgleich(self, netz):
        try:
            self._loeschen_senden(netz)
            self._holen(netz)
            self._senden(netz)
            try:
                l = netz.limits(self.spiel)
                if l:
                    self.d["limit"] = l
            except Exception:
                pass
            self.status = "online"
        finally:
            try:
                self.schreiben()
            except OSError:
                pass

    def _loeschen_senden(self, netz):
        o = self.d["offen"]
        listen = o.get("loeschen")
        if listen is None:
            return
        netz.http("DELETE", self.spiel + "/boards/" + self.id)
        for name in listen:
            netz.http("DELETE", self.spiel + "/listen/" + name + "/" + self.id)
        o["loeschen"] = None

    def _holen(self, netz):
        d, o, basis = self.d, self.d["offen"], self.spiel + "/"
        online = netz.http("GET", basis + "boards/" + self.id) or {}
        for k, v in online.items():
            if k not in o["board"]:          # lokal Geaendertes gewinnt
                d["board"][k] = v
        g = netz.http("GET", basis + "global") or {}
        g.update(o["setzen"])
        for k, n in o["plus"].items():
            g[k] = (g.get(k) or 0) + n
        d["global"] = g
        listen = netz.http("GET", basis + "listen") or {}
        for name, eintraege in listen.items():
            eigen = d["listen"].get(name, {}).get(self.id)
            on = eintraege.get(self.id)
            if name in o["listen"] and eigen and on and on.get("p", 0) >= eigen["p"]:
                o["listen"].remove(name)     # online steht schon was Besseres
            if name in o["listen"] and eigen:
                eintraege[self.id] = eigen
            d["listen"][name] = eintraege

    def _senden(self, netz):
        d, o, basis = self.d, self.d["offen"], self.spiel + "/"
        if o["board"]:
            try:
                netz.http("PATCH", basis + "boards/" + self.id,
                          {k: d["board"].get(k) for k in o["board"]})
            except OSError as e:
                if "413" not in str(e):
                    raise
                # Server sagt: Speicherlimit erreicht - lokal bleibt alles,
                # aber nicht bei jedem Abgleich wieder versuchen
                print("Hub online: storage limit reached")
                d["voll"] = True
            o["board"] = []
        # Persist an immutable operation before sending; retry after lost replies.
        if self.d.get("vorgang") or o["setzen"] or o["plus"]:
            if board_status().get("protokoll", 1) < 2:
                raise OSError("Update service for safe sync")
            if self.d.get("vorgang"):
                result = netz.vorgang(self.spiel, self.d["vorgang"])
                del self.d["vorgang"]
                if "werte" in result:
                    d["global"] = result["werte"]
                    d["global"].update(o["setzen"])
                    for k, n in o["plus"].items():
                        d["global"][k] = (d["global"].get(k) or 0) + n
                self.schreiben()
            if o["setzen"] or o["plus"]:
                seq = netz.vorgang(self.spiel)["seq"] + 1
                self.d["vorgang"] = {"seq": seq, "setzen": dict(o["setzen"]), "plus": dict(o["plus"])}
                o["setzen"] = {}
                o["plus"] = {}
                self.schreiben()
                result = netz.vorgang(self.spiel, self.d["vorgang"])
                del self.d["vorgang"]
                if "werte" in result:
                    d["global"] = result["werte"]
                self.schreiben()
        for name in list(o["listen"]):
            e = dict(d["listen"][name][self.id])
            e["t"] = {".sv": "timestamp"}
            netz.http("PUT", basis + "listen/" + name + "/" + self.id, e)
            o["listen"].remove(name)

    # ---- Schnittstelle fuer Spiele -----------------------------------
    def api(self):
        """Das Modul "hub", das ein Spiel mit "import hub" bekommt. Nur
        Funktionen, keine Attribute - so kommt das Spiel nicht an die
        WLAN-Zugangsdaten."""
        d, s = self.d, self
        s.benutzt = False

        class Hub:
            pass
        m = Hub()

        def laden(k, standard=None):
            return d["board"].get(_schluessel(k), standard)

        def speichern(k, wert):
            k = _schluessel(k)
            alt = d["board"].get(k)
            d["board"][k] = wert
            grenze = d.get("limit", {}).get("app", MAX_BYTES)
            if len(json.dumps(d["board"])) > grenze:
                d["board"][k] = alt
                raise ValueError("hub: Speicherlimit %d Bytes" % grenze)
            if k not in d["offen"]["board"]:
                d["offen"]["board"].append(k)
            s.schreiben()

        def global_laden(k, standard=None):
            return d["global"].get(_schluessel(k), standard)

        def global_setzen(k, wert):
            k = _schluessel(k)
            d["global"][k] = wert
            d["offen"]["setzen"][k] = wert
            d["offen"]["plus"].pop(k, None)
            s.schreiben()

        def global_addieren(k, n=1):
            k = _schluessel(k)
            d["global"][k] = (d["global"].get(k) or 0) + n
            if k in d["offen"]["setzen"]:
                d["offen"]["setzen"][k] = d["global"][k]
            else:
                d["offen"]["plus"][k] = d["offen"]["plus"].get(k, 0) + n
            s.schreiben()
            return d["global"][k]

        def eintragen(liste, punkte, name=""):
            """Bester Wert je Board. True = neuer persoenlicher Rekord."""
            liste = _schluessel(liste)
            eintraege = d["listen"].setdefault(liste, {})
            alt = eintraege.get(s.id)
            if alt is not None and alt.get("p", 0) >= punkte:
                return False
            eintraege[s.id] = {"n": str(name or "#%04d" % board_nr())[:10], "p": punkte}
            if liste not in d["offen"]["listen"]:
                d["offen"]["listen"].append(liste)
            s.schreiben()
            return True

        def bestenliste(liste, anzahl=10):
            """[(name, punkte, eigener_eintrag), ...], beste zuerst."""
            eintraege = d["listen"].get(_schluessel(liste), {})
            l = [(e.get("n", "?"), e.get("p", 0), b == s.id) for b, e in eintraege.items()
                 if isinstance(e, dict)]
            l.sort(key=lambda e: -e[1])
            return l[:anzahl]

        def sync():
            """Sofort synchron abgleichen (mit Zeitbudget) und WLAN kurz
            ein - also nicht mitten in einem ESP-NOW-Spiel aufrufen."""
            return s.abgleichen()

        # Merken, ob das Spiel den Speicher benutzt (fuer das App-Menue)
        def benutzt(f):
            def w(*a, **k):
                s.benutzt = True
                return f(*a, **k)
            return w
        laden, speichern, eintragen, bestenliste = benutzt(laden), benutzt(speichern), benutzt(eintragen), benutzt(bestenliste)
        global_laden, global_setzen = benutzt(global_laden), benutzt(global_setzen)
        global_addieren, sync = benutzt(global_addieren), benutzt(sync)

        def speicher_info():
            """(belegt, maximal) in Bytes fuer die Daten dieses Spiels."""
            return len(json.dumps(d["board"])), d.get("limit", {}).get("app", MAX_BYTES)

        m.speicher_info = speicher_info
        m.board_id = board_id
        m.board_nr = board_nr
        m.online = lambda: s.status == "online"
        m.laden = laden
        m.speichern = speichern
        m.global_laden = global_laden
        m.global_setzen = global_setzen
        m.global_addieren = global_addieren
        m.eintragen = eintragen
        m.bestenliste = bestenliste
        m.sync = sync
        return m


def verbindung_testen():
    """Fuer den Info-Bildschirm der Galerie: (ok, Meldung)."""
    k = konfig_lesen()
    if k is None:
        return False, "not configured"
    netz = Netz(k)
    try:
        netz.verbinden()
        netz.melden()
        netz.http("GET", "_ping")
        return True, "Connection OK"
    except Exception as e:
        return False, str(e)[:32]
    finally:
        netz.trennen()


# =====================================================================
#  Repeater: Boards ohne eigenes WLAN gehen ueber ein anderes Board online
# =====================================================================
#  Ein Board mit WLAN startet in Board info "Be a repeater". Andere Boards
#  waehlen bei "Set up Wi-Fi" den Punkt "Via repeater". Ihre HTTP-Anfragen
#  gehen dann per ESP-NOW an den Repeater, der sie ueber sein WLAN an den
#  Hub-Server schickt und die Antwort Stueck fuer Stueck zurueckfunkt.
#
#  Rahmen (max. 250 Bytes):
#    HR? <nonce>                 Suche (Broadcast, Client)
#    HR! <nonce>                 Antwort des Repeaters
#    HQ/HS id seq(2) letzt daten Anfrage / Antwort, Stueck fuer Stueck
#    HA id seq(2)                Quittung fuer ein Stueck
#    HX id                       Abbruch (Client schliesst die Antwort)
#  Stueck 0 ist ein JSON-Kopf, danach folgt der Body. Jedes Stueck wird
#  quittiert, so laeuft kein Empfangspuffer ueber und grosse Downloads
#  brauchen nicht mehr RAM als ein Stueck.
#
#  Der Repeater leitet nur an seine eigene Server-URL (und Store-URL)
#  weiter, nie an beliebige Adressen.
# =====================================================================
STUECK = 240
BROADCAST = b"\xff" * 6
MERKER = CACHE + "/_repeater.json"   # zuletzt gefundener Repeater


class Abbruch(Exception):
    pass


def _rahmen(typ, mid, seq, letzt, daten=b""):
    return typ + bytes((mid, seq >> 8, seq & 255, 1 if letzt else 0)) + daten


def _quittung(mid, seq):
    return b"HA" + bytes((mid, seq >> 8, seq & 255))


class Funk:
    """ESP-NOW auf dem Kanal der STA-Schnittstelle."""

    def __init__(self, kanal=None):
        import network
        import espnow
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        try:
            # Mit WLAN-Verbindung verpasst der Stromsparmodus ESP-NOW-Rahmen
            self.sta.config(pm=self.sta.PM_NONE)
        except (AttributeError, OSError, ValueError):
            pass
        if kanal:
            self.kanal(kanal)
        self.e = espnow.ESPNow()
        self.e.active(True)
        self.peers = set()
        self.peer(BROADCAST)

    def kanal(self, k=None):
        if k is None:
            return self.sta.config("channel")
        try:
            self.sta.disconnect()
        except OSError:
            pass
        self.sta.config(channel=k)

    def peer(self, mac):
        if mac not in self.peers:
            try:
                self.e.add_peer(mac)
            except OSError:
                pass
            self.peers.add(mac)

    def senden(self, mac, msg):
        self.peer(mac)
        try:
            return self.e.send(mac, msg, True)
        except OSError:
            return False

    def empfangen(self, ms):
        try:
            return self.e.recv(ms)
        except OSError:
            return None, None

    def aus(self):
        try:
            self.e.active(False)
        except Exception:
            pass


def _mit_quittung(funk, mac, msg, mid, seq):
    """Ein Stueck senden, bis es quittiert ist."""
    for _ in range(6):
        funk.senden(mac, msg)
        ende = time.ticks_add(time.ticks_ms(), 400)
        while time.ticks_diff(ende, time.ticks_ms()) > 0:
            m, a = funk.empfangen(40)
            if not a or m != mac:
                continue
            if a[:2] == b"HA" and len(a) >= 5 and a[2] == mid and ((a[3] << 8) | a[4]) == seq:
                return
            if a[:2] == b"HX" and len(a) >= 3 and a[2] == mid:
                raise Abbruch()
    raise OSError("Repeater not responding")


def _strom(funk, mac, typ, mid, quelle):
    """Stuecke aus quelle() senden; quelle liefert b"" am Ende."""
    seq = 0
    jetzt = quelle()
    while True:
        naechstes = quelle() if jetzt else b""
        _mit_quittung(funk, mac, _rahmen(typ, mid, seq, not naechstes, jetzt), mid, seq)
        if not naechstes:
            return
        jetzt = naechstes
        seq += 1


def _stuecke(kopf, body):
    """Quelle: erst der Kopf als eigenes Stueck, dann der Body."""
    teile = [kopf]
    pos = [0]

    def quelle():
        if teile:
            return teile.pop()
        t = body[pos[0]:pos[0] + STUECK]
        pos[0] += len(t)
        return t
    return quelle


class _Empfang:
    """Stuecke einer Nachricht der Reihe nach annehmen und quittieren."""

    def __init__(self, funk, mac, typ, mid):
        self.funk, self.mac, self.typ, self.mid = funk, mac, typ, mid
        self.seq = 0
        self.fertig = False

    def annehmen(self, a):
        """Gibt die Daten eines neuen Stuecks zurueck, sonst None."""
        if a[:2] != self.typ or len(a) < 6 or a[2] != self.mid:
            return None
        seq = (a[3] << 8) | a[4]
        if seq == self.seq - 1:                   # Quittung ging verloren
            self.funk.senden(self.mac, _quittung(self.mid, seq))
            return None
        if seq != self.seq:
            return None
        self.funk.senden(self.mac, _quittung(self.mid, seq))
        self.seq += 1
        self.fertig = a[5] == 1
        return a[6:]

    def naechstes(self, ms):
        ende = time.ticks_add(time.ticks_ms(), ms)
        while time.ticks_diff(ende, time.ticks_ms()) > 0:
            m, a = self.funk.empfangen(50)
            if a and m == self.mac:
                d = self.annehmen(a)
                if d is not None:
                    return d
        raise OSError("Repeater timeout")


# ---------------------------------------------------------------------
#  Client: steht in Netz.req und spricht wie requests
# ---------------------------------------------------------------------
class _Roh:
    def __init__(self, antwort):
        self.a = antwort

    def read(self, n=-1):
        return self.a.lesen(n)


class Antwort:
    def __init__(self, client, empfang, ms):
        self.c, self.emp = client, empfang
        self.puffer = b""
        kopf = json.loads(empfang.naechstes(ms))
        self.status_code = kopf.get("s", 502)
        self.raw = _Roh(self)
        self._inhalt = None

    def lesen(self, n=-1):
        while not self.emp.fertig and (n < 0 or len(self.puffer) < n):
            self.puffer += self.emp.naechstes(8000)
        if n < 0:
            n = len(self.puffer)
        t, self.puffer = self.puffer[:n], self.puffer[n:]
        return t

    @property
    def content(self):
        if self._inhalt is None:
            self._inhalt = self.lesen()
        return self._inhalt

    @property
    def text(self):
        return self.content.decode()

    def json(self):
        return json.loads(self.content)

    def close(self):
        if not self.emp.fertig:
            self.c.funk.senden(self.c.mac, b"HX" + bytes((self.emp.mid,)))
            self.emp.fertig = True


class RepeaterClient:
    def __init__(self):
        self.funk = None
        self.mac = None
        self.mid = 0

    def verbinden(self, rest=None):
        """Repeater suchen: zuerst der zuletzt benutzte Kanal."""
        merker = {}
        try:
            with open(MERKER) as f:
                merker = json.load(f)
        except (OSError, ValueError):
            pass
        kanaele = list(range(1, 14))
        if merker.get("kanal") in kanaele:
            kanaele.remove(merker["kanal"])
            kanaele.insert(0, merker["kanal"])
        self.funk = Funk(kanaele[0])
        nonce = os.urandom(4)
        for k in kanaele:
            if rest:
                rest()
            self.funk.kanal(k)
            self.funk.senden(BROADCAST, b"HR?" + nonce)
            ende = time.ticks_add(time.ticks_ms(), 150)
            while time.ticks_diff(ende, time.ticks_ms()) > 0:
                m, a = self.funk.empfangen(30)
                if a == b"HR!" + nonce:
                    self.mac = m
                    self.funk.peer(m)
                    if merker.get("kanal") != k:
                        try:
                            os.mkdir(CACHE)
                        except OSError:
                            pass
                        with open(MERKER, "w") as f:
                            json.dump({"kanal": k}, f)
                    return k
        raise OSError("No repeater found")

    def request(self, methode, url, timeout=5, data=None, headers=None):
        self.mid = (self.mid + 1) & 255
        kopf = json.dumps({"m": methode, "u": url, "h": headers or {}}).encode()
        if len(kopf) > STUECK:
            raise OSError("Repeater: request header too long")
        body = data.encode() if isinstance(data, str) else (data or b"")
        try:
            _strom(self.funk, self.mac, b"HQ", self.mid, _stuecke(kopf, body))
        except Abbruch:
            raise OSError("Repeater aborted")
        # Der Repeater braucht selbst bis zu ~8 s fuer HTTPS
        return Antwort(self, _Empfang(self.funk, self.mac, b"HS", self.mid), timeout * 1000 + 9000)

    def beenden(self):
        if self.funk:
            self.funk.aus()
            try:
                self.funk.sta.active(False)
            except Exception:
                pass
        self.funk = None


# ---------------------------------------------------------------------
#  Repeater-Betrieb (Board mit eigenem WLAN)
# ---------------------------------------------------------------------
def _erlaubt(url, konfig):
    for basis in (konfig.get("url"), konfig.get("store")):
        if basis and url.startswith(basis.rstrip("/") + "/"):
            return True
    return False


def _weiterleiten(funk, mac, mid, kopf, body, req, konfig):
    try:
        info = json.loads(kopf)
        url = info["u"]
        if not _erlaubt(url, konfig):
            raise ValueError("URL not allowed")
    except (ValueError, KeyError):
        fehler = json.dumps({"error": "Repeater: request refused"}).encode()
        _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": 403}).encode(), fehler))
        return
    try:
        r = req.request(info.get("m", "GET"), url, timeout=8, data=body or None, headers=info.get("h") or {})
    except Exception:
        fehler = json.dumps({"error": "Repeater: server unreachable"}).encode()
        _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": 502}).encode(), fehler))
        return
    try:
        roh = getattr(r, "raw", None)
        if roh is None:                          # Simulator: alles auf einmal
            _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": r.status_code}).encode(), r.content))
            return
        teile = [json.dumps({"s": r.status_code}).encode()]

        def quelle():
            if teile:
                return teile.pop()
            return roh.read(STUECK) or b""
        _strom(funk, mac, b"HS", mid, quelle)
    finally:
        r.close()


def repeater_betreiben(oled, ein, netz, stopp=None):
    """Bis S4 Anfragen anderer Boards weiterleiten. netz ist verbunden."""
    import hub_apps as ha
    funk = Funk()
    kanal = funk.kanal()
    laufend = {}        # mac -> [_Empfang, kopf, body]
    zaehler = 0
    gezeigt = None
    ein.warte_los()
    try:
        while True:
            if gezeigt != zaehler:
                gezeigt = zaehler
                ha.kopfzeile(oled, "REPEATER", "ch%d" % kanal)
                oled.text("Other boards:", 0, 14, 1)
                oled.text("Set up Wi-Fi >", 0, 24, 1)
                oled.text("Via repeater", 0, 34, 1)
                oled.hline(0, 44, 128, 1)
                oled.text(("%d req  S4=Stop" % zaehler)[:16], 0, 52, 1)
                oled.show()
            if ein.lesen() == "zurueck" or (stopp and stopp()):
                return zaehler
            m, a = funk.empfangen(30)
            if not a:
                continue
            if a[:3] == b"HR?" and len(a) == 7:
                funk.senden(m, b"HR!" + a[3:])
                continue
            if a[:2] != b"HQ" or len(a) < 6:
                continue
            mid, seq = a[2], (a[3] << 8) | a[4]
            z = laufend.get(m)
            if seq == 0 and (z is None or z[0].mid != mid):
                z = laufend[m] = [_Empfang(funk, m, b"HQ", mid), None, b""]
            if z is None:
                continue
            d = z[0].annehmen(a)
            if d is None:
                continue
            if z[1] is None:
                z[1] = d
            else:
                z[2] += d
                if len(z[2]) > 16384:            # kein Board schickt so viel
                    del laufend[m]
                    continue
            if z[0].fertig:
                del laufend[m]
                try:
                    _weiterleiten(funk, m, mid, z[1], z[2], netz.req, netz.k)
                except (OSError, Abbruch):
                    pass
                zaehler += 1
    finally:
        funk.aus()


def repeater_einrichten(oled, ein):
    """'Via repeater': Repeater suchen und die Einstellung speichern."""
    import hub_apps as ha
    ha.meldung(oled, "Searching", "repeater ...", "")
    c = RepeaterClient()
    try:
        kanal = c.verbinden()
    except OSError:
        ha.fehler_dialog(oled, ein, "Repeater", "No repeater found. Start 'Be a repeater' on a board with Wi-Fi.")
        return False
    finally:
        c.beenden()
    config = konfig_lesen() or {"url": "https://esphub-steel.vercel.app", "auth": ""}
    config["modus"] = "repeater"
    _json_schreiben(KONFIG, config)
    ha.meldung(oled, "Repeater found", "channel %d" % kanal, "saved")
    time.sleep_ms(1500)
    return True

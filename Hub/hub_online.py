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


def wlan_einrichten(oled, ein):
    """Explicit, password-protected AP; credentials stay on this board."""
    import network
    import socket
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
        ap.config(essid=ssid, password=password, authmode=3)
        ap.active(True)
        ip = ap.ifconfig()[0]
        choice = ha.menue(oled, ein, "WI-FI SETUP", [ssid, "PW " + password, ip], ["Start", "Cancel"])
        # Show the connection details throughout the five-minute setup window.
        if choice != 0:
            return False
        ha.meldung(oled, ssid, "PW " + password, ip)
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, 80))
        server.listen(1)
        server.settimeout(0.2)
        start = time.ticks_ms()
        ein.warte_los()
        while time.ticks_diff(time.ticks_ms(), start) < 300000:
            if ein.lesen() == "zurueck":
                return False
            try:
                client, address = server.accept()
            except OSError:
                continue
            saved = False
            try:
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
                    config = konfig_lesen() or {"url": "https://esphub-steel.vercel.app", "auth": ""}
                    config.update(wlan=wlan, passwort=pw)
                    # Verify the new network before replacing the old configuration.
                    sta.active(True)
                    sta.connect(wlan, pw)
                    deadline = time.ticks_ms()
                    while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), deadline) < 8000:
                        time.sleep_ms(100)
                    if not sta.isconnected():
                        raise ValueError("Wi-Fi unavailable. Check your details and try again.")
                    _json_schreiben(KONFIG, config)
                    saved = True
                    page = "<h1>Wi-Fi saved</h1><p>The board will restart now.</p>"
                elif method == "GET" and path == "/":
                    page = '<h1>Set up ESP-Hub</h1><form method="post"><input type="hidden" name="csrf" value="' + csrf + '"><label>Wi-Fi name<input name="wlan" maxlength="32" required autocomplete="off"></label><label>Wi-Fi password<input type="password" name="passwort" maxlength="63" autocomplete="new-password"></label><button>Connect and save</button></form><p>Leave the password blank for open Wi-Fi. Press S4 on the board to cancel.</p>'
                else:
                    raise ValueError("Unknown page")
                status = "200 OK"
            except Exception:
                # No request text or submitted password is reflected into HTML/logs.
                page = '<h1>Setup was not saved</h1><p>Check your Wi-Fi details and connection.</p><a href="/">Try again</a>'
                status = "400 Bad Request"
            try:
                body = ('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP-Hub Wi-Fi</title><style>body{font:18px system-ui;max-width:30rem;margin:2rem auto;padding:1rem}label,input,button{display:block;margin:1rem 0}input,button{font:inherit;padding:.6rem;box-sizing:border-box;max-width:100%}</style>' + page).encode()
                client.sendall(('HTTP/1.1 ' + status + '\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nX-Frame-Options: DENY\r\nContent-Security-Policy: default-src \'none\'; style-src \'unsafe-inline\'; form-action \'self\'; frame-ancestors \'none\'\r\nConnection: close\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode() + body)
            except OSError:
                pass
            finally:
                client.close()
            if saved:
                time.sleep_ms(500)
                machine.reset()
                return True
        return False
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

# =====================================================================
#  Speicher fuer den ESP-Hub: lokal + optional online
# =====================================================================
#  Spiele bekommen in der Galerie das Modul "hub" (siehe api()). Alles wird
#  sofort lokal in /hubdaten/<Spiel>.json gespeichert. Ist /hub_online.json
#  vorhanden, gleicht der Hub beim Spielstart und Spielende mit dem
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
WLAN_TIMEOUT_MS = 8000


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
    if not 0 < len(k) <= 40:
        raise ValueError("Schluessel: 1-40 Zeichen")
    for c in k:
        if not (c.isalpha() or c.isdigit() or c in "_-"):
            raise ValueError("Schluessel: nur A-Z, 0-9, _ und -")
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
    os.rename(datei + ".neu", datei)


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
    """Zuletzt geholter App-Katalog: {id: {...}} (leer, wenn nie online)."""
    try:
        with open(KATALOG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------
#  WLAN + HTTP
# ---------------------------------------------------------------------
class Netz:
    def __init__(self, konfig):
        self.k = konfig
        self.sta = None
        self.req = None

    def verbinden(self):
        import network
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        if not self.sta.isconnected():
            self.sta.connect(self.k.get("wlan", ""), self.k.get("passwort", ""))
            start = time.ticks_ms()
            while not self.sta.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > WLAN_TIMEOUT_MS:
                    raise OSError("WLAN nicht erreichbar")
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
        """Fehlermeldung des Servers lesen (z. B. 'Board gesperrt: ...')."""
        try:
            text = r.json().get("error", "")
        except Exception:
            text = ""
        return OSError("%s: %s" % (wer, text) if text else "%s: HTTP %d" % (wer, r.status_code))

    def melden(self, erledigt=None):
        """Beim Vercel-Server anmelden: Hub-Version, Apps, Nutzung, Speicher
        und Pruefsummen der Hub-Dateien. Zurueck kommen Konto und offene
        Auftraege. Andere Server kennen das nicht (404) - dann passiert nichts."""
        import hub_apps
        apps = {n: hub_apps.kopf(n)["version"] for n in hub_apps.apps()}
        pruef = {d: hub_apps.pruefsumme("/" + d) for d in hub_apps.HUB_DATEIEN}
        gc.collect()
        daten = {"nr": board_nr(), "hub": hub_apps.HUB_VERSION, "apps": apps, "pruef": pruef,
                 "nutzung": hub_apps.nutzung_lesen(), "frei": hub_apps.frei(), "ram": gc.mem_free()}
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
        _json_schreiben(BOARD, {"konto": a.get("konto"), "auftraege": a.get("auftraege") or {}})
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
            return self.req.request(methode, url, timeout=8, **kw)
        except TypeError:           # aeltere urequests ohne timeout
            return self.req.request(methode, url, **kw)

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
        r = self._anfrage("GET", self._url(self.k.get("store") or self.k["url"], "apps/" + app["id"]))
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
            raise OSError("Download kaputt")

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
        os.rename(self.datei + ".neu", self.datei)   # nie halb geschriebene Datei

    def offen(self):
        o = self.d["offen"]
        return bool(o["board"] or o["setzen"] or o["plus"] or o["listen"] or o.get("loeschen") is not None)

    def alles_loeschen(self):
        """Spielstand dieses Boards loeschen. Online passiert das beim
        naechsten Abgleich (Board-Daten + eigene Bestenlisten-Eintraege)."""
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
    def abgleichen(self, andere=True):
        """Holen, zusammenfuehren, Ausstehendes hochladen. Blockiert 1-5 s.
        andere=True: auch liegengebliebene Daten anderer Spiele hochladen
        und den App-Katalog (fuer Update-Anzeige) holen."""
        if self.konfig is None:
            return False
        netz = Netz(self.konfig)
        try:
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
                        if d.endswith(".json") and d[:-5] != self.spiel:
                            sp = Speicher(d[:-5])
                            if sp.offen():
                                sp._abgleich(netz)
                except Exception as e:
                    print("Hub online (andere Spiele):", e)
            return True
        except Exception as e:
            print("Hub online:", e)
            self.status = "gesperrt" if "gesperrt" in str(e) else "offline"
            return False
        finally:
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
                print("Hub online: Speicherlimit erreicht")
                d["voll"] = True
            o["board"] = []
        if o["setzen"] or o["plus"]:
            p = dict(o["setzen"])
            for k, n in o["plus"].items():
                p[k] = {".sv": {"increment": n}}
            netz.http("PATCH", basis + "global", p)
            o["setzen"] = {}
            o["plus"] = {}
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
            """Sofort abgleichen. Blockiert 1-5 s und schaltet WLAN kurz
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
        return False, "keine Konfig"
    netz = Netz(k)
    try:
        netz.verbinden()
        netz.melden()
        netz.http("GET", "_ping")
        return True, "Verbindung OK"
    except Exception as e:
        return False, str(e)[:32]
    finally:
        netz.trennen()

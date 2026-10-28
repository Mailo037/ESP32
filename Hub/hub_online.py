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
            "offen": {"board": [], "setzen": {}, "plus": {}, "listen": []}}


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

    def http(self, methode, pfad, daten=None):
        url = self.k["url"].rstrip("/") + "/esphub/" + pfad + ".json"
        if self.k.get("auth"):
            url += "?auth=" + self.k["auth"]
        body = None if daten is None else json.dumps(daten)
        kw = {"data": body, "headers": {"Content-Type": "application/json"}}
        try:
            r = self.req.request(methode, url, timeout=6, **kw)
        except TypeError:           # aeltere urequests ohne timeout
            r = self.req.request(methode, url, **kw)
        try:
            if r.status_code >= 300:
                raise OSError("HTTP %d" % r.status_code)
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
        return bool(o["board"] or o["setzen"] or o["plus"] or o["listen"])

    # ---- Abgleich ----------------------------------------------------
    def abgleichen(self, andere=True):
        """Holen, zusammenfuehren, Ausstehendes hochladen. Blockiert 1-5 s.
        andere=True: auch liegengebliebene Daten anderer Spiele hochladen."""
        if self.konfig is None:
            return False
        netz = Netz(self.konfig)
        try:
            netz.verbinden()
            self._abgleich(netz)
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
            self.status = "offline"
            return False
        finally:
            netz.trennen()

    def _abgleich(self, netz):
        try:
            self._holen(netz)
            self._senden(netz)
            self.status = "online"
        finally:
            try:
                self.schreiben()
            except OSError:
                pass

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
            netz.http("PATCH", basis + "boards/" + self.id,
                      {k: d["board"].get(k) for k in o["board"]})
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

        class Hub:
            pass
        m = Hub()

        def laden(k, standard=None):
            return d["board"].get(_schluessel(k), standard)

        def speichern(k, wert):
            k = _schluessel(k)
            alt = d["board"].get(k)
            d["board"][k] = wert
            if len(json.dumps(d["board"])) > MAX_BYTES:
                d["board"][k] = alt
                raise ValueError("hub: mehr als %d Bytes" % MAX_BYTES)
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
        netz.http("GET", "_ping")
        return True, "Verbindung OK"
    except Exception as e:
        return False, str(e)[:32]
    finally:
        netz.trennen()

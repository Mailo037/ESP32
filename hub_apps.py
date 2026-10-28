# =====================================================================
#  ESP-Hub: Apps verwalten + Bedienelemente (Menue, Rueckfrage)
# =====================================================================
#  Wird von main.py (auch waehrend ein Spiel laeuft) und der Galerie
#  benutzt. Spiele koennen dieses Modul nicht importieren (Sandbox).
#
#  Kopfzeilen einer App (ganz oben in gal_<Name>.py, alle optional):
#    # HUB-NAME: Geometry Dash
#    # HUB-VERSION: 1.2
#    # HUB-INFO: Wuerfel-Springspiel mit 3 Leveln
# =====================================================================
import json
import os
import time
from machine import Pin, ADC

with open("/hub_version.json") as _version:
    HUB_VERSION = json.load(_version)["version"]
PRAEFIX = "gal_"
DATEN = "/daten"
CACHE = "/hubdaten"
NUTZUNG = CACHE + "/_nutzung.json"
INSTALLIERT = CACHE + "/_installiert.json"   # Pruefsummen vertrauenswuerdiger Apps
PAKETE = "/apps"
HUB_DATEIEN = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")
TASTEN_AKTIV_HIGH = True
AN = 1 if TASTEN_AKTIV_HIGH else 0


# ---------------------------------------------------------------------
#  Apps
# ---------------------------------------------------------------------
def apps():
    l = [d[len(PRAEFIX):-3] for d in os.listdir("/")
         if d.startswith(PRAEFIX) and d.endswith(".py")]
    try:
        for n in os.listdir(PAKETE):
            if gueltige_id(n) and groesse(PAKETE + "/" + n + "/main.py"):
                l.append(n)
    except OSError:
        pass
    return sorted(set(l), key=lambda n: anzeigename(n).lower())


def datei(name):
    paket = PAKETE + "/" + name + "/main.py"
    if groesse(paket):
        return paket
    return "/" + PRAEFIX + name + ".py"


def gueltige_id(name):
    return 0 < len(name) <= 40 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_" for c in name)


def paketpfad(name):
    if not gueltige_id(name):
        raise ValueError("App-ID ungueltig")
    return PAKETE + "/" + name


def pakete_retten():
    try:
        names = os.listdir(PAKETE)
    except OSError:
        return
    for n in names:
        if n.startswith(".alt_") and gueltige_id(n[5:]):
            target = paketpfad(n[5:])
            if groesse(target + "/main.py"):
                loeschen(PAKETE + "/" + n)
            else:
                os.rename(PAKETE + "/" + n, target)


def anzeigename(name):
    return name.replace("_", " ")


def kopf(name):
    """HUB-Kopfzeilen lesen, ohne das Spiel zu starten."""
    k = {"name": anzeigename(name), "version": "", "info": ""}
    try:
        with open(datei(name)) as f:
            for _ in range(40):
                z = f.readline()
                if not z:
                    break
                z = z.strip()
                if z.startswith("# HUB-") and ":" in z:
                    schl, _, wert = z[6:].partition(":")
                    schl = schl.strip().lower()
                    if schl in k:
                        k[schl] = wert.strip()
    except OSError:
        pass
    return k


def version_tupel(v):
    t = []
    for teil in str(v).split("."):
        z = ""
        for c in teil:
            if not c.isdigit():
                break
            z += c
        t.append(int(z) if z else 0)
    return tuple(t)


def neuer(online, lokal):
    """True, wenn Version 'online' neuer ist als 'lokal'."""
    return bool(online) and version_tupel(online) > version_tupel(lokal)


# ---------------------------------------------------------------------
#  Vertrauen: Apps aus Store, Konto oder Repo-Installer (Pruefsumme passt)
#  bekommen Hub-Dienste und Updates. Selbst hochgeladene oder veraenderte
#  Dateien laufen weiter, aber als "lokal".
# ---------------------------------------------------------------------
def pruefsumme(pfad):
    import hashlib
    import binascii
    h = hashlib.sha256()
    try:
        with open(pfad, "rb") as f:
            while True:
                b = f.read(1024)
                if not b:
                    break
                h.update(b)
    except OSError:
        return ""
    return binascii.hexlify(h.digest()).decode()


def installiert_lesen():
    try:
        with open(INSTALLIERT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def installiert_merken(name, sha):
    alle = installiert_lesen()
    if sha:
        alle[name] = sha
    else:
        alle.pop(name, None)
    try:
        os.mkdir(CACHE)
    except OSError:
        pass
    with open(INSTALLIERT, "w") as f:
        json.dump(alle, f)


def vertraut(name, sha=None):
    sha = sha or pruefsumme(datei(name))
    if not sha:
        return False
    if datei(name).startswith(PAKETE + "/"):
        try:
            with open(paketpfad(name) + "/manifest.json") as f:
                meta = json.load(f)
            if any(pruefsumme(paketpfad(name) + "/" + d["name"]) != d["sha256"] for d in meta["dateien"]):
                return False
        except (OSError, ValueError, KeyError):
            return False
    if installiert_lesen().get(name) == sha:
        return True
    try:
        import hub_online
        a = hub_online.katalog_lokal().get(name)
    except Exception:
        a = None
    return bool(a and a.get("sha256") == sha)


# ---------------------------------------------------------------------
#  Speicher
# ---------------------------------------------------------------------
def groesse(pfad):
    """Bytes einer Datei oder eines ganzen Ordners."""
    try:
        st = os.stat(pfad)
    except OSError:
        return 0
    if st[0] & 0x4000:
        return sum(groesse(pfad + "/" + n) for n in os.listdir(pfad))
    return st[6]


def app_groessen(name):
    """(App, Spielstand) in Bytes."""
    code = groesse(paketpfad(name)) if datei(name).startswith(PAKETE + "/") else groesse(datei(name))
    return code, groesse(DATEN + "/" + name) + groesse(CACHE + "/" + name + ".json")


def frei():
    try:
        s = os.statvfs("/")
        return s[0] * s[3]
    except (OSError, AttributeError):
        return 0


def kb(n):
    if n >= 10 * 1048576:
        return "%dM" % (n // 1048576)
    if n >= 1000 * 1024:
        return "%d.%dM" % (n // 1048576, n % 1048576 * 10 // 1048576)
    return "%dK" % ((n + 1023) // 1024)


def loeschen(pfad):
    """Datei oder Ordner (rekursiv) entfernen."""
    try:
        st = os.stat(pfad)
    except OSError:
        return
    if st[0] & 0x4000:
        for n in os.listdir(pfad):
            loeschen(pfad + "/" + n)
        os.rmdir(pfad)
    else:
        os.remove(pfad)


def daten_loeschen(name, speicher=None):
    """Eigenen Spielstand loeschen: lokal sofort, online beim naechsten
    Abgleich (nur die Eintraege dieses Boards)."""
    loeschen(DATEN + "/" + name)
    if speicher is None:
        import hub_online
        speicher = hub_online.Speicher(name)
    speicher.alles_loeschen()


def app_loeschen(name):
    """Deinstallieren. Der Online-Spielstand bleibt - nach einer
    Neuinstallation ist er wieder da."""
    loeschen(datei(name))
    loeschen(paketpfad(name))
    loeschen("/" + PRAEFIX + name + ".py")
    loeschen(DATEN + "/" + name)
    installiert_merken(name, None)


def nutzung_lesen():
    try:
        with open(NUTZUNG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def nutzung_merken(name, n):
    alle = nutzung_lesen()
    if alle.get(name) == n:
        return
    alle[name] = n
    try:
        os.mkdir(CACHE)
    except OSError:
        pass
    with open(NUTZUNG, "w") as f:
        json.dump(alle, f)


def nutzung_text(n):
    """'Hub,Funk' usw. - welche Dienste die App benutzt (Hub = Online-
    Speicher, Web = eigene HTTP-Anfragen, Funk = WLAN/ESP-NOW)."""
    if n is None:
        return "?"
    t = [k for k, an in (("Hub", n.get("hub")), ("Web", n.get("web")), ("Funk", n.get("funk"))) if an]
    return ",".join(t) if t else "keine"


def info_zeilen(name, k=None, nutzung=None, lokal=False):
    k = k or kopf(name)
    a, d = app_groessen(name)
    if nutzung is None:
        nutzung = nutzung_lesen().get(name)
    return [("v" + k["version"] if k["version"] else "v?") + ("  lokal" if lokal else "") + " " + kb(a),
            "Daten %s %s" % (kb(d) if d else "0K", nutzung_text(nutzung))]


# ---------------------------------------------------------------------
#  Bedienung
# ---------------------------------------------------------------------
def oled_neu():
    from machine import I2C
    from ssd1306 import SSD1306_I2C
    return SSD1306_I2C(128, 64, I2C(0, scl=Pin(22), sda=Pin(21), freq=400000))


class Eingabe:
    """Taster + Joystick zu Ereignissen: hoch, runter, ok, zurueck."""
    TOT = 12000

    def __init__(self, x0=32768, y0=32768):
        self.s17, self.s16 = Pin(17, Pin.IN), Pin(16, Pin.IN)
        self.s5, self.s4, self.sj = Pin(5, Pin.IN), Pin(4, Pin.IN), Pin(2, Pin.IN)
        self.jx, self.jy = ADC(Pin(34)), ADC(Pin(35))
        for a in (self.jx, self.jy):
            try:
                a.atten(ADC.ATTN_11DB)
            except Exception:
                pass
        self.x0, self.y0 = x0, y0
        self.alt = ()
        self.wdh = 0

    def gedrueckt(self):
        jy = self.jy.read_u16() - self.y0
        jx = self.jx.read_u16() - self.x0
        g = []
        if self.s17.value() == AN or jy > self.TOT:
            g.append("hoch")
        if self.s16.value() == AN or jy < -self.TOT:
            g.append("runter")
        if self.s5.value() == AN or self.sj.value() == AN or jx > self.TOT * 2:
            g.append("ok")
        if self.s4.value() == AN or jx < -self.TOT * 2:
            g.append("zurueck")
        return g

    def lesen(self):
        g = self.gedrueckt()
        jetzt = time.ticks_ms()
        e = None
        for k in g:
            if k not in self.alt:
                e = k
                self.wdh = time.ticks_add(jetzt, 380)
                break
        else:
            for k in ("hoch", "runter"):
                if k in g and time.ticks_diff(jetzt, self.wdh) >= 0:
                    e = k
                    self.wdh = time.ticks_add(jetzt, 140)
        self.alt = g
        return e

    def warte_los(self):
        while self.gedrueckt():
            time.sleep_ms(20)
        self.alt = ()


def kopfzeile(oled, text, rechts=""):
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 10, 1)
    oled.text(text[:16], 1, 1, 0)
    if rechts:
        oled.text(rechts, 127 - 8 * len(rechts), 1, 0)


def menue(oled, ein, titel, zeilen, punkte, wahl=0):
    """Auswahlliste. Rueckgabe: Index oder -1 (S4 = zurueck)."""
    y0 = 12 + 9 * len(zeilen) + (2 if zeilen else 0)
    sichtbar = max(1, (64 - y0) // 9)
    oben = 0
    ein.warte_los()
    neu = True
    while True:
        if neu:
            oben = min(max(oben, wahl - sichtbar + 1), wahl)
            kopfzeile(oled, titel)
            for i, z in enumerate(zeilen):
                oled.text(z[:16], 0, 12 + 9 * i, 1)
            if zeilen:
                oled.hline(0, y0 - 2, 128, 1)
            for i in range(sichtbar):
                n = oben + i
                if n >= len(punkte):
                    break
                y = y0 + 9 * i
                if n == wahl:
                    oled.fill_rect(0, y - 1, 128, 9, 1)
                oled.text(punkte[n][:16], 2, y, 0 if n == wahl else 1)
            oled.show()
            neu = False
        e = ein.lesen()
        if e == "hoch":
            wahl = (wahl - 1) % len(punkte)
            neu = True
        elif e == "runter":
            wahl = (wahl + 1) % len(punkte)
            neu = True
        elif e == "ok":
            ein.warte_los()
            return wahl
        elif e == "zurueck":
            ein.warte_los()
            return -1
        time.sleep_ms(15)


def frage(oled, ein, titel, z1, z2=""):
    kopfzeile(oled, titel)
    oled.text(z1[:16], 0, 18, 1)
    oled.text(z2[:16], 0, 28, 1)
    oled.hline(0, 44, 128, 1)
    oled.text("S5=Ja  S4=Nein", 8, 52, 1)
    oled.show()
    ein.warte_los()
    while True:
        e = ein.lesen()
        if e in ("ok", "zurueck"):
            ein.warte_los()
            return e == "ok"
        time.sleep_ms(15)


def meldung(oled, z1, z2="", z3=""):
    oled.fill(0)
    for i, z in enumerate((z1, z2, z3)):
        if z:
            oled.text(z[:16], 64 - 4 * len(z[:16]), 16 + 12 * i, 1)
    oled.show()


def balken(oled, y, anteil):
    oled.rect(8, y, 112, 8, 1)
    oled.fill_rect(10, y + 2, int(108 * min(1, anteil)), 4, 1)
    oled.show()

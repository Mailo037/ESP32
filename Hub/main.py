# =====================================================================
#  ESP-HUB v2.0 - Spiele-Galerie mit App-Store fuer das BZTG espBoard
# =====================================================================
#  Auf dem Board liegt nur dieser Hub als main.py. Jedes Spiel ist eine
#  eigene Datei "gal_<Name>.py" - neue Spiele kommen per Hochladen oder
#  aus dem App-Store dazu.
#
#  GALERIE (hub_galerie.py)
#    Joystick hoch/runter (oder S17/S16) : auswaehlen
#    S5 (oder Joystick rechts / Joystick-Taster) : starten / oeffnen
#    S4 : App-Menue (Version, Speicher, Update, loeschen, deinstallieren)
#  IM SPIEL
#    S4 + S16 halten : App-Menue (Spiel pausiert)
#    S4 + S5  halten : Spiel sofort beenden, zurueck zur Galerie
#  Poti RP3 (links oben)  : Lautstaerke (ganz links = stumm)
#
#  SANDBOX - jedes Spiel laeuft abgeschottet vom Hub:
#    * frischer Interpreter (Soft-Reset vor und nach jedem Spiel)
#    * eigener Namensraum: das Spiel sieht keine Variablen des Hubs
#    * Dateien: open() und os.* zeigen nur in /daten/<Spiel>/
#    * die Hub-Module sind gesperrt, Spiele bekommen nur "import hub"
#  Schutz gegen Versehen, kein Schutz gegen absichtlich boesen Code
#  (MicroPython kennt keine echte Prozess-Trennung).
#
#  Dateien: main.py, hub_apps.py, hub_galerie.py, hub_online.py, ssd1306.py
# =====================================================================
import gc
import os
import sys
import machine
import time
from machine import Pin
import hub_apps
import hub_online

VERSION = hub_apps.HUB_VERSION
START_DATEI = "/hub_start.txt"      # welches Spiel nach dem Reset laeuft
HALTEN_MS = 400                     # so lange S4+S5 / S4+S16 halten
AN = hub_apps.AN

_open = open
_os = os
_zeit = time


def neustart():
    """Soft-Reset: alles weg, main.py (der Hub) startet neu."""
    getattr(machine, "soft_reset", machine.reset)()


def lies(datei):
    try:
        with open(datei) as f:
            return f.read().strip()
    except OSError:
        return ""


def schreibe(datei, text):
    with open(datei, "w") as f:
        f.write(text)


def ordner_anlegen(pfad):
    teil = ""
    for t in pfad.strip("/").split("/"):
        teil += "/" + t
        try:
            os.mkdir(teil)
        except OSError:
            pass


# =====================================================================
#  SANDBOX
# =====================================================================
class ZurGalerie(BaseException):
    """Spiel beenden. Erbt nicht von Exception, damit ein
    "except Exception:" im Spiel sie nicht verschluckt."""


class _Modul:
    pass


class _Sandbox:
    def __init__(self, name, speicher):
        self.name = name
        self.speicher = speicher
        self.basis = hub_apps.DATEN + "/" + name
        ordner_anlegen(self.basis)
        self.s4, self.s5, self.s16 = Pin(4, Pin.IN), Pin(5, Pin.IN), Pin(16, Pin.IN)
        self.naechst = _zeit.ticks_ms()
        self.seit = None
        self.combo = None
        self.abbruch = 0
        self.aktion = None          # nach dem Spiel: "ende" / "daten" / "deinstall"
        self.pause_ms = 0           # Zeit im Menue - wird dem Spiel verschwiegen
        self.oled = None            # das Display-Objekt des Spiels
        self.module_vorher = set()

    # ---- Dateien: alles landet in /daten/<Spiel>/ -------------------
    def pfad(self, p):
        teile = [t for t in str(p).split("/") if t not in ("", ".")]
        if ".." in teile:
            raise OSError(1)        # EPERM: raus aus der Sandbox geht nicht
        return self.basis + ("/" + "/".join(teile) if teile else "")

    def oeffnen(self, p, *a, **k):
        return _open(self.pfad(p), *a, **k)

    def os_modul(self):
        m = _Modul()
        pf = self.pfad
        m.sep = "/"
        m.listdir = lambda p="": _os.listdir(pf(p))
        m.ilistdir = lambda p="": _os.ilistdir(pf(p))
        m.stat = lambda p: _os.stat(pf(p))
        m.remove = lambda p: _os.remove(pf(p))
        m.rename = lambda a, b: _os.rename(pf(a), pf(b))
        m.mkdir = lambda p: _os.mkdir(pf(p))
        m.rmdir = lambda p: _os.rmdir(pf(p))
        m.getcwd = lambda: "/"
        m.chdir = lambda p: pf(p) and None
        for n in ("uname", "urandom", "statvfs", "sync"):
            if hasattr(_os, n):
                setattr(m, n, getattr(_os, n))
        return m

    # ---- Tastenkombinationen -----------------------------------------
    # Alle Spiele fragen pro Bild die Zeit ab. Deshalb steckt die
    # Pruefung in ticks_ms/sleep_ms - hoechstens alle 40 ms ein Blick
    # auf die Taster, das kostet praktisch keine Rechenzeit.
    def wache(self):
        t = _zeit.ticks_ms()
        if self.abbruch:
            # Spiel laeuft nach ZurGalerie weiter: ein "finally:" darf noch
            # kurz aufraeumen, ein verschluckendes "except:" nicht ewig
            if _zeit.ticks_diff(t, self.abbruch) > 1000:
                machine.reset()
            raise ZurGalerie()
        if _zeit.ticks_diff(t, self.naechst) < 0:
            return
        self.naechst = _zeit.ticks_add(t, 40)
        combo = None
        if self.s4.value() == AN:
            if self.s5.value() == AN:
                combo = "ende"
            elif self.s16.value() == AN:
                combo = "menue"
        if combo is None or combo != self.combo:
            self.combo, self.seit = combo, t
            return
        if _zeit.ticks_diff(t, self.seit) < HALTEN_MS:
            return
        self.combo = None
        if combo == "menue":
            self.menue()
            if self.aktion is None:
                return
        self.abbruch = _zeit.ticks_ms() or 1
        raise ZurGalerie()

    def menue(self):
        """App-Menue mitten im Spiel. Das Spiel steht still; danach wird
        sein Bild wiederhergestellt und die Pause aus der Zeit gerechnet."""
        start = _zeit.ticks_ms()
        try:
            from machine import PWM
            PWM(Pin(15)).duty_u16(0)            # Summer still
        except Exception:
            pass
        oled = self.oled
        bild = inv = None
        if oled is not None:
            bild = bytes(oled.buffer)
            inv = getattr(oled, "invertiert", None)
            try:
                oled.invert(0)
            except Exception:
                pass
        else:
            oled = hub_apps.oled_neu()
        ein = hub_apps.Eingabe()
        k = hub_apps.kopf(self.name)
        zeilen = hub_apps.info_zeilen(self.name, k, self.nutzung(), lokal="hub" not in sys.modules)
        while True:
            w = hub_apps.menue(oled, ein, k["name"], zeilen,
                               ["Weiter", "Schliessen", "Daten loeschen", "Deinstallieren"])
            if w in (-1, 0):
                break
            if w == 1:
                self.aktion = "ende"
                break
            if w == 2 and hub_apps.frage(oled, ein, "SPIELSTAND", "Deinen Spiel-", "stand loeschen?"):
                self.aktion = "daten"
                break
            if w == 3 and hub_apps.frage(oled, ein, "DEINSTALLIEREN", k["name"], "entfernen?"):
                self.aktion = "deinstall"
                break
        if self.aktion is None and bild is not None:
            oled.buffer[:] = bild
            if inv is not None and inv >= 0:
                oled.invertiert = -1
                oled.invert(inv)
            oled.show()
        ein.warte_los()
        self.pause_ms += _zeit.ticks_diff(_zeit.ticks_ms(), start)

    def nutzung(self):
        # Eingebaute Module (espnow, socket) stehen auf dem ESP32 nicht in
        # sys.modules - Funk erkennt man daran, dass das WLAN-Modul an ist
        # (der Hub schaltet es vor dem Spiel aus)
        try:
            import network
            funk = network.WLAN(network.STA_IF).active() or network.WLAN(network.AP_IF).active()
        except Exception:
            funk = False
        web = any(n in sys.modules and n not in self.module_vorher for n in ("requests", "urequests"))
        return {"hub": self.speicher.benutzt, "funk": bool(funk), "web": web}

    def zeit_modul(self):
        m = _Modul()
        for n in dir(_zeit):
            if not n.startswith("__"):
                setattr(m, n, getattr(_zeit, n))
        w = self.wache
        sb = self
        tms = _zeit.ticks_ms
        tus = getattr(_zeit, "ticks_us", None)
        sms = _zeit.sleep_ms
        tadd = _zeit.ticks_add

        def ticks_ms():
            w()
            return tadd(tms(), -sb.pause_ms)

        def sleep_ms(ms):
            # lange Pausen in Haeppchen, damit die Tasten sofort wirken
            while ms > 50:
                w()
                sms(50)
                ms -= 50
            w()
            if ms > 0:
                sms(int(ms))

        m.ticks_ms = ticks_ms
        m.sleep_ms = sleep_ms
        m.sleep = lambda s: sleep_ms(s * 1000)
        if tus:
            def ticks_us():
                w()
                return tadd(tus(), -sb.pause_ms * 1000)
            m.ticks_us = ticks_us
        return m

    def display_merken(self):
        """Das Display-Objekt des Spiels merken (fuer das App-Menue)."""
        try:
            import ssd1306
        except ImportError:
            return
        sb = self
        alt = ssd1306.SSD1306.__init__

        def init(o, *a, **k):
            sb.oled = o
            alt(o, *a, **k)
        ssd1306.SSD1306.__init__ = init

    def einrichten(self, hub_api):
        self.module_vorher = set(sys.modules)     # was das Spiel selbst laedt, zaehlt
        self.display_merken()
        z = self.zeit_modul()
        o = self.os_modul()
        gesperrt = _Modul()
        self.vorher = {}
        for n, m in (("time", z), ("utime", z), ("os", o), ("uos", o), ("hub", hub_api),
                     ("main", gesperrt), ("hub_online", gesperrt), ("hub_apps", gesperrt),
                     ("hub_galerie", gesperrt)):
            self.vorher[n] = sys.modules.get(n)
            if m is None:
                sys.modules.pop(n, None)    # lokale App: "import hub" schlaegt fehl
            else:
                sys.modules[n] = m

    def aufraeumen(self):
        for n, m in self.vorher.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


def spiel_starten(name):
    datei = hub_apps.datei(name)
    print("ESP-Hub: starte", datei)
    # Nur Apps aus Store, Konto oder Repo (Pruefsumme passt) bekommen
    # Hub-Dienste. Selbst aufgespielte/veraenderte Apps laufen "lokal".
    vertraut = hub_apps.vertraut(name)
    speicher = hub_online.Speicher(name)
    sb = _Sandbox(name, speicher)
    if not vertraut:
        print("ESP-Hub: lokale App - ohne Hub-Dienste")
        speicher.konfig = None
    if speicher.konfig:
        meldung("Online-Daten", "laden ...")
        speicher.abgleichen()
    g = {"__name__": "__main__", "__file__": datei, "open": sb.oeffnen}
    fehler = None
    try:
        # Datei in einem Stueck lesen (kein Nachwachsen des Puffers) und
        # den Quelltext vor dem Start freigeben - spart RAM bei grossen Spielen
        with _open(datei) as f:
            quelle = f.read(_os.stat(datei)[6])
        try:
            code = compile(quelle, datei, "exec")
            quelle = None
        except NameError:          # Firmware ohne compile()
            code = quelle
        gc.collect()
        sb.einrichten(speicher.api() if vertraut else None)
        exec(code, g)
    except ZurGalerie:
        print("ESP-Hub: zurueck zur Galerie")
    except SystemExit:
        pass
    except KeyboardInterrupt:
        raise                       # Strg+C in Thonny -> REPL
    except BaseException as e:
        fehler = e
        sys.print_exception(e)
    nutzung = sb.nutzung()
    g = code = None
    sb.aufraeumen()
    gc.collect()
    hub_apps.nutzung_merken(name, nutzung)
    if sb.aktion == "daten":
        hub_apps.daten_loeschen(name, speicher)
        schreibe(START_DATEI, name)          # Spiel frisch neu starten
    elif sb.aktion == "deinstall":
        hub_apps.app_loeschen(name)
    if speicher.konfig and speicher.offen():
        meldung("Speichere", "online ...")
        speicher.abgleichen()
    if fehler is not None:
        fehler_zeigen(name, fehler)
    neustart()


def meldung(z1, z2):
    try:
        hub_apps.meldung(hub_apps.oled_neu(), z1, z2)
    except Exception:
        pass


def fehler_zeigen(name, e):
    """Absturz anzeigen, mit S5 zurueck zur Galerie."""
    try:
        oled = hub_apps.oled_neu()
        hub_apps.kopfzeile(oled, "FEHLER")
        oled.text(hub_apps.anzeigename(name)[:16], 0, 13, 1)
        text = "%s: %s" % (type(e).__name__, e)
        for i in range(3):
            oled.text(text[i * 16:(i + 1) * 16], 0, 25 + i * 9, 1)
        oled.text("S5 = Galerie", 16, 56, 1)
        oled.show()
    except Exception:
        pass
    s5 = Pin(5, Pin.IN)
    while s5.value() == AN:
        _zeit.sleep_ms(20)
    while s5.value() != AN:
        _zeit.sleep_ms(20)


# =====================================================================
#  START
# =====================================================================
def main():
    name = lies(START_DATEI)
    if name:
        # Startauftrag sofort loeschen: stuerzt das Spiel ab oder wird
        # das Board neu gestartet, kommt man in der Galerie raus
        try:
            os.remove(START_DATEI)
        except OSError:
            pass
        if name in hub_apps.apps():
            spiel_starten(name)
            return
    import hub_galerie
    hub_galerie.galerie(START_DATEI, neustart)


main()

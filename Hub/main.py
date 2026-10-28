# =====================================================================
#  ESP-HUB v1.0 - Spiele-Galerie fuer das BZTG espBoard
# =====================================================================
#  Statt fuer jedes Spiel main.py zu ersetzen, liegt auf dem Board nur
#  noch dieser Hub als main.py. Jedes Spiel ist eine eigene Datei mit
#  dem Praefix "gal_", z. B.  gal_ESP_Pong.py  ->  "ESP Pong".
#  Neues Spiel = neue gal_-Datei hochladen, fertig.
#
#  GALERIE
#    Joystick hoch/runter (oder S17/S16) : Spiel auswaehlen
#    S5 (oder Joystick rechts / Joystick-Taster) : Spiel starten
#  IM SPIEL
#    S4 + S5 zusammen halten : Spiel sofort beenden, zurueck zur Galerie
#  Poti RP3 (links oben)  : Lautstaerke (ganz links = stumm)
#
#  SANDBOX - jedes Spiel laeuft abgeschottet vom Hub:
#    * frischer Interpreter (Soft-Reset vor und nach jedem Spiel)
#    * eigener Namensraum: das Spiel sieht keine Variablen des Hubs
#    * Dateien: open() und os.* zeigen nur in /daten/<Spiel>/ -
#      main.py, boot.py und die gal_-Dateien sind fuer Spiele unsichtbar
#    * "import main" ist gesperrt
#  Schutz gegen Versehen, kein Schutz gegen absichtlich boesen Code
#  (MicroPython kennt keine echte Prozess-Trennung).
# =====================================================================
import gc
import os
import sys
import machine
import time
from machine import Pin

VERSION = "v1.0"
PRAEFIX = "gal_"
START_DATEI = "/hub_start.txt"      # welches Spiel nach dem Reset laeuft
ZULETZT_DATEI = "/hub_zuletzt.txt"  # Galerie merkt sich die Auswahl
DATEN_ORDNER = "/daten"
ZURUECK_HALTEN_MS = 400             # so lange S4 + S5 halten
TASTEN_AKTIV_HIGH = True            # Taster liefern gedrueckt 3,3 V
AN = 1 if TASTEN_AKTIV_HIGH else 0

_open = open
_os = os
_zeit = time


def neustart():
    """Soft-Reset: alles weg, main.py (der Hub) startet neu."""
    getattr(machine, "soft_reset", machine.reset)()


def spiele():
    namen = []
    for d in os.listdir("/"):
        if d.startswith(PRAEFIX) and d.endswith(".py"):
            namen.append(d[len(PRAEFIX):-3])
    namen.sort()
    return namen


def anzeigename(name):
    return name.replace("_", " ")


def lies(datei):
    try:
        with open(datei) as f:
            return f.read().strip()
    except OSError:
        return ""


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
    """S4 + S5 gehalten. Erbt nicht von Exception, damit ein
    "except Exception:" im Spiel sie nicht verschluckt."""


class _Modul:
    pass


class _Sandbox:
    def __init__(self, name):
        self.basis = DATEN_ORDNER + "/" + name
        ordner_anlegen(self.basis)
        self.s4 = Pin(4, Pin.IN)
        self.s5 = Pin(5, Pin.IN)
        self.naechst = _zeit.ticks_ms()
        self.seit = None
        self.abbruch = 0

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

    # ---- S4 + S5 beendet das Spiel -----------------------------------
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
        if self.s4.value() == AN and self.s5.value() == AN:
            if self.seit is None:
                self.seit = t
            elif _zeit.ticks_diff(t, self.seit) >= ZURUECK_HALTEN_MS:
                self.abbruch = t or 1
                raise ZurGalerie()
        else:
            self.seit = None

    def zeit_modul(self):
        m = _Modul()
        for n in dir(_zeit):
            if not n.startswith("__"):
                setattr(m, n, getattr(_zeit, n))
        w = self.wache
        tms = _zeit.ticks_ms
        tus = getattr(_zeit, "ticks_us", None)
        sms = _zeit.sleep_ms

        def ticks_ms():
            w()
            return tms()

        def sleep_ms(ms):
            # lange Pausen in Haeppchen, damit S4 + S5 sofort wirkt
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
                return tus()
            m.ticks_us = ticks_us
        return m

    def einrichten(self):
        z = self.zeit_modul()
        o = self.os_modul()
        gesperrt = _Modul()
        for n, m in (("time", z), ("utime", z), ("os", o), ("uos", o),
                     ("main", gesperrt), ("hub", gesperrt)):
            sys.modules[n] = m


def spiel_starten(name):
    datei = PRAEFIX + name + ".py"
    print("ESP-Hub: starte", datei)
    sb = _Sandbox(name)
    g = {"__name__": "__main__", "__file__": datei, "open": sb.oeffnen}
    fehler = None
    try:
        # Datei in einem Stueck lesen (kein Nachwachsen des Puffers) und
        # den Quelltext vor dem Start freigeben - spart RAM bei grossen Spielen
        with _open("/" + datei) as f:
            quelle = f.read(_os.stat("/" + datei)[6])
        try:
            code = compile(quelle, datei, "exec")
            quelle = None
        except NameError:          # Firmware ohne compile()
            code = quelle
        gc.collect()
        sb.einrichten()
        exec(code, g)
    except ZurGalerie:
        print("ESP-Hub: S4+S5 - zurueck zur Galerie")
    except SystemExit:
        pass
    except KeyboardInterrupt:
        raise                       # Strg+C in Thonny -> REPL
    except BaseException as e:
        fehler = e
        sys.print_exception(e)
    g = code = None
    gc.collect()
    if fehler is not None:
        fehler_zeigen(name, fehler)
    neustart()


def fehler_zeigen(name, e):
    """Absturz anzeigen, mit S5 zurueck zur Galerie."""
    try:
        oled = _oled()
        oled.fill(0)
        oled.fill_rect(0, 0, 128, 10, 1)
        oled.text("FEHLER", 40, 1, 0)
        oled.text(anzeigename(name)[:16], 0, 13, 1)
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


def _oled():
    from machine import I2C
    from ssd1306 import SSD1306_I2C
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
    return SSD1306_I2C(128, 64, i2c)


# =====================================================================
#  GALERIE
# =====================================================================
LED_PINS = (13, 12, 14, 27, 26, 25, 33, 32)   # P7 ... P0
ZEILEN = 4
ZEILE_Y = 12
ZEILE_H = 10
TOTZONE = 9000


def galerie():
    from machine import ADC, PWM
    for p in LED_PINS + (19, 23, 18):
        Pin(p, Pin.OUT, value=0)
    try:
        summer = PWM(Pin(15), freq=2000, duty_u16=0)
    except Exception:
        summer = None
    poti = ADC(Pin(39))
    joy_x = ADC(Pin(34))
    joy_y = ADC(Pin(35))
    for a in (poti, joy_x, joy_y):
        try:
            a.atten(ADC.ATTN_11DB)
        except Exception:
            pass
    s17, s16 = Pin(17, Pin.IN), Pin(16, Pin.IN)
    s5, s4, sj = Pin(5, Pin.IN), Pin(4, Pin.IN), Pin(2, Pin.IN)
    oled = _oled()

    def piep(f, ms=18):
        w = poti.read_u16()
        if summer is None or w < 2000:
            return
        summer.freq(f)
        summer.duty_u16(4000 + w * 29000 // 65535)
        _zeit.sleep_ms(ms)
        summer.duty_u16(0)

    # Joystick-Mitte messen (loslassen beim Einschalten)
    x0 = y0 = 0
    for _ in range(16):
        x0 += joy_x.read_u16()
        y0 += joy_y.read_u16()
        _zeit.sleep_ms(3)
    x0 //= 16
    y0 //= 16

    liste = spiele()
    zuletzt = lies(ZULETZT_DATEI)
    wahl = liste.index(zuletzt) if zuletzt in liste else 0
    oben = 0

    def zeichnen():
        oled.fill(0)
        oled.fill_rect(0, 0, 128, 10, 1)
        oled.text("ESP-HUB", 2, 1, 0)
        if liste:
            z = "%d/%d" % (wahl + 1, len(liste))
            oled.text(z, 126 - 8 * len(z), 1, 0)
        if not liste:
            oled.text("Keine Spiele!", 12, 16, 1)
            oled.text("gal_NAME.py", 20, 30, 1)
            oled.text("hochladen", 28, 40, 1)
            oled.show()
            return
        for i in range(ZEILEN):
            n = oben + i
            if n >= len(liste):
                break
            y = ZEILE_Y + i * ZEILE_H
            text = anzeigename(liste[n])[:14]
            if n == wahl:
                oled.fill_rect(0, y - 1, 120, ZEILE_H, 1)
                oled.text(">" + text, 1, y, 0)
            else:
                oled.text(" " + text, 1, y, 1)
        # Scrollbalken
        if len(liste) > ZEILEN:
            h = max(4, ZEILEN * ZEILE_H * ZEILEN // len(liste))
            y = ZEILE_Y - 1 + (ZEILEN * ZEILE_H - h) * oben // (len(liste) - ZEILEN)
            oled.fill_rect(124, y, 3, h, 1)
        oled.hline(0, 53, 128, 1)
        oled.text("S5 = Starten", 16, 56, 1)
        oled.show()

    def led_zeigen():
        for i, p in enumerate(LED_PINS):
            Pin(p).value(1 if liste and i == wahl % 8 else 0)

    zeichnen()
    led_zeigen()
    # erst loslassen, damit ein noch gehaltenes S4+S5 nichts ausloest
    while s5.value() == AN or sj.value() == AN:
        _zeit.sleep_ms(20)

    alt = 0
    naechste_wdh = 0
    rechts_alt = True
    while True:
        jy = joy_y.read_u16() - y0
        jx = joy_x.read_u16() - x0
        richtung = 0
        if jy > TOTZONE or s17.value() == AN:
            richtung = -1
        elif jy < -TOTZONE or s16.value() == AN:
            richtung = 1
        jetzt = _zeit.ticks_ms()
        if richtung and liste and (richtung != alt or _zeit.ticks_diff(jetzt, naechste_wdh) >= 0):
            naechste_wdh = _zeit.ticks_add(jetzt, 380 if richtung != alt else 150)
            wahl = (wahl + richtung) % len(liste)
            if wahl < oben:
                oben = wahl
            elif wahl >= oben + ZEILEN:
                oben = wahl - ZEILEN + 1
            zeichnen()
            led_zeigen()
            piep(1800 if richtung < 0 else 1500)
        alt = richtung

        rechts = jx > TOTZONE * 2
        los = s5.value() == AN or sj.value() == AN or (rechts and not rechts_alt)
        rechts_alt = rechts
        if los and liste:
            starten(oled, liste[wahl], piep)
        _zeit.sleep_ms(15)


def starten(oled, name, piep):
    oled.fill(0)
    oled.text("Starte", 40, 2, 1)
    t = anzeigename(name)[:16]
    oled.text(t, 64 - 4 * len(t), 14, 1)
    oled.hline(0, 26, 128, 1)
    oled.text("Zurueck zur", 20, 32, 1)
    oled.text("Galerie:", 32, 42, 1)
    oled.text("S4+S5 halten", 16, 54, 1)
    oled.show()
    piep(1300, 40)
    piep(2000, 60)
    with open(START_DATEI, "w") as f:
        f.write(name)
    with open(ZULETZT_DATEI, "w") as f:
        f.write(name)
    _zeit.sleep_ms(1200)
    neustart()


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
        if name in spiele():
            spiel_starten(name)
            return
    galerie()


main()

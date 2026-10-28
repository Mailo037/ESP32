# SPACE DODGE v2.0 - Spiel fuer das BZTG espBoard (MicroPython, ESP32)
#
# Joystick      : Raumschiff steuern (links/rechts/oben/unten)
# S17 (oben)    : schiessen
# S4  (links)   : Bombe (kostet 5 Energie, zerstoert alle Gegner)
# Joystick-Taster: Schutzschild (verbraucht Energie)
# S5  (rechts)  : Pause
# S16 (unten)   : Start / Neustart
# Poti links    : Lautstaerke des Summers
# Poti rechts   : Schwierigkeit (Gegner-Tempo und -Anzahl)
# 8 LEDs        : Munition (1 pro Schuss, laedt von selbst nach)
# Balken unten  : Energie fuer Schild und Bombe
# RGB-LED       : gruen = ok, blau = Schild, rot = getroffen
# BMP280        : Temperatur auf dem Titelbild, startet den Zufallsgenerator
# S5 im Titelbild: Bestenliste anzeigen
# Bestenliste   : Top 5 mit Namen (Laenge einstellbar), gespeichert als bestenliste.txt
#                 (Namen eingeben: Joystick hoch/runter = Buchstabe,
#                  links/rechts = Stelle, S16 = fertig)
#
# Auf den ESP: main.py + ssd1306.py (beide in den Root-Ordner)

from machine import Pin, ADC, I2C, PWM
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add
import random
import struct

# =====================================================================
#  EINSTELLUNGEN - hier kannst du alles anpassen
# =====================================================================
# --- Munition (die 8 LEDs zeigen den Füllstand, egal wie gross das Magazin ist)
MUNITION_MAX = 16             # Magazingroesse = max. Schuesse am Stueck (1 ... 99)
MUNITION_START = 16           # Schuesse beim Spielstart (0 ... MUNITION_MAX)
SCHUSS_KOSTEN = 1             # Munition, die ein Schuss verbraucht
NACHLADEN_PRO_SEKUNDE = 1     # Munition, die pro Sekunde automatisch nachlaedt
SCHUSS_PAUSE_MS = 180         # Mindestabstand zwischen zwei Schuessen in ms
# --- Name in der Bestenliste
NAME_LAENGE = 4               # Buchstaben pro Name (1 ... 8)
PLAETZE = 5                   # Plaetze in der Bestenliste (1 ... 5, mehr passen nicht aufs Display)
BUCHSTABEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"   # erlaubte Zeichen
# --- LED-Animation (die 8 LEDs wechseln sich rot/gelb ab)
ROT_MASKE = 0b01010101        # welche LEDs rot sind (LED1 = ganz rechts im Byte).
                              # Sind Rot und Gelb vertauscht: auf 0b10101010 aendern
ANIMATION_TEMPO_MS = 110      # Dauer eines Animationsschritts im Titelbild
# --- Cheatcode: im Titelbild eingeben, nochmal eingeben = wieder aus
# U/D/L/R = Joystick hoch/runter/links/rechts, F = S17 (Feuer). Beliebig aenderbar.
CHEAT_CODE = "UULRLR"
CHEAT_LEBEN = 9               # Leben im Cheat-Modus
CHEAT_UNENDLICH_MUNITION = True
CHEAT_UNENDLICH_ENERGIE = True   # Schild und Bombe
CHEAT_BESTENLISTE = True     # True = auch Cheat-Runden kommen in die Bestenliste
# --- Tempo und Technik
SPIEL_TEMPO = 1.0             # 1.0 = normal, 1.3 = schneller, 0.8 = langsamer
MAX_FPS = 50                  # Bildrate begrenzen (das Spieltempo bleibt gleich)
I2C_FREQ = 400000             # OLED-Takt. Viele Displays schaffen 800000-1000000
TASTEN_AKTIV_HIGH = True      # Board: 3,3 V ueber Taster, 10k Pull-down
# =====================================================================

NAME_LAENGE = max(1, min(8, NAME_LAENGE))
PLAETZE = max(1, min(5, PLAETZE))
MUNITION_MAX = max(1, MUNITION_MAX)
MUNITION_START = max(0, min(MUNITION_MAX, MUNITION_START))

# Alle Geschwindigkeiten unten sind "Pixel pro Takt". Ein Takt dauert
# TAKT_MS - so laeuft das Spiel gleich schnell, egal wie viele Bilder
# pro Sekunde das Display schafft.
TAKT_MS = 40.0 / SPIEL_TEMPO

# ---------- Hardware ----------
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=I2C_FREQ)
oled = SSD1306_I2C(128, 64, i2c)

leds = [Pin(p, Pin.OUT) for p in (32, 33, 25, 26, 27, 14, 12, 13)]

Soben = Pin(17, Pin.IN)     # S17
Slinks = Pin(4, Pin.IN)     # S4
Sunten = Pin(16, Pin.IN)    # S16
Srechts = Pin(5, Pin.IN)    # S5
Sjoy = Pin(2, Pin.IN)       # Joystick-Taster


def adc(pin):
    a = ADC(Pin(pin))
    a.atten(ADC.ATTN_11DB)   # voller Bereich 0 ... 3,3 V
    return a


PotiL = adc(39)
PotiR = adc(36)
hJoys = adc(34)
vJoys = adc(35)

buzzer = PWM(Pin(15), freq=1000, duty_u16=0)
rot = PWM(Pin(19), freq=5000, duty_u16=0)
gruen = PWM(Pin(23), freq=5000, duty_u16=0)
blau = PWM(Pin(18), freq=5000, duty_u16=0)


def temperatur_lesen():
    """Temperatur vom BMP280 (I2C 0x76 oder 0x77) - ohne Extra-Treiber."""
    for addr in (0x76, 0x77):
        try:
            if i2c.readfrom_mem(addr, 0xD0, 1)[0] not in (0x56, 0x57, 0x58, 0x60):
                continue
            t1, t2, t3 = struct.unpack("<Hhh", i2c.readfrom_mem(addr, 0x88, 6))
            i2c.writeto_mem(addr, 0xF4, b"\x21")     # 1x Temperatur, Einzelmessung
            sleep_ms(10)
            d = i2c.readfrom_mem(addr, 0xFA, 3)
            roh = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
            v1 = (roh / 16384.0 - t1 / 1024.0) * t2
            v2 = (roh / 131072.0 - t1 / 8192.0) ** 2 * t3
            return (v1 + v2) / 5120.0
        except (OSError, IndexError):
            pass
    return None


temperatur = temperatur_lesen()


# ---------- Hilfsfunktionen ----------
def zeige():
    # I2C-Aussetzer (ENODEV) abfangen, damit das Spiel weiterlaeuft
    try:
        oled.show()
    except OSError:
        sleep_ms(20)


def taste(pin):
    wert = bool(pin.value())
    return wert if TASTEN_AKTIV_HIGH else not wert


rgb_stand = None


def rgb(r, g, b):
    # nur schreiben, wenn sich die Farbe aendert
    global rgb_stand
    if rgb_stand == (r, g, b):
        return
    rot.duty_u16(r * 257)
    gruen.duty_u16(g * 257)
    blau.duty_u16(b * 257)
    rgb_stand = (r, g, b)


ton_ende = 0


def ton(freq, ms):
    global ton_ende
    # Poti links = Lautstaerke (Piezo ist bei 50 % Tastverhaeltnis am lautesten)
    lautstaerke = 12000 + PotiL.read_u16() // 3
    buzzer.freq(freq)
    buzzer.duty_u16(lautstaerke)
    ton_ende = ticks_add(ticks_ms(), ms)


def ton_pruefen():
    global ton_ende
    if ton_ende and ticks_diff(ticks_ms(), ton_ende) > 0:
        buzzer.duty_u16(0)
        ton_ende = 0


led_stand = -1


def leds_maske(maske):
    # Bit 0 = LED1 ... Bit 7 = LED8; nur geaenderte LEDs schreiben
    global led_stand
    if maske == led_stand:
        return
    for i in range(8):
        bit = (maske >> i) & 1
        if led_stand < 0 or ((led_stand >> i) & 1) != bit:
            leds[i].value(bit)
    led_stand = maske


def leds_setzen(n):
    leds_maske((1 << max(0, min(8, n))) - 1)


ROT = ROT_MASKE & 0xFF
GELB = ~ROT_MASKE & 0xFF


def animation_bauen():
    # Liste von LED-Masken, wird im Titelbild in Endlosschleife abgespielt
    frames = []
    # 1) Lauflicht mit Schweif hin und her
    weg = list(range(8)) + list(range(6, 0, -1))
    for k, i in enumerate(weg):
        richtung = 1 if k < 8 else -1
        maske = 1 << i
        j = i - richtung
        if 0 <= j < 8:
            maske |= 1 << j
        frames.append(maske)
    # 2) Wechselblinker rot / gelb
    for _ in range(3):
        frames += [ROT, ROT, 0, GELB, GELB, 0]
    # 3) von aussen nach innen und zurueck
    frames += [0x81, 0xC3, 0xE7, 0xFF, 0xE7, 0xC3, 0x81, 0]
    return frames


ANIMATION = animation_bauen()


def treffer(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def warte_loslassen(taster):
    while taste(taster):
        sleep_ms(10)


def bestenliste_lesen():
    # Datei bestenliste.txt: pro Zeile "NAME;PUNKTE", beste zuerst
    liste = []
    try:
        with open("bestenliste.txt") as f:
            for zeile in f:
                teile = zeile.strip().split(";")
                if len(teile) == 2:
                    liste.append((teile[0][:NAME_LAENGE], int(teile[1])))
    except Exception:
        pass
    if not liste:                       # alten Rekord uebernehmen
        try:
            with open("highscore.txt") as f:
                liste.append(("ESP", int(f.read())))
        except Exception:
            pass
    liste.sort(key=lambda e: -e[1])
    return liste[:PLAETZE]


def bestenliste_schreiben(liste):
    try:
        with open("bestenliste.txt", "w") as f:
            for name, punkte in liste:
                f.write("%s;%d\n" % (name, punkte))
    except Exception:
        pass


# Joystick-Mittelstellung beim Start messen (Joystick dabei loslassen!)
def mitte_messen():
    oled.fill(0)
    oled.text("SPACE DODGE", 20, 8)
    oled.text("Joystick", 32, 28)
    oled.text("loslassen...", 16, 40)
    zeige()
    sleep_ms(500)
    h = v = 0
    for _ in range(20):
        h += hJoys.read_u16()
        v += vJoys.read_u16()
        sleep_ms(5)
    return h // 20, v // 20


H0, V0 = mitte_messen()
TOTZONE = 9000


# ---------- Bildschirme ----------
def titelbild(cheat=False):
    oled.invert(0)
    oled.fill(0)
    if cheat:
        oled.text("*CHEAT*", 0, 56)
    oled.text("SPACE DODGE", 16, 0)
    oled.hline(0, 10, 128, 1)
    oled.text("S4  Steuerung", 0, 18)
    oled.text("S5  Bestenliste", 0, 30)
    oled.text("S16 START", 0, 48)
    if temperatur is not None:
        t = "%dC" % round(temperatur)
        oled.text(t, 128 - len(t) * 8, 56)
    zeige()


SEITEN = (
    ("STEUERUNG 1/3", ("Joystick fliegen", "Joy-Taste Schild", "S17 Feuer", "S4  Bombe (-5E)", "S5  Pause")),
    ("STEUERUNG 2/3", ("Poti L Lautst.", "Poti R Tempo", "S16 Start", "S5 Bestenliste")),
    ("ANZEIGEN 3/3", ("LEDs: Munition", "Balken: Energie", "RGB blau=Schild", "RGB rot=Treffer", "orange = 1 Leben")),
)


def hilfe():
    seite = 0
    while True:
        oled.invert(0)
        oled.fill(0)
        titel_text, zeilen = SEITEN[seite]
        oled.text(titel_text, 8, 0)
        oled.hline(0, 9, 128, 1)
        for i, z in enumerate(zeilen):
            oled.text(z, 0, 12 + i * 9)
        oled.text("S4 weiter S16 zu", 0, 57)
        zeige()
        leds_setzen(0)
        while not (taste(Slinks) or taste(Sunten)):
            sleep_ms(20)
        if taste(Sunten):
            warte_loslassen(Sunten)
            return
        warte_loslassen(Slinks)
        seite = (seite + 1) % len(SEITEN)


def bestenliste_zeigen(liste, markiere=None):
    oled.invert(0)
    oled.fill(0)
    oled.text("BESTENLISTE", 16, 0)
    oled.hline(0, 10, 128, 1)
    if not liste:
        oled.text("noch leer", 28, 30)
    breite = min(5, 12 - NAME_LAENGE)      # Punkte-Spalte, damit alles in 16 Zeichen passt
    for i, (name, punkte) in enumerate(liste):
        marke = ">" if (name, punkte) == markiere else " "
        p = str(punkte)
        p = " " * (breite - len(p)) + p
        oled.text("%s%d %s %s" % (marke, i + 1, name, p), 0, 14 + i * 9)
    oled.text("S16 weiter", 24, 57)
    zeige()
    leds_setzen(0)
    while not (taste(Sunten) or taste(Srechts)):
        sleep_ms(20)
    warte_loslassen(Sunten)
    warte_loslassen(Srechts)


def name_eingeben(platz):
    # Joystick hoch/runter = Buchstabe, links/rechts = Stelle, S16 = fertig
    wahl = [0] * NAME_LAENGE
    pos = 0
    letzte = 0
    abstand = min(16, 120 // NAME_LAENGE)
    x0 = (128 - ((NAME_LAENGE - 1) * abstand + 8)) // 2
    while True:
        jetzt = ticks_ms()
        h = hJoys.read_u16() - H0
        v = vJoys.read_u16() - V0
        if ticks_diff(jetzt, letzte) > 200:
            if v > TOTZONE:
                wahl[pos] = (wahl[pos] + 1) % len(BUCHSTABEN)
                letzte = jetzt
            elif v < -TOTZONE:
                wahl[pos] = (wahl[pos] - 1) % len(BUCHSTABEN)
                letzte = jetzt
            elif h > TOTZONE and pos < NAME_LAENGE - 1:
                pos += 1
                letzte = jetzt
            elif h < -TOTZONE and pos > 0:
                pos -= 1
                letzte = jetzt
        if taste(Sunten):
            warte_loslassen(Sunten)
            return "".join(BUCHSTABEN[i] for i in wahl)
        oled.fill(0)
        oled.text("PLATZ %d!" % platz, 32, 0)
        oled.text("Dein Name:", 24, 12)
        for i in range(NAME_LAENGE):
            x = x0 + i * abstand
            oled.text(BUCHSTABEN[wahl[i]], x, 34)
            if i == pos:
                oled.text("^", x, 24)
                oled.text("v", x, 44)
        oled.text("Joystick waehlen", 0, 56)
        zeige()
        leds_setzen(pos + 1)
        sleep_ms(20)


def cheat_meldung(an):
    oled.invert(0)
    oled.fill(0)
    oled.text("CHEAT-CODE!", 20, 16)
    oled.text("AKTIV" if an else "AUS", 44, 36)
    zeige()
    rgb(255, 0, 255)
    leds_maske(0xFF)
    ton(1500, 120)
    sleep_ms(1200)
    ton_pruefen()


def titel(liste, cheat):
    titelbild(cheat)
    start = ticks_ms()
    eingabe = ""      # zuletzt eingegebene Richtungen / S17
    alt = ""
    while not taste(Sunten):
        if taste(Srechts):
            warte_loslassen(Srechts)
            bestenliste_zeigen(liste)
            titelbild(cheat)
        if taste(Slinks):
            warte_loslassen(Slinks)
            hilfe()
            titelbild(cheat)
        # Cheatcode erkennen (nur bei neuem Tastendruck / neuer Joystick-Richtung)
        h = hJoys.read_u16() - H0
        v = vJoys.read_u16() - V0
        if abs(v) >= abs(h):
            neu = "U" if v > TOTZONE else ("D" if v < -TOTZONE else "")
        else:
            neu = "R" if h > TOTZONE else ("L" if h < -TOTZONE else "")
        if taste(Soben):
            neu = "F"
        if neu and neu != alt:
            eingabe = (eingabe + neu)[-len(CHEAT_CODE):]
            if eingabe == CHEAT_CODE:
                cheat = not cheat
                eingabe = ""
                cheat_meldung(cheat)
                titelbild(cheat)
        alt = neu
        # RGB-LED "atmet", die 8 LEDs spielen die rot/gelb-Animation
        t = ticks_diff(ticks_ms(), start)
        helligkeit = abs(((t * 2 // 5) % 510) - 255)
        rgb(0, helligkeit, helligkeit // 3)
        leds_maske(ANIMATION[(t // ANIMATION_TEMPO_MS) % len(ANIMATION)])
        sleep_ms(15)
    warte_loslassen(Sunten)
    random.seed(ticks_ms() + int((temperatur or 0) * 1000))
    ton(2000, 150)
    sleep_ms(160)
    ton_pruefen()
    return cheat


def game_over(score, liste, cheat):
    # Platz: bei Gleichstand rutscht der neue Eintrag hinter den alten
    platz = 1 + sum(1 for _, s in liste if s >= score)
    qualifiziert = score > 0 and platz <= PLAETZE and (not cheat or CHEAT_BESTENLISTE)
    rekord = liste[0][1] if liste else 0
    oled.invert(0)
    rgb(255, 0, 0)
    for k, f in enumerate((1500, 1100, 800, 500)):
        leds_maske(ROT if k % 2 == 0 else GELB)    # Game-Over-Blinker
        ton(f, 200)
        sleep_ms(220)
        ton_pruefen()
    oled.fill(0)
    oled.text("GAME OVER", 28, 4)
    oled.text("Punkte: %d" % score, 16, 24)
    oled.text("Rekord: %d" % max(rekord, score), 16, 36)
    if cheat and not CHEAT_BESTENLISTE:
        oled.text("Cheat-Runde", 20, 14)
    elif qualifiziert and platz == 1:
        oled.text("NEUER REKORD!", 12, 14)
    oled.text("S16 weiter", 24, 54)
    zeige()
    leds_setzen(0)
    while not taste(Sunten):
        sleep_ms(20)
    warte_loslassen(Sunten)
    if qualifiziert:
        name = name_eingeben(platz)
        liste.insert(platz - 1, (name, score))
        liste = liste[:PLAETZE]
        bestenliste_schreiben(liste)
        bestenliste_zeigen(liste, (name, score))
    return liste


def pause():
    warte_loslassen(Srechts)
    oled.fill_rect(30, 24, 68, 16, 0)
    oled.rect(30, 24, 68, 16, 1)
    oled.text("PAUSE", 44, 28)
    zeige()
    leds_setzen(0)
    buzzer.duty_u16(0)
    while not taste(Srechts):
        sleep_ms(20)
    warte_loslassen(Srechts)


# ---------- Spiel ----------
def spiel(highscore, cheat):
    sx, sy = 60.0, 54.0       # Schiff (9 x 6 Pixel)
    leben = CHEAT_LEBEN if cheat else 3
    energie = 8.0             # fuer Schild und Bombe (Balken unten im OLED)
    munition = float(MUNITION_START)      # Anzeige auf den 8 LEDs
    letzter_frame = ticks_ms()
    score = 0
    gegner = []               # [x, y, geschwindigkeit]
    schuesse = []             # [x, y]
    letzter_schuss = 0
    unverwundbar_bis = 0      # Zeitpunkt (ms), bis zu dem das Schiff blinkt
    blitz_bis = 0
    farbe_bis = 0
    bild_ms = 1000 // MAX_FPS

    rgb(0, 255, 0)
    while True:
        jetzt = ticks_ms()

        # --- Pause ---
        if taste(Srechts):
            pause()
            jetzt = ticks_ms()
            letzter_frame = jetzt

        # Wie viele Takte sind seit dem letzten Bild vergangen?
        dt = ticks_diff(jetzt, letzter_frame)
        if dt > 60:
            dt = 60           # nach Rucklern nicht springen
        letzter_frame = jetzt
        k = dt / TAKT_MS

        # --- Schwierigkeit: Poti rechts + Spielfortschritt ---
        diff = 0.6 + PotiR.read_u16() * 2.4 / 65535 + min(score / 400, 2.0)

        # --- Joystick: Schiff bewegen ---
        h = hJoys.read_u16() - H0
        v = vJoys.read_u16() - V0
        if h > TOTZONE:
            sx += (3 if h > 3 * TOTZONE else 2) * k
        elif h < -TOTZONE:
            sx -= (3 if h < -3 * TOTZONE else 2) * k
        if v > TOTZONE:       # Joystick oben -> Schiff nach oben (wie im Pruefprogramm)
            sy -= 2 * k
        elif v < -TOTZONE:
            sy += 2 * k
        sx = max(0.0, min(119.0, sx))
        sy = max(26.0, min(57.0, sy))
        ix = int(sx)
        iy = int(sy)

        # --- Schiessen ---
        if taste(Soben) and munition >= SCHUSS_KOSTEN and ticks_diff(jetzt, letzter_schuss) > SCHUSS_PAUSE_MS:
            schuesse.append([ix + 4, iy - 2.0])
            letzter_schuss = jetzt
            if not (cheat and CHEAT_UNENDLICH_MUNITION):
                munition -= SCHUSS_KOSTEN
            ton(1800, 25)
        munition = min(float(MUNITION_MAX), munition + NACHLADEN_PRO_SEKUNDE * dt / 1000)

        # --- Bombe ---
        if taste(Slinks) and energie >= 5:
            energie -= 5
            score += 5 * len(gegner)
            gegner = []
            blitz_bis = ticks_add(jetzt, 160)
            ton(800, 250)
            warte_loslassen(Slinks)

        # --- Schild ---
        schild = taste(Sjoy) and energie > 0
        if schild:
            energie -= 0.08 * k
        else:
            energie = min(8.0, energie + 0.02 * k)
        if cheat and CHEAT_UNENDLICH_ENERGIE:
            energie = 8.0

        # --- Gegner erzeugen ---
        if random.random() < 0.035 * diff * k:
            gegner.append([random.randint(0, 121), 10.0, 0.6 + diff * 0.3 + random.random() * 0.6])

        # --- Schuesse bewegen ---
        schritt = 4 * k
        for s in schuesse:
            s[1] -= schritt
        schuesse = [s for s in schuesse if s[1] > 9]

        # --- Gegner bewegen und Kollisionen ---
        unverwundbar = ticks_diff(unverwundbar_bis, jetzt) > 0
        neue_gegner = []
        for g in gegner:
            g[1] += g[2] * k
            ex, ey = g[0], int(g[1])
            if ey > 63:
                continue                      # unten raus, kein Punkt
            abgeschossen = False
            for s in schuesse:
                if treffer(ex, ey, 7, 7, s[0], s[1], 1, 4):
                    schuesse.remove(s)
                    abgeschossen = True
                    break
            if abgeschossen:
                score += 10
                ton(1200, 40)
                continue
            if schild and treffer(ex, ey, 7, 7, ix - 3, iy - 3, 15, 12):
                score += 2
                ton(1000, 30)
                continue
            if not unverwundbar and treffer(ex, ey, 7, 7, ix, iy, 9, 6):
                leben -= 1
                unverwundbar = True
                unverwundbar_bis = ticks_add(jetzt, 1600)
                farbe_bis = ticks_add(jetzt, 400)
                rgb(255, 0, 0)
                ton(700, 300)
                continue
            neue_gegner.append(g)
        gegner = neue_gegner

        if leben <= 0:
            oled.invert(0)
            return score

        # --- RGB-LED ---
        if farbe_bis and ticks_diff(jetzt, farbe_bis) > 0:
            farbe_bis = 0
        if not farbe_bis:
            if schild:
                rgb(0, 0, 255)
            elif leben == 1:
                rgb(255, 80, 0)
            else:
                rgb(0, 255, 0)

        # --- LEDs: Munition (auf 8 LEDs skaliert); naechste LED blinkt beim Nachladen ---
        voll = int(munition * 8 / MUNITION_MAX)
        if voll < 8 and (jetzt // 160) % 2 == 0:
            leds_setzen(voll + 1)
        else:
            leds_setzen(voll)

        # --- Zeichnen ---
        oled.fill(0)
        oled.text("L%d S%04d H%04d" % (leben, score, max(score, highscore)), 0, 0)
        oled.hline(0, 9, 128, 1)
        for g in gegner:
            ex, ey = g[0], int(g[1])
            oled.rect(ex, ey, 7, 7, 1)
            oled.pixel(ex + 3, ey + 3, 1)
        for s in schuesse:
            oled.vline(s[0], int(s[1]), 4, 1)
        if not unverwundbar or (jetzt // 80) % 2 == 0:       # Blinken nach Treffer
            oled.line(ix + 4, iy, ix, iy + 5, 1)
            oled.line(ix + 4, iy, ix + 8, iy + 5, 1)
            oled.hline(ix, iy + 5, 9, 1)
        if schild:
            oled.rect(ix - 3, iy - 3, 15, 12, 1)
        oled.hline(0, 63, int(max(energie, 0) * 16), 1)     # Energie-Balken
        oled.invert(ticks_diff(blitz_bis, jetzt) > 0)      # Bomben-Blitz
        zeige()

        ton_pruefen()
        # Bildrate begrenzen
        rest = bild_ms - ticks_diff(ticks_ms(), jetzt)
        if rest > 0:
            sleep_ms(rest)


# ---------- Hauptprogramm ----------
bestenliste = bestenliste_lesen()
cheat = False
while True:
    cheat = titel(bestenliste, cheat)
    punkte = spiel(bestenliste[0][1] if bestenliste else 0, cheat)
    bestenliste = game_over(punkte, bestenliste, cheat)

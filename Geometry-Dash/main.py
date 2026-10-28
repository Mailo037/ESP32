# HUB-NAME: Geometry Dash
# HUB-VERSION: 1.1
# HUB-INFO: Wuerfel-Springspiel mit 3 Leveln und Uebungsmodus
# =====================================================================
#  GEOMETRY DASH (Fan-Nachbau) fuer das BZTG espBoard
#  MicroPython, ESP32, SSD1306 128x64
# =====================================================================
#  MENUE
#    Joystick links/rechts : Level waehlen
#    S16 / Joystick-Taster : Start
#    S5                    : Uebungsmodus an/aus (mit Checkpoints)
#  SPIEL
#    S17 / Joystick-Taster / Joystick hoch : Springen
#      (gedrueckt halten = bei jeder Landung sofort wieder springen)
#    S5                    : Pause
#    S4                    : zurueck ins Menue
#  Poti RP3 (links oben)   : Lautstaerke von Musik und Effekten (ganz links = stumm)
#  8 LEDs                  : Fortschritt im Level
#  RGB-LED                 : Levelfarbe, rot = Absturz
#
#  Auf den ESP: main.py + ssd1306.py (beide in den Root-Ordner)
# =====================================================================

from machine import Pin, ADC, I2C, PWM
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add
import math
try:
    import hub          # gibt es nur, wenn das Spiel aus dem ESP-Hub startet
except ImportError:
    hub = None

# =====================================================================
#  EINSTELLUNGEN
# =====================================================================
TEMPO = 60.0            # Pixel pro Sekunde (60 = 7,5 Bloecke/s)
SPRUNG = 185.0          # Absprung-Geschwindigkeit (Pixel/s)
SCHWERKRAFT = 720.0     # Pixel/s^2
PAD_SPRUNG = 235.0      # Sprungpad (gelb, flach am Boden)
ORB_SPRUNG = 175.0      # Sprungring in der Luft
DREH_TEMPO = 400.0      # Grad pro Sekunde in der Luft
MAX_FPS = 60
I2C_FREQ = 400000       # viele Displays schaffen 800000-1000000
MUSIK = True
TASTEN_AKTIV_HIGH = True
HOCH_POSITIV = True     # Joystick: positiver ADC-Wert = nach oben
TOTZONE = 9000
# LEDs von links nach rechts (P7 ... P0), so wie sie auf dem Board sitzen
LED_PINS = (13, 12, 14, 27, 26, 25, 33, 32)
REKORD_DATEI = "gd_rekord.txt"
# =====================================================================

PHYS_DT = 1.0 / 120     # Physik rechnet immer in gleich grossen Schritten
BODEN_Y = 56            # Oberkante des Bodens
OBEN_Y = 8              # Oberkante der Levelzeile 0
SPIELER_X = 24          # Spieler-Position auf dem Bildschirm
ZEILEN = 6              # Levelhoehe in Bloecken (je 8 Pixel)

# =====================================================================
#  LEVEL
#  Jedes Level besteht aus Abschnitten. Ein Abschnitt ist ein kleines
#  Bild aus 6 Zeilen (oben -> unten, die letzte Zeile liegt auf dem Boden):
#    .  leer          #  Block (man kann darauf laufen)
#    ^  Stachel       v  Stachel nach unten (haengt unter einem Block)
#    o  Sprungpad     *  Sprungring (in der Luft druecken!)
#  Eigene Level: einfach einen neuen Eintrag in LEVELS anlegen.
# =====================================================================


def leer(n):
    return ("." * n,) * ZEILEN


def boden(s):
    return ("." * len(s),) * (ZEILEN - 1) + (s,)


LEVELS = (
    ("ERSTER SPRUNG", 1, 1200, (
        leer(22),
        boden("....^......."),
        boden("....^......."),
        boden("...^^........"),
        boden("...#........."),
        boden("...#..#......"),
        boden("...^^....^^..."),
        ("...............",
         "...............",
         "...............",
         "......###......",
         "...######......",
         "#########......"),
        boden("...^^......."),
        boden("...#^^#........"),
        ("..............",
         "..............",
         "..............",
         "....###.......",
         "....###.......",
         "..o.###.......",),
        ("................",
         "................",
         "................",
         "................",
         ".......#####....",
         "...#...#####....."[:16]),
        boden("...^^...^^...^^......"),
        leer(14),
    )),
    ("TREPPAUF", 2, 1000, (
        leer(22),
        boden("...^^....^^^......."),
        ("..................",
         "..................",
         "..................",
         ".........##.......",
         ".....##..##.......",
         ".##..##..##..^^..."),
        ("....................",
         "....................",
         "..........#######...",
         "..........v.....v...",
         ".....###............",
         "..o..###..^^^^^^^..."),
        ("..................",
         "..................",
         "..................",
         "......*...........",
         "..................",
         "...^^^^^^.........",),
        boden("..^^...^^^...#^^^#^^^#....."),
        ("....................",
         "....................",
         "...............##...",
         "...........##.......",
         ".......##...........",
         "...##.....^^^^^^^^^."),
        boden("....^^.....^^^.......^^^...."),
        leer(14),
    )),
    ("ORBIT", 3, 800, (
        leer(22),
        boden("...^^^...^^^...."),
        ("...................",
         "...................",
         "...................",
         "....*..*..*........",
         "...................",
         "...^^^^^^^^^......."),
        ("........................",
         "........................",
         "........#..#..#.........",
         ".....#..v..v..v..#......",
         "..#..v...........v..#...",
         "..#.^^^^^^^^^^^^^^^.#..."),
        ("....................",
         "....................",
         "....................",
         "......*..*..........",
         "....................",
         "..o.^^^^^^^^^......."),
        boden("...#^^#^^#^^#....^^^...."),
        ("......................",
         "......................",
         "......................",
         "....*..*..*..*........",
         "......................",
         "...^^^^^^^^^^^^......."),
        boden("..^^^...^^^...^^^......"),
        leer(14),
    )),
)


class Level:
    def __init__(self, nr):
        name, sterne, _, teile = LEVELS[nr]
        self.nr = nr
        self.name = name
        self.sterne = sterne
        zeilen = [[] for _ in range(ZEILEN)]
        for teil in teile:
            breite = len(teil[0])
            for r in range(ZEILEN):
                z = teil[r]
                zeilen[r].append(z[:breite] + "." * (breite - len(z)))
        self.zeilen = [bytes("".join(z), "ascii") for z in zeilen]
        self.breite = len(self.zeilen[0])
        self.ende_x = (self.breite - 10) * 8
        # Pro Spalte nur die belegten Felder merken -> schnelles Zeichnen
        self.spalten = []
        for c in range(self.breite):
            self.spalten.append(tuple((r, self.zeilen[r][c]) for r in range(ZEILEN)
                                      if self.zeilen[r][c] != 46))   # 46 = "."

    def feld(self, c, r):
        if c < 0 or c >= self.breite or r < 0 or r >= ZEILEN:
            return 46
        return self.zeilen[r][c]


# Feld-Codes (Bytewerte der Zeichen)
F_BLOCK = 35    # '#'
F_STACHEL = 94  # '^'
F_UNTEN = 118   # 'v'
F_PAD = 111     # 'o'
F_ORB = 42      # '*'

TOT = 1
ZIEL = 2


def ueberlapp(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class Spieler:
    """Wuerfel-Physik. Wird auch am PC zum Testen der Level benutzt."""

    def __init__(self):
        self.x = 0.0
        self.y = float(BODEN_Y - 8)
        self.vy = 0.0
        self.boden = True
        self.drehung = 0.0
        self.benutzt = -1        # Spalte des zuletzt benutzten Pads/Rings

    def kopie(self):
        k = Spieler()
        k.x, k.y, k.vy, k.boden, k.drehung, k.benutzt = (
            self.x, self.y, self.vy, self.boden, self.drehung, self.benutzt)
        return k

    def schritt(self, lv, halten, puffer):
        """Ein Physik-Schritt. halten = Sprungtaste gedrueckt,
        puffer = Taste wurde gerade erst gedrueckt (fuer Ringe).
        Gibt (Ergebnis, Ring_benutzt) zurueck."""
        dt = PHYS_DT
        self.x += TEMPO * dt
        alt_unten = self.y + 8
        self.vy += SCHWERKRAFT * dt
        self.y += self.vy * dt
        self.boden = False
        if self.y + 8 >= BODEN_Y:
            self.y = BODEN_Y - 8.0
            self.vy = 0.0
            self.boden = True

        x = self.x
        y = self.y
        c0 = int(x) >> 3
        r0 = (int(y) - OBEN_Y) >> 3
        am_ring = -1
        for c in (c0, c0 + 1):
            tx = c * 8
            for r in (r0 - 1, r0, r0 + 1, r0 + 2):   # +-1 Zeile fuer die Ringe
                f = lv.feld(c, r)
                if f == 46:
                    continue
                ty = OBEN_Y + r * 8
                if f == F_BLOCK:
                    if not ueberlapp(x, self.y, 8, 8, tx, ty, 8, 8):
                        continue
                    if self.vy >= 0 and alt_unten <= ty + 3:
                        self.y = ty - 8.0          # von oben gelandet
                        self.vy = 0.0
                        self.boden = True
                    else:
                        return TOT, False          # gegen die Wand
                elif f == F_STACHEL:
                    # Trefferzone etwas kleiner als der gezeichnete Stachel (fair!)
                    if ueberlapp(x + 1, y + 1, 6, 6, tx + 2.5, ty + 3, 3, 5):
                        return TOT, False
                elif f == F_UNTEN:
                    if ueberlapp(x + 1, y + 1, 6, 6, tx + 2.5, ty, 3, 5):
                        return TOT, False
                elif f == F_PAD:
                    if self.benutzt != c and ueberlapp(x, y, 8, 8, tx, ty + 5, 8, 3):
                        self.vy = -PAD_SPRUNG
                        self.boden = False
                        self.benutzt = c
                elif f == F_ORB:
                    if ueberlapp(x - 2, y - 2, 12, 12, tx, ty, 8, 8):
                        am_ring = c

        ring = False
        if self.boden:
            # auf den naechsten 90-Grad-Winkel einrasten
            self.drehung = (int(self.drehung + 45) // 90) * 90 % 360
            if halten:
                self.vy = -SPRUNG
                self.boden = False
        else:
            self.drehung = (self.drehung + DREH_TEMPO * dt) % 360
            if am_ring >= 0 and puffer and self.benutzt != am_ring:
                self.vy = -ORB_SPRUNG
                self.benutzt = am_ring
                ring = True

        if self.x >= lv.ende_x:
            return ZIEL, ring
        return 0, ring


# =====================================================================
#  AB HIER NUR AUF DEM ESP32
# =====================================================================
def hardware():
    global oled, leds, S4, S5, S16, S17, SJOY, vJoys, hJoys, potiL, buzzer, rgb_pwm
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=I2C_FREQ)
    oled = SSD1306_I2C(128, 64, i2c)
    leds = [Pin(n, Pin.OUT) for n in LED_PINS]
    S4 = Pin(4, Pin.IN)
    S5 = Pin(5, Pin.IN)
    S16 = Pin(16, Pin.IN)
    S17 = Pin(17, Pin.IN)
    SJOY = Pin(2, Pin.IN)
    vJoys = ADC(Pin(35))
    hJoys = ADC(Pin(34))
    potiL = ADC(Pin(39))
    for a in (vJoys, hJoys, potiL):
        a.atten(ADC.ATTN_11DB)
    buzzer = PWM(Pin(15), freq=440, duty_u16=0)
    rgb_pwm = [PWM(Pin(p), freq=5000, duty_u16=0) for p in (19, 23, 18)]


def taste(pin):
    w = bool(pin.value())
    return w if TASTEN_AKTIV_HIGH else not w


class Taste:
    def __init__(self, pin):
        self.pin = pin
        self.alt = taste(pin)

    def neu(self):
        j = taste(self.pin)
        f = j and not self.alt
        self.alt = j
        return f


def zeige():
    try:
        oled.show()
    except OSError:
        sleep_ms(5)


rgb_stand = None


def rgb(r, g, b):
    global rgb_stand
    if rgb_stand == (r, g, b):
        return
    for k, w in zip(rgb_pwm, (r, g, b)):
        k.duty_u16(w * 64)
    rgb_stand = (r, g, b)


led_stand = -1


def leds_balken(n):
    global led_stand
    if n == led_stand:
        return
    for i, led in enumerate(leds):
        led.value(1 if i < n else 0)
    led_stand = n


# ---------- Ton: Musik + Effekte ----------
# Noten als Frequenz, 0 = Pause. Eine Note = eine Achtel.
C4, D4, E4, F4, G4, A4, B4 = 262, 294, 330, 349, 392, 440, 494
C5, D5, E5, G5, A5 = 523, 587, 659, 784, 880
A3, G3, F3, E3 = 220, 196, 175, 165
MELODIEN = (
    (140, (A3, A3, E4, A3, C5, A3, E4, B4, G3, G3, D4, G3, B4, G3, D4, A4,
           F3, F3, C4, F3, A4, F3, C4, G4, E3, E3, B4, E3, G4, E4, B4, E4)),
    (150, (C4, 0, C5, C4, 0, C4, G4, C5, A3, 0, A4, A3, 0, A3, E4, A4,
           F3, 0, F4, F3, 0, F3, C4, F4, G3, 0, G4, G3, D4, G4, B4, D5)),
    (165, (E4, E5, E4, D5, E4, B4, E4, A4, C4, C5, C4, B4, C4, G4, C4, E4,
           D4, D5, D4, A4, D4, G4, D4, E4, E3, E4, G4, B4, E5, D5, B4, G4)),
)

effekt_bis = 0
musik_schritt = -1


def lautstaerke():
    """Poti RP3 (links oben) = Lautstaerke, ganz nach links = stumm.
    Der Piezo ist bei 50 % Tastverhaeltnis (duty 32768) am lautesten."""
    w = potiL.read_u16()
    return 0 if w < 2000 else 4000 + w * 29000 // 65535


def effekt(freq, ms):
    global effekt_bis
    l = lautstaerke()
    if not l:
        return
    buzzer.freq(freq)
    buzzer.duty_u16(l)
    effekt_bis = ticks_add(ticks_ms(), ms)


def ton_update(start, melodie, spielt):
    global effekt_bis, musik_schritt
    now = ticks_ms()
    if effekt_bis:
        if ticks_diff(now, effekt_bis) < 0:
            return
        effekt_bis = 0
        buzzer.duty_u16(0)
        musik_schritt = -1
    if not (MUSIK and spielt):
        if musik_schritt != -2:
            buzzer.duty_u16(0)
            musik_schritt = -2
        return
    bpm, noten = melodie
    achtel = 30000 // bpm
    t = ticks_diff(now, start)
    s = t // achtel
    if s == musik_schritt:
        # Note kurz absetzen, damit man den Rhythmus hoert
        if t % achtel > achtel * 3 // 4:
            buzzer.duty_u16(0)
        return
    musik_schritt = s
    f = noten[s % len(noten)]
    l = lautstaerke()
    if f and l:
        buzzer.freq(f)
        buzzer.duty_u16(l)
    else:
        buzzer.duty_u16(0)


def stille():
    global effekt_bis, musik_schritt
    effekt_bis = 0
    musik_schritt = -1
    buzzer.duty_u16(0)


# ---------- Zeichnen ----------
# Ecken eines um den Mittelpunkt gedrehten Quadrats, vorberechnet
ECKEN = []
for _i in range(24):
    _w = math.radians(_i * 15 + 45)
    ECKEN.append(tuple((round(r * math.cos(_w + k * math.pi / 2)),
                        round(r * math.sin(_w + k * math.pi / 2)))
                       for r in (5.2, 2.2) for k in range(4)))
del _i, _w


def zeichne_wuerfel(sx, sy, drehung):
    if drehung % 90 == 0:
        oled.rect(sx, sy, 8, 8, 1)
        oled.fill_rect(sx + 2, sy + 2, 4, 4, 1)
        return
    e = ECKEN[int(drehung) // 15 % 24]
    cx = sx + 4
    cy = sy + 4
    for k in range(4):
        a = e[k]
        b = e[(k + 1) % 4]
        oled.line(cx + a[0], cy + a[1], cx + b[0], cy + b[1], 1)
        a = e[4 + k]
        b = e[4 + (k + 1) % 4]
        oled.line(cx + a[0], cy + a[1], cx + b[0], cy + b[1], 1)


RING = ((1, -3), (2, -3), (3, -2), (3, -1), (3, 1), (3, 2), (2, 3), (1, 3),
        (-1, 3), (-2, 3), (-3, 2), (-3, 1), (-3, -1), (-3, -2), (-2, -3), (-1, -3),
        (0, -3), (3, 0), (0, 3), (-3, 0))


def zeichne_feld(f, x, y, blink):
    if f == F_BLOCK:
        oled.rect(x, y, 8, 8, 1)
        oled.pixel(x + 2, y + 2, 1)
        oled.pixel(x + 5, y + 5, 1)
    elif f == F_STACHEL:
        oled.line(x, y + 7, x + 3, y, 1)
        oled.line(x + 4, y, x + 7, y + 7, 1)
        oled.hline(x, y + 7, 8, 1)
    elif f == F_UNTEN:
        oled.line(x, y, x + 3, y + 7, 1)
        oled.line(x + 4, y + 7, x + 7, y, 1)
        oled.hline(x, y, 8, 1)
    elif f == F_PAD:
        oled.fill_rect(x + 1, y + 6, 6, 2, 1)
        if blink:
            oled.hline(x + 2, y + 4, 4, 1)
    elif f == F_ORB:
        cx = x + 4
        cy = y + 4
        for dx, dy in RING:
            oled.pixel(cx + dx, cy + dy, 1)
        if blink:
            oled.fill_rect(cx - 1, cy - 1, 2, 2, 1)


def zeichne_welt(lv, kamera, t_ms):
    oled.fill(0)
    k = int(kamera)
    # Hintergrund-Sterne (bewegen sich langsamer -> Tiefe)
    for i in range(10):
        sx = (i * 37 - k // 3) % 128
        oled.pixel(sx, 12 + (i * 23) % 36, 1)
    # Boden mit Streifen
    oled.hline(0, BODEN_Y, 128, 1)
    for x in range(-(k % 16), 128, 16):
        oled.line(x, 63, x + 6, BODEN_Y + 1, 1)
    blink = (t_ms // 150) % 2 == 0
    c0 = k >> 3
    for c in range(c0, c0 + 17):
        if c < 0 or c >= lv.breite:
            continue
        x = c * 8 - k
        for r, f in lv.spalten[c]:
            zeichne_feld(f, x, OBEN_Y + r * 8, blink)
    # Fortschrittsbalken oben
    p = min(1.0, max(0.0, (kamera + SPIELER_X) / lv.ende_x))
    oled.hline(0, 0, 128, 1)
    oled.fill_rect(0, 1, int(126 * p) + 2, 2, 1)
    oled.hline(0, 3, 128, 1)
    return p


def prozent(sp, lv):
    return min(100, max(0, int(sp.x * 100 / lv.ende_x)))


# ---------- Rekorde ----------
def rekorde_lesen():
    r = [0] * len(LEVELS)
    try:
        with open(REKORD_DATEI) as f:
            for zeile in f:
                i, p = zeile.strip().split(";")
                if 0 <= int(i) < len(r):
                    r[int(i)] = int(p)
    except Exception:
        pass
    return r


def rekorde_schreiben(r):
    try:
        with open(REKORD_DATEI, "w") as f:
            for i, p in enumerate(r):
                f.write("%d;%d\n" % (i, p))
    except Exception:
        pass


# ---------- Bildschirme ----------
def mitte(s, y, c=1):
    oled.text(s, (128 - len(s) * 8) // 2, y, c)


def mitte_messen():
    oled.fill(0)
    mitte("GEOMETRY", 10)
    mitte("DASH", 22)
    mitte("Joystick", 40)
    mitte("loslassen...", 50)
    zeige()
    sleep_ms(600)
    v = h = 0
    for _ in range(20):
        v += vJoys.read_u16()
        h += hJoys.read_u16()
        sleep_ms(5)
    return v // 20, h // 20


def menue(nr, rekorde, uebung, h0):
    joy = Taste(SJOY)
    t16 = Taste(S16)
    t5 = Taste(S5)
    sperre = 0
    t0 = ticks_ms()
    # bester Wert aller Boards je Level (aus dem ESP-Hub)
    welt_rekord = None
    if hub:
        welt_rekord = []
        for i in range(len(LEVELS)):
            l = hub.bestenliste("level%d" % i, 1)
            welt_rekord.append(max(rekorde[i], l[0][1] if l else 0))
    while True:
        now = ticks_ms()
        h = hJoys.read_u16() - h0
        if abs(h) > TOTZONE * 2:
            if ticks_diff(now, sperre) > 0:
                nr = (nr + (1 if h > 0 else -1)) % len(LEVELS)
                sperre = ticks_add(now, 300)
                effekt(900, 30)
        else:
            sperre = 0
        if t5.neu():
            uebung = not uebung
            effekt(1200, 40)
        if joy.neu() or t16.neu():
            effekt(1500, 60)
            return nr, uebung
        ton_update(t0, MELODIEN[nr % len(MELODIEN)], False)

        name, sterne, _, _ = LEVELS[nr]
        oled.fill(0)
        mitte("GEOMETRY DASH", 0)
        oled.hline(0, 9, 128, 1)
        oled.text("<", 0, 22)
        oled.text(">", 120, 22)
        mitte(name, 18)
        mitte("*" * sterne, 30)
        if welt_rekord is not None:
            mitte("Du %d%% Top %d%%" % (rekorde[nr], welt_rekord[nr]), 42)
        else:
            mitte("Rekord %d%%" % rekorde[nr], 42)
        oled.text("S5 Uebung:" + ("AN" if uebung else "AUS"), 0, 56)
        # kleiner huepfender Wuerfel als Deko
        t = ticks_diff(now, t0) % 600
        hy = int(abs(math.sin(t * math.pi / 600)) * 6)
        zeichne_wuerfel(4, 32 - hy, (t * 90 // 300) if hy else 0)
        oled.hline(0, 40, 14, 1)
        zeige()
        leds_balken(rekorde[nr] * 8 // 100)
        rgb(*FARBEN[nr % len(FARBEN)])
        sleep_ms(30)


FARBEN = ((0, 255, 80), (0, 120, 255), (255, 0, 200))


def absturz_animation(lv, kamera, sx, sy):
    stille()
    effekt(110, 250)
    rgb(255, 0, 0)
    start = ticks_ms()
    while True:
        t = ticks_diff(ticks_ms(), start)
        if t > 650:
            break
        zeichne_welt(lv, kamera, t)
        r = t // 18
        for i in range(8):
            w = i * math.pi / 4
            oled.fill_rect(sx + 3 + int(math.cos(w) * r), sy + 3 + int(math.sin(w) * r), 2, 2, 1)
        if t < 300:
            oled.rect(sx + 4 - r // 2, sy + 4 - r // 2, r, r, 1)
        zeige()
        ton_update(0, None, False)
    leds_balken(0)


def sieg(lv, versuche, uebung):
    stille()
    for i, f in enumerate((523, 659, 784, 1047, 784, 1047)):
        effekt(f, 110)
        leds_balken(8 if i % 2 else 0)
        sleep_ms(120)
    stille()
    oled.fill(0)
    mitte("LEVEL", 6)
    mitte("GESCHAFFT!", 18)
    mitte(lv.name, 32)
    mitte("%d Versuche" % versuche, 44)
    if uebung:
        oled.text("(Uebung)", 32, 56)
    zeige()
    for i in range(40):
        rgb(*FARBEN[i % len(FARBEN)])
        leds_balken(8 if (i // 3) % 2 else 0)
        sleep_ms(60)
        if taste(S16) or taste(SJOY):
            break


def pause():
    stille()
    oled.fill_rect(30, 22, 68, 18, 0)
    oled.rect(30, 22, 68, 18, 1)
    mitte("PAUSE", 27)
    zeige()
    while taste(S5):
        sleep_ms(10)
    while not taste(S5):
        sleep_ms(20)
    while taste(S5):
        sleep_ms(10)


def spielen(nr, rekorde, uebung, v0):
    """Spielt ein Level. Rueckgabe erst beim Sieg oder mit S4."""
    lv = Level(nr)
    melodie = MELODIEN[nr % len(MELODIEN)]
    farbe = FARBEN[nr % len(FARBEN)]
    t4 = Taste(S4)
    t5 = Taste(S5)
    versuche = 0
    checkpoint = None
    bild_ms = 1000 // MAX_FPS

    while True:                                  # ein Versuch
        versuche += 1
        sp = checkpoint.kopie() if (uebung and checkpoint) else Spieler()
        letzter_cp = sp.x
        start = ticks_ms()
        musik_start = start
        letztes = start
        rest = 0.0
        puffer_bis = 0
        alt_druck = True                         # erst loslassen
        rgb(*farbe)
        ergebnis = 0
        while ergebnis == 0:
            now = ticks_ms()
            if t4.neu():
                stille()
                return
            if t5.neu():
                pause()
                now = ticks_ms()
                letztes = now
            # Sprungtaste: S17, Joystick-Taster oder Joystick hoch
            v = vJoys.read_u16() - v0
            hoch = v > TOTZONE * 2 if HOCH_POSITIV else v < -TOTZONE * 2
            druck = taste(S17) or taste(SJOY) or hoch
            if druck and not alt_druck:
                puffer_bis = ticks_add(now, 120)
            alt_druck = druck

            # Physik in festen Schritten (gleiches Ergebnis bei jeder Bildrate)
            rest += min(ticks_diff(now, letztes), 50) / 1000.0
            letztes = now
            puffer = ticks_diff(puffer_bis, now) > 0
            while rest >= PHYS_DT and ergebnis == 0:
                rest -= PHYS_DT
                ergebnis, ring = sp.schritt(lv, druck, puffer)
                if ring:
                    puffer_bis = now
                    puffer = False
                    rgb(255, 255, 255)

            # Checkpoint im Uebungsmodus: alle 3 s, wenn man sicher steht
            if uebung and sp.boden and sp.x - letzter_cp > TEMPO * 3:
                checkpoint = sp.kopie()
                letzter_cp = sp.x
                effekt(1800, 20)

            kamera = sp.x - SPIELER_X
            p = zeichne_welt(lv, kamera, ticks_diff(now, start))
            if versuche > 1 or uebung:
                txt = "VERSUCH %d" % versuche
                oled.text(txt, 40 - int(sp.x - (checkpoint.x if uebung and checkpoint else 0)), 20)
            if uebung and checkpoint:
                cx = int(checkpoint.x - kamera) + 3
                if 0 <= cx < 128:
                    oled.line(cx, BODEN_Y - 2, cx + 2, BODEN_Y - 5, 1)
                    oled.line(cx + 2, BODEN_Y - 5, cx + 4, BODEN_Y - 2, 1)
            zeichne_wuerfel(SPIELER_X, int(sp.y), int(sp.drehung))
            zeige()
            leds_balken(int(p * 8 + 0.5))
            if rgb_stand == (255, 255, 255) and ticks_diff(now, puffer_bis) > 80:
                rgb(*farbe)
            ton_update(musik_start, melodie, True)

            warte = bild_ms - ticks_diff(ticks_ms(), now)
            if warte > 0:
                sleep_ms(warte)

        if ergebnis == ZIEL:
            if not uebung:
                rekorde[nr] = 100
                rekorde_schreiben(rekorde)
                if hub:
                    hub.eintragen("level%d" % nr, 100)
            sieg(lv, versuche, uebung)
            return
        # Absturz
        pz = prozent(sp, lv)
        if not uebung and pz > rekorde[nr]:
            rekorde[nr] = pz
            rekorde_schreiben(rekorde)
            if hub:
                hub.eintragen("level%d" % nr, pz)
        absturz_animation(lv, sp.x - SPIELER_X, SPIELER_X, int(sp.y))
        oled.fill_rect(36, 24, 56, 14, 0)
        oled.rect(36, 24, 56, 14, 1)
        mitte("%d%%" % pz, 27)
        zeige()
        sleep_ms(350)


def main():
    hardware()
    v0, h0 = mitte_messen()
    rekorde = rekorde_lesen()
    nr = 0
    uebung = False
    while True:
        nr, uebung = menue(nr, rekorde, uebung, h0)
        spielen(nr, rekorde, uebung, v0)


if __name__ == "__main__":
    main()

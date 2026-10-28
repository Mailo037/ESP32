# 3D-RENDER v2.0 - Wuerfel, Dreieck, Pyramide, Oktaeder, Tetraeder, Ikosaeder
# fuer das BZTG espBoard (MicroPython, ESP32, SSD1306 128x64)
#
# Joystick links/rechts : drehen um die Y-Achse
# Joystick oben/unten   : drehen um die X-Achse
# Joystick-Taster       : naechste Form
# S16                   : Ansicht zuruecksetzen
# S17                   : Auto-Drehung an/aus
# S4 / S5               : Zoom kleiner / groesser
# LEDs                  : zeigen, welche Form gerade dran ist
#
# Auf den ESP: main.py + ssd1306.py (beide in den Root-Ordner)

from machine import Pin, ADC, I2C
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_ms, ticks_diff
import math

# =====================================================================
#  EINSTELLUNGEN
# =====================================================================
CX, CY = 64, 35          # Bildmitte
SCALE = 20.0             # Pixel pro 3D-Einheit
PERSP = 0.04             # leichte Perspektive (0 = orthographisch)
ZOOM_MIN = 0.6
ZOOM_MAX = 1.15
TOTZONE = 9000           # Joystick-Totzone
DREH_TEMPO = 2.8         # rad/s bei Vollausschlag
AUTO_TEMPO = 0.6         # rad/s Auto-Drehung
MAX_FPS = 60             # Bildrate begrenzen (Drehtempo bleibt gleich)
I2C_FREQ = 400000        # OLED-Takt. Viele Displays schaffen 800000-1000000
ACHSEN_TAUSCHEN = False  # True, falls links/rechts und hoch/runter vertauscht sind
X_UMDREHEN = False       # Joystick links/rechts umkehren
Y_UMDREHEN = False       # Joystick hoch/runter umkehren
LED_PINS = (32, 33, 25, 26, 27, 14, 12, 13)

# Falls die Taster gedrueckt 0 liefern, auf False setzen:
TASTEN_AKTIV_HIGH = True
# =====================================================================

# ---------- Hardware ----------
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=I2C_FREQ)
oled = SSD1306_I2C(128, 64, i2c)

S16 = Pin(16, Pin.IN)
S17 = Pin(17, Pin.IN)
S4 = Pin(4, Pin.IN)
S5 = Pin(5, Pin.IN)
SJOY = Pin(2, Pin.IN)


def adc(pin):
    a = ADC(Pin(pin))
    a.atten(ADC.ATTN_11DB)   # voller Bereich 0 ... 3,3 V
    return a


hJoys = adc(34)
vJoys = adc(35)
if ACHSEN_TAUSCHEN:
    hJoys, vJoys = vJoys, hJoys

leds = [Pin(n, Pin.OUT) for n in LED_PINS]

# ---------- 3D-Daten ----------
# Wuerfel: 8 Ecken, 12 Kanten
CUBE_V = (
    (-0.58, -0.58, -0.58), (0.58, -0.58, -0.58),
    (0.58, 0.58, -0.58), (-0.58, 0.58, -0.58),
    (-0.58, -0.58, 0.58), (0.58, -0.58, 0.58),
    (0.58, 0.58, 0.58), (-0.58, 0.58, 0.58),
)
CUBE_E = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)

# Dreieck: 3 Ecken, 3 Kanten (flach in der X-Y-Ebene)
R = 1.0
TRI_V = (
    (0.0, -R, 0.0),
    (-0.866 * R, 0.5 * R, 0.0),
    (0.866 * R, 0.5 * R, 0.0),
)
TRI_E = ((0, 1), (1, 2), (2, 0))

# Pyramide: quadratische Grundflaeche + Spitze
PYRA_V = (
    (-0.7, -0.7, -0.7), (0.7, -0.7, -0.7),
    (0.7, -0.7, 0.7), (-0.7, -0.7, 0.7),
    (0.0, 1.0, 0.0),
)
PYRA_E = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 0), (4, 1), (4, 2), (4, 3),
)

# Oktaeder: 6 Ecken, 12 Kanten
OCTA_V = (
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (-1.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (0.0, -1.0, 0.0),
)
OCTA_E = (
    (0, 1), (0, 2), (0, 3), (0, 4),
    (5, 1), (5, 2), (5, 3), (5, 4),
    (1, 2), (2, 3), (3, 4), (4, 1),
)

# Tetraeder: 4 Ecken, 6 Kanten (jede Ecke mit jeder verbunden)
TETRA_V = (
    (0.8, 0.8, 0.8), (-0.8, -0.8, 0.8),
    (-0.8, 0.8, -0.8), (0.8, -0.8, -0.8),
)
TETRA_E = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def ikosaeder():
    # 12 Ecken aus drei "goldenen Rechtecken", Kanten = alle Paare
    # mit dem kuerzesten Abstand (30 Stueck)
    g = (1 + math.sqrt(5)) / 2
    s = 1.0 / math.sqrt(1 + g * g)
    v = []
    for a in (-1, 1):
        for b in (-1, 1):
            v.append((0.0, a * s, b * g * s))
            v.append((a * s, b * g * s, 0.0))
            v.append((b * g * s, 0.0, a * s))
    kanten = []
    for i in range(12):
        for j in range(i + 1, 12):
            d = sum((v[i][k] - v[j][k]) ** 2 for k in range(3))
            if d < 4 * s * s * 1.01:
                kanten.append((i, j))
    return tuple(v), tuple(kanten)


IKOSA_V, IKOSA_E = ikosaeder()

SHAPES = (
    ("WUERFEL", CUBE_V, CUBE_E),
    ("DREIECK", TRI_V, TRI_E),
    ("PYRAMIDE", PYRA_V, PYRA_E),
    ("OKTAEDER", OCTA_V, OCTA_E),
    ("TETRAEDER", TETRA_V, TETRA_E),
    ("IKOSAEDER", IKOSA_V, IKOSA_E),
)

# ---------- Hilfsfunktionen ----------
def zeige():
    # I2C-Aussetzer abfangen, damit die Demo weiterlaeuft
    try:
        oled.show()
    except OSError:
        sleep_ms(20)


def gedrueckt(pin):
    wert = bool(pin.value())
    return wert if TASTEN_AKTIV_HIGH else not wert


def mitte_messen():
    h = v = 0
    for _ in range(20):
        h += hJoys.read_u16()
        v += vJoys.read_u16()
        sleep_ms(5)
    return h // 20, v // 20


def achse(wert, mitte):
    d = wert - mitte
    if d > TOTZONE:
        w = (d - TOTZONE) / (32768 - TOTZONE)
    elif d < -TOTZONE:
        w = (d + TOTZONE) / (32768 - TOTZONE)
    else:
        return 0.0
    if w > 1.0:
        return 1.0
    if w < -1.0:
        return -1.0
    return w


def splash():
    oled.fill(0)
    oled.text("3D RENDER", 24, 1)
    oled.hline(0, 11, 128, 1)
    oled.text("Joystick drehen", 0, 18)
    oled.text("Joy-Taste Form", 0, 29)
    oled.text("S16 Reset", 0, 40)
    oled.text("S17 Auto", 64, 40)
    oled.text("S4/S5 Zoom", 24, 51)
    zeige()
    sleep_ms(1800)


def kalibrieren():
    oled.fill(0)
    oled.text("JOYSTICK", 32, 16)
    oled.text("LOSLASSEN!", 16, 30)
    oled.text("Mitte messen", 16, 44)
    zeige()
    sleep_ms(1200)
    return mitte_messen()


def leds_form(nr):
    # LED Nummer nr leuchtet (bei mehr als 8 Formen faengt es von vorn an)
    for i, led in enumerate(leds):
        led.value(1 if i == nr % len(leds) else 0)


# Projizierte Punkte werden in diese Liste geschrieben (keine neue Liste pro Bild)
PTS = [(0, 0)] * max(len(v) for _, v, _ in SHAPES)


def zeichne(verts, kanten, yaw, pitch, zoom):
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    pts = PTS
    for i, (x, y, z) in enumerate(verts):
        # Drehung um Y (Gier)
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        # Drehung um X (Nick)
        y1 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp
        # Projektion mit leichter Perspektive
        s = zoom * SCALE / (1.0 + PERSP * z2)
        pts[i] = (int(CX + x1 * s), int(CY - y1 * s))
    line = oled.line
    for a, b in kanten:
        pa = pts[a]
        pb = pts[b]
        line(pa[0], pa[1], pb[0], pb[1], 1)
    for i in range(len(verts)):
        px, py = pts[i]
        oled.hline(px - 1, py, 3, 1)
        oled.vline(px, py - 1, 3, 1)


def hud(name, auto, fps):
    oled.text(name, 0, 0)
    rechts = "%s %d" % ("A" if auto else "M", fps)
    oled.text(rechts, 128 - len(rechts) * 8, 0)
    oled.hline(0, 8, 128, 1)


def main():
    h0, v0 = kalibrieren()
    splash()

    shape = 0
    yaw = 0.6
    pitch = -0.35
    zoom = 1.0
    auto = True
    last = ticks_ms()
    fps_t = last
    frames = 0
    fps = 0
    letzte_form = 0
    bild_ms = 1000 // MAX_FPS
    leds_form(shape)

    alt_sjoy = gedrueckt(SJOY)
    alt_s16 = gedrueckt(S16)
    alt_s17 = gedrueckt(S17)
    alt_s4 = gedrueckt(S4)
    alt_s5 = gedrueckt(S5)

    while True:
        jetzt = ticks_ms()
        dt = min(ticks_diff(jetzt, last), 100) / 1000.0
        last = jetzt

        # --- Tasten mit Flankenerkennung ---
        sjoy = gedrueckt(SJOY)
        if sjoy and not alt_sjoy and ticks_diff(jetzt, letzte_form) > 250:
            shape = (shape + 1) % len(SHAPES)
            letzte_form = jetzt
            leds_form(shape)
            sleep_ms(30)                 # einfache Entprellung
        alt_sjoy = sjoy

        s16 = gedrueckt(S16)
        if s16 and not alt_s16:
            yaw, pitch, zoom = 0.6, -0.35, 1.0
        alt_s16 = s16

        s17 = gedrueckt(S17)
        if s17 and not alt_s17:
            auto = not auto
        alt_s17 = s17

        s4 = gedrueckt(S4)
        if s4 and not alt_s4:
            zoom = max(ZOOM_MIN, zoom - 0.1)
        alt_s4 = s4

        s5 = gedrueckt(S5)
        if s5 and not alt_s5:
            zoom = min(ZOOM_MAX, zoom + 0.1)
        alt_s5 = s5

        # --- Joystick ---
        hx = achse(hJoys.read_u16(), h0)
        vy = achse(vJoys.read_u16(), v0)
        if X_UMDREHEN:
            hx = -hx
        if Y_UMDREHEN:
            vy = -vy
        yaw += hx * DREH_TEMPO * dt
        pitch += vy * DREH_TEMPO * dt

        # Auto-Drehung nur, wenn der Joystick losgelassen ist
        if auto and hx == 0.0 and vy == 0.0:
            yaw += AUTO_TEMPO * dt

        yaw = yaw % (2.0 * math.pi)
        pitch = max(-1.35, min(1.35, pitch))

        # --- Zeichnen ---
        oled.fill(0)
        name, verts, kanten = SHAPES[shape]
        zeichne(verts, kanten, yaw, pitch, zoom)
        hud(name, auto, fps)
        zeige()

        # --- FPS zaehlen ---
        frames += 1
        if ticks_diff(jetzt, fps_t) >= 1000:
            fps = frames
            frames = 0
            fps_t = jetzt

        # Bildrate begrenzen
        rest = bild_ms - ticks_diff(ticks_ms(), jetzt)
        if rest > 0:
            sleep_ms(rest)


if __name__ == "__main__":
    main()

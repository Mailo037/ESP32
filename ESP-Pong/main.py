# HUB-NAME: ESP Pong
# HUB-VERSION: 2.1
# HUB-INFO: Multiplayer-Pong ueber ESP-NOW mit Lobby fuer alle Boards
# =====================================================================
#  ESP-PONG v2.0 - Multiplayer-Pong fuer BZTG espBoards ueber ESP-NOW
# =====================================================================
#  Jedes Board hat eine feste Nummer (aus der MAC-Adresse, z. B. #0427).
#  Nach dem Start landen alle Boards in der LOBBY und sehen sich dort
#  gegenseitig - mit Status und Signalstaerke.
#
#  LOBBY
#    Joystick hoch/runter : Board in der Liste auswaehlen
#    S5 (oder Joystick nach rechts / Joystick-Taster):
#                           HOST  -> beitreten
#                           FREI  -> zum Spiel einladen
#                           Einladung annehmen
#    S16                  : selbst ein Spiel eroeffnen (Host werden)
#    S4                   : abbrechen / Einladung ablehnen
#  SPIEL
#    Joystick hoch/runter : Schlaeger
#    S5 (oder Joystick rechts / Joystick-Taster): nach Spielende Revanche
#    S4                   : Match verlassen, zurueck zur Lobby
#  Poti RP3 (links oben)  : Lautstaerke (ganz links = stumm)
#
#  Auf JEDES Board kopieren: main.py + ssd1306.py (Root-Ordner)
#  Kein Router, kein Schul-WLAN - die Boards sprechen direkt.
# =====================================================================

from machine import Pin, ADC, I2C, PWM
from micropython import const
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add
import struct
import random
import network
import espnow

# =====================================================================
#  EINSTELLUNGEN
# =====================================================================
VERSION = "v2.1"            # wird in der Lobby angezeigt
NAME = ""                   # eigener Name (max. 8 Zeichen), leer = "#Nummer"
TASTEN_AKTIV_HIGH = True    # Board: 3,3 V ueber Taster, 10k Pull-down
HOCH_POSITIV = True         # Joystick: positiver ADC-Wert = nach oben
TOTZONE = 9000              # Joystick-Totzone
PADDLE_SPEED = 95.0         # px/s bei Vollausschlag
BALL_START = 85.0           # px/s beim Aufschlag
BALL_MAX = 150.0            # maximale Ballgeschwindigkeit
BALL_PLUS = 1.05            # Tempo-Faktor pro Schlaegertreffer
WIN_SCORE = 5               # Punkte fuer den Sieg (max. 4 LEDs pro Spieler)
MAX_FPS = 100               # Bildrate begrenzen (Ruhe fuer das WLAN)
I2C_FREQ = 400000           # OLED-Takt. Viele Displays schaffen 800000-1000000
TX_POWER = 8                # dBm (8 reicht fuer einen Raum, schont den Strom)
KANAL = 1                   # WLAN-Kanal, muss auf allen Boards gleich sein
STROMSPAREN_AUS = True      # WLAN-Stromsparen aus = weniger Verzoegerung
SENDE_MS = 16               # Spielstand ca. 60x pro Sekunde senden

# LEDs oben auf dem Board, von links nach rechts (P7 ... P0).
# Je 4 LEDs pro Spieler: links = Host (links), rechts = Gast (rechts).
LED_PINS = (13, 12, 14, 27, 26, 25, 33, 32)
LEDS_UMDREHEN = False       # True, falls die Haelften vertauscht sind

# RGB-LED: gruen = Spiel laeuft, blau = wartet, rot = Verbindung weg
RGB_PINS = (19, 23, 18)     # rot, gruen, blau
RGB_AN = True
RGB_HELL = 40               # 0 ... 255

# =====================================================================
#  SPIELFELD
# =====================================================================
COURT_TOP = const(12)
COURT_BOT = const(63)
PADDLE_H = const(14)
PADDLE_W = const(3)
PADDLE_L_X = const(2)
PADDLE_R_X = const(123)

# =====================================================================
#  FUNK-PROTOKOLL (alle Pakete beginnen mit MAGIC)
# =====================================================================
MAGIC = const(0xB7)
T_BEACON = const(1)   # an alle: Status, Nummer, Name
T_JOIN = const(2)     # Gast -> Host: moechte mitspielen
T_ACCEPT = const(3)   # Host -> Gast: ok
T_DENY = const(4)     # nein / Einladung abgelehnt
T_INVITE = const(5)   # Einladung
T_STATE = const(6)    # Host -> Gast: Ball, Schlaeger, Punkte
T_PADDLE = const(7)   # Gast -> Host: eigener Schlaeger
T_BYE = const(8)      # Match verlassen

# Status in der Lobby
FREI = const(0)
HOST = const(1)
SPIEL = const(2)
WARTE = const(3)
STATUS_TEXT = ("FREI", "HOST", "SPIEL", "WARTE")

# Phasen im Spiel
PH_PLAY = const(0)
PH_OVER = const(1)
PH_WAIT = const(2)
PH_SERVE = const(3)

FMT_STATE = "<BBBhhhhBBBB"   # magic typ seq bx by vx vy p1y s1 s2 phase (x16)
FMT_PADDLE = "<BBBhB"        # magic typ seq p2y(x16) neustart-zaehler
GROESSE_STATE = struct.calcsize(FMT_STATE)
GROESSE_PADDLE = struct.calcsize(FMT_PADDLE)
BROADCAST = b"\xff\xff\xff\xff\xff\xff"

# =====================================================================
#  HARDWARE
# =====================================================================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=I2C_FREQ)
oled = SSD1306_I2C(128, 64, i2c)

S16 = Pin(16, Pin.IN)
S4 = Pin(4, Pin.IN)
S5 = Pin(5, Pin.IN)
SJOY = Pin(2, Pin.IN)

if LEDS_UMDREHEN:
    LED_PINS = tuple(reversed(LED_PINS))
leds = [Pin(n, Pin.OUT) for n in LED_PINS]
led_stand = None

vJoys = ADC(Pin(35))
vJoys.atten(ADC.ATTN_11DB)
hJoys = ADC(Pin(34))
hJoys.atten(ADC.ATTN_11DB)
POTI_LAUT = ADC(Pin(39))      # Poti RP3 = Lautstaerke
POTI_LAUT.atten(ADC.ATTN_11DB)
H0 = 32768                    # Joystick-Mitte links/rechts (wird gemessen)

try:
    buzzer = PWM(Pin(15), freq=1000, duty_u16=0)
except TypeError:
    buzzer = PWM(Pin(15))
beep_until = 0

rgb_pwm = None
if RGB_AN:
    try:
        rgb_pwm = [PWM(Pin(p), freq=5000, duty_u16=0) for p in RGB_PINS]
    except Exception:
        rgb_pwm = None
rgb_stand = None


# =====================================================================
#  HILFSFUNKTIONEN
# =====================================================================
def duty_setzen(wert):
    try:
        buzzer.duty_u16(wert)
    except AttributeError:
        buzzer.duty(wert // 64)


def lautstaerke():
    """Poti RP3 (links oben) = Lautstaerke, ganz nach links = stumm.
    Der Piezo ist bei 50 % Tastverhaeltnis (duty 32768) am lautesten."""
    w = POTI_LAUT.read_u16()
    return 0 if w < 2000 else 4000 + w * 29000 // 65535


def beep(freq=1200, ms=25):
    global beep_until
    laut = lautstaerke()
    if not laut:
        return
    try:
        buzzer.freq(freq)
        duty_setzen(laut)
    except Exception:
        return
    beep_until = ticks_add(ticks_ms(), ms)


def beep_update():
    global beep_until
    if beep_until and ticks_diff(ticks_ms(), beep_until) >= 0:
        duty_setzen(0)
        beep_until = 0


def beep_aus():
    global beep_until
    beep_until = 0
    duty_setzen(0)


def rgb(r, g, b):
    global rgb_stand
    if rgb_pwm is None or rgb_stand == (r, g, b):
        return
    for kanal, wert in zip(rgb_pwm, (r, g, b)):
        kanal.duty_u16(wert * RGB_HELL * 257 // 255)
    rgb_stand = (r, g, b)


def gedrueckt(pin):
    wert = bool(pin.value())
    return wert if TASTEN_AKTIV_HIGH else not wert


class Taste:
    """Flankenerkennung: neu() ist nur beim Druecken einmal True."""

    def __init__(self, pin):
        self.pin = pin
        self.alt = gedrueckt(pin)

    def neu(self):
        jetzt = gedrueckt(self.pin)
        flanke = jetzt and not self.alt
        self.alt = jetzt
        return flanke


class Los:
    """Bestaetigen: S5, Joystick nach rechts oder Joystick-Taster."""

    def __init__(self):
        self.s5 = Taste(S5)
        self.joy = Taste(SJOY)
        self.rechts_alt = True          # erst loslassen, dann zaehlt es

    def neu(self):
        a = self.s5.neu()
        b = self.joy.neu()
        rechts = achse(hJoys.read_u16(), H0) > 0.6
        c = rechts and not self.rechts_alt
        self.rechts_alt = rechts
        return a or b or c


def leds_anzeigen(s1, s2):
    """Punkte als Leuchtbalken: links Host von aussen, rechts Gast von aussen."""
    global led_stand
    if (s1, s2) == led_stand:
        return
    for i in range(4):
        leds[i].value(1 if i < s1 else 0)
        leds[7 - i].value(1 if i < s2 else 0)
    led_stand = (s1, s2)


def leds_aus():
    leds_anzeigen(0, 0)


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


def joystick_y(v0):
    """-1 ... +1, positiv = nach oben."""
    a = achse(vJoys.read_u16(), v0)
    return a if HOCH_POSITIV else -a


def mitte_text(s, y):
    oled.text(s, max(0, (128 - len(s) * 8) // 2), y)


def zeige():
    try:
        oled.show()
    except OSError:
        sleep_ms(5)


def zeige_rect(x, y, w, h):
    try:
        oled.show_rect(x, y, w, h)
    except OSError:
        sleep_ms(5)


def bild_begrenzen(start):
    rest = 1000 // MAX_FPS - ticks_diff(ticks_ms(), start)
    if rest > 0:
        sleep_ms(rest)


def meldung_zeigen(zeile1, zeile2="", ms=1200):
    oled.fill(0)
    mitte_text(zeile1, 22)
    mitte_text(zeile2, 36)
    zeige()
    ende = ticks_add(ticks_ms(), ms)
    while ticks_diff(ende, ticks_ms()) > 0:
        beep_update()
        sleep_ms(10)


# =====================================================================
#  FUNK
# =====================================================================
class Funk:
    def __init__(self):
        oled.fill(0)
        mitte_text("ESP-NOW", 20)
        mitte_text("START...", 34)
        zeige()

        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        try:
            self.sta.disconnect()
        except Exception:
            pass
        for opt in ({"channel": KANAL}, {"txpower": TX_POWER}):
            try:
                self.sta.config(**opt)
            except Exception:
                pass
        if STROMSPAREN_AUS:
            try:
                self.sta.config(pm=self.sta.PM_NONE)
            except Exception:
                pass

        self.mac = bytes(self.sta.config("mac"))
        self.nr = ((self.mac[4] << 8) | self.mac[5]) % 10000
        name = "".join(c for c in NAME.strip().upper() if " " <= c <= "~")[:8]
        self.name = name if name else "#%04d" % self.nr

        self.e = espnow.ESPNow()
        self.e.active(True)
        self.peers = []
        self.peer_dazu(BROADCAST)
        self.beacon_zeit = 0
        self.beacon_buf = bytearray(struct.pack("<BBBH", MAGIC, T_BEACON, FREI, self.nr)
                                    + name.encode())

    def peer_dazu(self, mac):
        if mac in self.peers:
            return
        if len(self.peers) >= 15:          # ESP-NOW erlaubt max. 20 Peers
            self.peer_weg(self.peers[1])   # [0] ist Broadcast
        try:
            self.e.add_peer(mac)
        except OSError:
            pass                           # schon bekannt
        self.peers.append(mac)

    def peer_weg(self, mac):
        if mac == BROADCAST or mac not in self.peers:
            return
        try:
            self.e.del_peer(mac)
        except OSError:
            pass
        self.peers.remove(mac)

    def senden(self, mac, daten):
        if mac != BROADCAST:
            self.peer_dazu(mac)
        try:
            # sync=False: nicht auf die Quittung warten -> keine Ruckler
            self.e.send(mac, daten, False)
        except OSError:
            pass

    def kurz(self, mac, typ):
        self.senden(mac, bytes((MAGIC, typ)))

    def empfangen(self):
        """Liefert (mac, nachricht) oder (None, None). Ohne Speicher-Neuanlage."""
        try:
            mac, msg = self.e.irecv(0)
        except OSError:
            return None, None
        if not msg or len(msg) < 2 or msg[0] != MAGIC:
            return None, None
        return mac, msg

    def beacon(self, status, intervall=500):
        jetzt = ticks_ms()
        if ticks_diff(jetzt, self.beacon_zeit) < intervall:
            return
        self.beacon_zeit = jetzt
        self.beacon_buf[2] = status
        self.senden(BROADCAST, self.beacon_buf)

    def rssi(self, mac):
        try:
            return self.e.peers_table[mac][0]
        except Exception:
            return None

    def leeren(self):
        while True:
            mac, _ = self.empfangen()
            if mac is None:
                try:
                    if not self.e.any():
                        return
                except Exception:
                    return


# =====================================================================
#  STARTBILD + KALIBRIEREN
# =====================================================================
def kalibrieren():
    global H0
    oled.fill(0)
    mitte_text("ESP-PONG " + VERSION, 4)
    oled.hline(0, 14, 128, 1)
    mitte_text("JOYSTICK", 24)
    mitte_text("LOSLASSEN!", 36)
    mitte_text("Mitte messen...", 50)
    zeige()
    sleep_ms(900)
    summe = h = 0
    for _ in range(30):
        summe += vJoys.read_u16()
        h += hJoys.read_u16()
        sleep_ms(8)
    H0 = h // 30
    return summe // 30


# =====================================================================
#  LOBBY
# =====================================================================
def signal_balken(x, y, rssi):
    if rssi is None:
        return
    stufe = 3 if rssi > -60 else (2 if rssi > -72 else (1 if rssi > -85 else 0))
    for i in range(3):
        h = 2 + i * 2
        if i < stufe:
            oled.fill_rect(x + i * 3, y + 7 - h, 2, h, 1)
        else:
            oled.pixel(x + i * 3, y + 6, 1)


def board_name(boards, mac):
    b = boards.get(mac)
    return b[1] if b else "?"


def lobby(funk, v0, meldung=None):
    """Zeigt alle Boards. Gibt (rolle, mac, name) zurueck, sobald ein
    Spiel startet. rolle ist HOST (linker Schlaeger) oder SPIEL (Gast)."""
    boards = {}            # mac -> [nr, name, status, zuletzt]
    auswahl = 0
    oben = 0               # erster sichtbarer Eintrag
    status = FREI
    partner = None         # HOST/WARTE: nur dieser darf beitreten (None = alle)
    warte_bis = 0
    verbinde_zeit = 0
    verbinde = None        # [mac, start, letzter_versuch]
    einladung = None       # [mac, name, bis]
    blaettern = 0
    neu_zeichnen = True
    letztes_bild = 0
    if meldung:
        meldung = [meldung, ticks_add(ticks_ms(), 2000)]
    los = Los()
    t16 = Taste(S16)
    t4 = Taste(S4)
    leds_aus()

    while True:
        now = ticks_ms()
        beep_update()

        # ---------- Funk ----------
        while True:
            mac, msg = funk.empfangen()
            if mac is None:
                break
            typ = msg[1]
            if typ == T_BEACON and len(msg) >= 5:
                mac = bytes(mac)
                nr = msg[3] | (msg[4] << 8)
                try:
                    name = bytes(msg[5:13]).decode()
                except Exception:
                    name = ""
                eintrag = boards.get(mac)
                if eintrag is None or eintrag[2] != msg[2]:
                    neu_zeichnen = True
                boards[mac] = [nr, name or "#%04d" % nr, msg[2], now]
            elif typ == T_JOIN and status in (HOST, WARTE):
                mac = bytes(mac)
                if partner is None or partner == mac:
                    funk.kurz(mac, T_ACCEPT)
                    beep(1200, 80)
                    return HOST, mac, board_name(boards, mac)
                funk.kurz(mac, T_DENY)
            elif typ == T_ACCEPT and verbinde and bytes(mac) == verbinde[0]:
                beep(1200, 80)
                return SPIEL, verbinde[0], board_name(boards, verbinde[0])
            elif typ == T_DENY:
                mac = bytes(mac)
                if verbinde and mac == verbinde[0]:
                    verbinde = None
                    meldung = ["ABGELEHNT", ticks_add(now, 1500)]
                    beep(300, 150)
                elif status == WARTE and mac == partner:
                    status = FREI
                    partner = None
                    meldung = ["ABGELEHNT", ticks_add(now, 1500)]
                    beep(300, 150)
                neu_zeichnen = True
            elif typ == T_INVITE:
                mac = bytes(mac)
                if status == FREI and verbinde is None and einladung is None:
                    einladung = [mac, board_name(boards, mac), ticks_add(now, 10000)]
                    beep(1500, 60)
                    neu_zeichnen = True
                elif status == WARTE and mac == partner:
                    # Beide haben sich gleichzeitig eingeladen:
                    # das Board mit der groesseren MAC wird Gast.
                    if funk.mac > mac:
                        status = FREI
                        partner = None
                        verbinde = [mac, now, 0]
                        neu_zeichnen = True
                elif einladung is None or einladung[0] != mac:
                    funk.kurz(mac, T_DENY)

        # Boards, die sich 2,5 s nicht gemeldet haben, verschwinden
        for mac in [m for m, b in boards.items() if ticks_diff(now, b[3]) > 2500]:
            del boards[mac]
            neu_zeichnen = True
        liste = sorted(boards.items(), key=lambda kv: kv[1][0])
        if auswahl >= len(liste):
            auswahl = max(0, len(liste) - 1)

        funk.beacon(status)

        # ---------- Eingaben ----------
        j = los.neu()
        s16 = t16.neu()
        s4 = t4.neu()
        y = joystick_y(v0)

        if einladung:
            if j:
                verbinde = [einladung[0], now, 0]
                einladung = None
                beep(1000, 40)
            elif s4 or ticks_diff(now, einladung[2]) > 0:
                funk.kurz(einladung[0], T_DENY)
                einladung = None
                beep(500, 60)
            if einladung is None:
                neu_zeichnen = True

        elif verbinde:
            if ticks_diff(now, verbinde[2]) > 250:     # alle 250 ms anfragen
                funk.kurz(verbinde[0], T_JOIN)
                verbinde[2] = now
            if s4 or ticks_diff(now, verbinde[1]) > 2500:
                if not s4:
                    meldung = ["KEINE ANTWORT", ticks_add(now, 1500)]
                    beep(300, 150)
                verbinde = None
                neu_zeichnen = True

        elif status in (HOST, WARTE):
            if s4:
                status = FREI
                partner = None
                beep(500, 60)
                neu_zeichnen = True
            elif status == WARTE:
                if ticks_diff(now, warte_bis) > 0:
                    status = FREI
                    partner = None
                    meldung = ["KEINE ANTWORT", ticks_add(now, 1500)]
                    beep(300, 150)
                    neu_zeichnen = True
                elif ticks_diff(now, verbinde_zeit) > 1000:
                    funk.kurz(partner, T_INVITE)   # Einladung wiederholen
                    verbinde_zeit = now

        else:
            # Auswahl mit dem Joystick (mit Wiederholung beim Festhalten)
            if y > 0.5 or y < -0.5:
                if ticks_diff(now, blaettern) > 0:
                    auswahl += -1 if y > 0 else 1
                    auswahl = max(0, min(auswahl, len(liste) - 1))
                    blaettern = ticks_add(now, 220)
                    neu_zeichnen = True
            else:
                blaettern = 0

            if s16:
                status = HOST
                partner = None
                beep(1000, 40)
                neu_zeichnen = True
            elif j and liste:
                mac, (nr, name, st, _) = liste[auswahl]
                if st == HOST:
                    verbinde = [mac, now, 0]
                    beep(1000, 40)
                elif st == FREI:
                    status = WARTE
                    partner = mac
                    warte_bis = ticks_add(now, 10000)
                    verbinde_zeit = now
                    funk.kurz(mac, T_INVITE)
                    beep(1000, 40)
                else:
                    meldung = ["BESETZT", ticks_add(now, 1200)]
                    beep(300, 100)
                neu_zeichnen = True

        if meldung and ticks_diff(now, meldung[1]) > 0:
            meldung = None
            neu_zeichnen = True

        # ---------- Anzeige (max. ca. 8x pro Sekunde reicht) ----------
        if neu_zeichnen or ticks_diff(now, letztes_bild) > 400:
            neu_zeichnen = False
            letztes_bild = now
            if auswahl < oben:
                oben = auswahl
            elif auswahl > oben + 3:
                oben = auswahl - 3
            lobby_zeichnen(funk, liste, auswahl, oben, status, partner,
                           boards, verbinde, einladung, meldung)
            if status == FREI and not verbinde:
                rgb(0, 0, 0)
            else:
                rgb(0, 0, 255)

        sleep_ms(15)


def lobby_zeichnen(funk, liste, auswahl, oben, status, partner, boards,
                   verbinde, einladung, meldung):
    oled.fill(0)
    oled.text("PONG", 0, 0)
    oled.text(funk.name, 128 - len(funk.name) * 8, 0)
    oled.hline(0, 9, 128, 1)

    if verbinde:
        mitte_text("VERBINDE MIT", 20)
        b = boards.get(verbinde[0])
        mitte_text(b[1] if b else "?", 32)
        oled.text("S4=Abbruch", 0, 56)
    elif status == HOST:
        mitte_text("DU BIST HOST", 16)
        mitte_text("Warte auf", 30)
        mitte_text("Gegner...", 40)
        oled.text("S4=Abbruch", 0, 56)
    elif status == WARTE:
        mitte_text("EINLADUNG AN", 18)
        b = boards.get(partner)
        mitte_text(b[1] if b else "?", 30)
        mitte_text("gesendet...", 42)
        oled.text("S4=Abbruch", 0, 56)
    elif not liste:
        mitte_text("Suche Boards...", 22)
        mitte_text("S16 = Host", 36)
        oled.text(VERSION, 0, 56)
    else:
        for zeile in range(4):
            i = oben + zeile
            if i >= len(liste):
                break
            mac, (nr, name, st, _) = liste[i]
            y = 12 + zeile * 10
            text = "%-8s %s" % (name[:8], STATUS_TEXT[st] if st < 4 else "?")
            if i == auswahl:
                oled.fill_rect(0, y - 1, 118, 10, 1)
                oled.text(text, 1, y, 0)
            else:
                oled.text(text, 1, y, 1)
            signal_balken(119, y, funk.rssi(mac))
        if len(liste) > 4:     # Scrollbalken
            h = max(4, 40 * 4 // len(liste))
            oled.vline(127, 11 + (40 - h) * oben // (len(liste) - 4), h, 1)
        oled.text("S5=Los  S16=Host", 0, 56)

    if einladung:
        oled.fill_rect(4, 14, 120, 40, 0)
        oled.rect(4, 14, 120, 40, 1)
        mitte_text(einladung[1], 18)
        mitte_text("laedt dich ein", 28)
        mitte_text("S5=Ja  S4=Nein", 42)
    elif meldung:
        oled.fill_rect(8, 24, 112, 16, 0)
        oled.rect(8, 24, 112, 16, 1)
        mitte_text(meldung[0], 28)
    zeige()


# =====================================================================
#  SPIELZUSTAND (rechnet nur der Host)
# =====================================================================
class PongSpiel:
    def __init__(self):
        self.neustart()

    def neustart(self):
        self.s1 = 0
        self.s2 = 0
        self.p1_y = (COURT_TOP + COURT_BOT - PADDLE_H) / 2.0
        self.p2_y = self.p1_y
        self.mitte()
        self.phase = PH_WAIT
        self.serve_at = 0
        self.serve_dir = 1
        self.over_since = 0

    def mitte(self):
        self.ball_x = 64.0
        self.ball_y = (COURT_TOP + COURT_BOT) / 2.0
        self.vx = 0.0
        self.vy = 0.0

    def schlaeger(self, achse_y, dt):
        self.p1_y -= achse_y * PADDLE_SPEED * dt
        if self.p1_y < COURT_TOP:
            self.p1_y = COURT_TOP
        elif self.p1_y > COURT_BOT - PADDLE_H:
            self.p1_y = COURT_BOT - PADDLE_H

    def aufschlag(self, richtung, now, delay=900):
        self.mitte()
        self.serve_dir = richtung
        self.phase = PH_SERVE
        self.serve_at = ticks_add(now, delay)

    def punkt(self, wer, now):
        if wer == 1:
            self.s1 += 1
        else:
            self.s2 += 1
        if self.s1 >= WIN_SCORE or self.s2 >= WIN_SCORE:
            self.phase = PH_OVER
            self.over_since = now
            self.mitte()
            beep(400, 250)
        else:
            # Aufschlag in Richtung des Spielers, der den Punkt gemacht hat
            self.aufschlag(1 if wer == 1 else -1, now)
            beep(600, 80)

    def begrenzen(self):
        if self.vx > BALL_MAX:
            self.vx = BALL_MAX
        elif self.vx < -BALL_MAX:
            self.vx = -BALL_MAX
        vy_max = BALL_MAX * 0.75
        if self.vy > vy_max:
            self.vy = vy_max
        elif self.vy < -vy_max:
            self.vy = -vy_max

    def update(self, dt, now):
        """Bewegt den Ball. Gibt True zurueck, wenn sich die Richtung
        geaendert hat (dann sofort an den Gast senden)."""
        if self.phase == PH_SERVE:
            if ticks_diff(now, self.serve_at) >= 0:
                self.phase = PH_PLAY
                self.vx = self.serve_dir * BALL_START
                self.vy = random.uniform(-25.0, 25.0)
                beep(1100, 40)
                return True
            return False
        if self.phase != PH_PLAY:
            return False

        # In kleinen Schritten bewegen, damit der Ball nicht durch
        # die Schlaeger springt.
        schritte = 1 + int((abs(self.vx) + abs(self.vy)) * dt / 2.0)
        sdt = dt / schritte
        ereignis = False
        for _ in range(schritte):
            self.ball_x += self.vx * sdt
            self.ball_y += self.vy * sdt
            bx = self.ball_x
            by = self.ball_y

            # oben / unten abprallen
            if by < COURT_TOP + 1:
                self.ball_y = COURT_TOP + 1
                self.vy = abs(self.vy)
                beep(700, 10)
                ereignis = True
            elif by > COURT_BOT - 1:
                self.ball_y = COURT_BOT - 1
                self.vy = -abs(self.vy)
                beep(700, 10)
                ereignis = True

            # linker Schlaeger (Host)
            if self.vx < 0 and PADDLE_L_X - 1 <= bx <= PADDLE_L_X + PADDLE_W + 1:
                if self.p1_y - 1 <= by <= self.p1_y + PADDLE_H + 1:
                    self.ball_x = PADDLE_L_X + PADDLE_W + 1
                    self.vx = abs(self.vx) * BALL_PLUS
                    self.vy += (by - (self.p1_y + PADDLE_H / 2.0)) * 2.0
                    self.begrenzen()
                    beep(1500, 15)
                    ereignis = True
                    continue

            # rechter Schlaeger (Gast)
            if self.vx > 0 and PADDLE_R_X - 1 <= bx <= PADDLE_R_X + PADDLE_W + 1:
                if self.p2_y - 1 <= by <= self.p2_y + PADDLE_H + 1:
                    self.ball_x = PADDLE_R_X - 1
                    self.vx = -abs(self.vx) * BALL_PLUS
                    self.vy += (by - (self.p2_y + PADDLE_H / 2.0)) * 2.0
                    self.begrenzen()
                    beep(1500, 15)
                    ereignis = True
                    continue

            # Tor
            if bx < -2:
                self.punkt(2, now)
                return True
            if bx > 130:
                self.punkt(1, now)
                return True
        return ereignis


# =====================================================================
#  ANZEIGE IM SPIEL
#  Es wird immer das ganze Bild im Speicher gezeichnet (schnell), aber
#  nur die Stellen zum Display geschickt, die sich geaendert haben.
# =====================================================================
class Feld:
    def __init__(self, links, rechts):
        self.links = links
        self.rechts = rechts
        self.alt = None      # (kopf, hinweis, bx, by, p1, p2)

    def ungueltig(self):
        self.alt = None

    def zeichnen(self, s1, s2, bx, by, p1, p2, hinweis):
        bx = int(bx)
        by = int(by)
        p1 = int(p1)
        p2 = int(p2)
        kopf = (s1, s2)

        oled.fill(0)
        oled.text(self.links, 0, 1)
        mitte_text("%d:%d" % (s1, s2), 1)
        oled.text(self.rechts, 128 - len(self.rechts) * 8, 1)
        oled.hline(0, 10, 128, 1)
        for y in range(COURT_TOP, 64, 7):          # Mittellinie
            oled.vline(63, y, 3, 1)
        oled.fill_rect(PADDLE_L_X, p1, PADDLE_W, PADDLE_H, 1)
        oled.fill_rect(PADDLE_R_X, p2, PADDLE_W, PADDLE_H, 1)
        oled.fill_rect(bx - 1, by - 1, 3, 3, 1)
        if hinweis:
            oled.fill_rect(10, 29, 108, 12, 0)
            oled.rect(10, 29, 108, 12, 1)
            mitte_text(hinweis, 31)

        alt = self.alt
        self.alt = (kopf, hinweis, bx, by, p1, p2)
        if alt is None or alt[0] != kopf or alt[1] != hinweis:
            zeige()                                # alles neu
            return
        _, _, obx, oby, op1, op2 = alt
        if obx != bx or oby != by:                 # Ball alt + neu
            x0 = min(obx, bx) - 1
            y0 = min(oby, by) - 1
            zeige_rect(x0, y0, max(obx, bx) + 2 - x0, max(oby, by) + 2 - y0)
        if op1 != p1:
            y0 = min(op1, p1)
            zeige_rect(PADDLE_L_X, y0, PADDLE_W, max(op1, p1) + PADDLE_H - y0)
        if op2 != p2:
            y0 = min(op2, p2)
            zeige_rect(PADDLE_R_X, y0, PADDLE_W, max(op2, p2) + PADDLE_H - y0)


def zeichne_ende(s1, s2, links, rechts, ich_links):
    oled.fill(0)
    mitte_text("SPIEL VORBEI", 1)
    oled.hline(0, 10, 128, 1)
    gewinner_links = s1 > s2
    mitte_text(links if gewinner_links else rechts, 14)
    mitte_text("GEWINNT! %d:%d" % (s1, s2), 24)
    if gewinner_links == ich_links:
        oled.text("*", 0, 14)
        oled.text("*", 120, 14)
    oled.hline(0, 35, 128, 1)
    mitte_text("S5 = Revanche", 40)
    mitte_text("S4 = Lobby", 52)
    zeige()


# =====================================================================
#  HOST (linker Schlaeger, rechnet das Spiel)
# =====================================================================
def host_loop(funk, v0, gast, gast_name):
    spiel = PongSpiel()
    feld = Feld(funk.name[:5], gast_name[:5])
    los = Los()
    t4 = Taste(S4)
    letztes = ticks_ms()
    letzter_gast = letztes
    gast_gesehen = False
    verbunden_war = False
    restart_zaehler = None
    seq = 0
    letztes_senden = 0
    ende_gezeigt = False
    puffer = bytearray(GROESSE_STATE)
    funk.peer_dazu(gast)

    while True:
        now = ticks_ms()
        dt = ticks_diff(now, letztes) / 1000.0
        if dt > 0.05:
            dt = 0.05
        letztes = now
        beep_update()

        if t4.neu():
            funk.kurz(gast, T_BYE)
            beep(800, 60)
            funk.peer_weg(gast)
            return "MATCH VERLASSEN"

        # --- Nachrichten ---
        while True:
            mac, msg = funk.empfangen()
            if mac is None:
                break
            if mac != gast:
                continue
            typ = msg[1]
            if typ == T_PADDLE and len(msg) >= GROESSE_PADDLE:
                _, _, _, y16, rz = struct.unpack_from(FMT_PADDLE, msg)
                y = y16 / 16.0
                if y < COURT_TOP:
                    y = COURT_TOP
                elif y > COURT_BOT - PADDLE_H:
                    y = COURT_BOT - PADDLE_H
                spiel.p2_y = y
                letzter_gast = now
                gast_gesehen = True
                if restart_zaehler is not None and rz != restart_zaehler \
                        and spiel.phase == PH_OVER:
                    spiel.neustart()
                    spiel.aufschlag(random.choice((-1, 1)), now)
                    beep(900, 60)
                restart_zaehler = rz
            elif typ == T_JOIN:
                funk.kurz(gast, T_ACCEPT)     # Antwort ging verloren
            elif typ == T_BYE:
                funk.peer_weg(gast)
                return "GEGNER WEG"

        # --- Verbindung pruefen ---
        weg_ms = ticks_diff(now, letzter_gast)
        verbunden = gast_gesehen and weg_ms < 1000
        if verbunden and not verbunden_war:
            if spiel.phase == PH_WAIT:
                spiel.aufschlag(random.choice((-1, 1)), now)
            feld.ungueltig()
            beep(1200, 80)
        elif not verbunden and verbunden_war:
            if spiel.phase in (PH_PLAY, PH_SERVE):
                spiel.phase = PH_WAIT
                spiel.mitte()
        verbunden_war = verbunden
        if weg_ms > 5000:
            funk.peer_weg(gast)
            return "VERBINDUNG WEG"

        # --- eigener Schlaeger + Spiel ---
        spiel.schlaeger(joystick_y(v0), dt)
        ereignis = False
        if spiel.phase == PH_OVER:
            if los.neu() or ticks_diff(now, spiel.over_since) > 15000:
                spiel.neustart()
                spiel.aufschlag(random.choice((-1, 1)), now)
                beep(900, 60)
                ereignis = True
        else:
            los.neu()
            ereignis = spiel.update(dt, now)

        leds_anzeigen(spiel.s1, spiel.s2)
        funk.beacon(SPIEL, 1000)

        # --- Zustand senden: regelmaessig und sofort bei Richtungswechsel ---
        if ereignis or ticks_diff(now, letztes_senden) >= SENDE_MS:
            letztes_senden = now
            seq = (seq + 1) & 0xFF
            struct.pack_into(FMT_STATE, puffer, 0, MAGIC, T_STATE, seq,
                             int(spiel.ball_x * 16), int(spiel.ball_y * 16),
                             int(spiel.vx * 16), int(spiel.vy * 16),
                             int(spiel.p1_y), spiel.s1, spiel.s2, spiel.phase)
            funk.senden(gast, puffer)

        # --- Zeichnen ---
        if spiel.phase == PH_OVER:
            if not ende_gezeigt:
                zeichne_ende(spiel.s1, spiel.s2, feld.links, feld.rechts, True)
                ende_gezeigt = True
                feld.ungueltig()
            rgb(0, 0, 255)
        else:
            ende_gezeigt = False
            hinweis = None
            if spiel.phase == PH_WAIT:
                hinweis = "WARTE AUF GAST" if not gast_gesehen else "VERBINDUNG..."
            feld.zeichnen(spiel.s1, spiel.s2, spiel.ball_x, spiel.ball_y,
                          spiel.p1_y, spiel.p2_y, hinweis)
            if verbunden:
                rgb(0, 255, 0)
            else:
                rgb(255, 0, 0)

        bild_begrenzen(now)


# =====================================================================
#  GAST (rechter Schlaeger)
# =====================================================================
def gast_loop(funk, v0, host, host_name):
    p2_y = (COURT_TOP + COURT_BOT - PADDLE_H) / 2.0
    feld = Feld(host_name[:5], funk.name[:5])
    los = Los()
    t4 = Taste(S4)
    letztes = ticks_ms()
    letzter_state = letztes
    state = None           # [bx, by, vx, vy, p1, s1, s2, phase]
    letzte_seq = None
    restart_zaehler = 0
    seq = 0
    letztes_senden = 0
    letzte_y16 = None
    ende_gezeigt = False
    puffer = bytearray(GROESSE_PADDLE)
    funk.peer_dazu(host)

    while True:
        now = ticks_ms()
        dt = ticks_diff(now, letztes) / 1000.0
        if dt > 0.05:
            dt = 0.05
        letztes = now
        beep_update()

        if t4.neu():
            funk.kurz(host, T_BYE)
            beep(800, 60)
            funk.peer_weg(host)
            return "MATCH VERLASSEN"

        # --- Nachrichten ---
        while True:
            mac, msg = funk.empfangen()
            if mac is None:
                break
            if mac != host:
                continue
            typ = msg[1]
            if typ == T_STATE and len(msg) >= GROESSE_STATE:
                (_, _, s, bx, by, vx, vy, p1, s1, s2,
                 phase) = struct.unpack_from(FMT_STATE, msg)
                # alte (verspaetete) Pakete ignorieren
                if letzte_seq is not None and ((s - letzte_seq) & 0xFF) > 128:
                    continue
                letzte_seq = s
                vx /= 16.0
                vy /= 16.0
                if state is not None:
                    # Toene wie beim Host
                    if phase == PH_PLAY and state[7] == PH_PLAY:
                        if (vx > 0) != (state[2] > 0):
                            beep(1500, 15)
                        elif (vy > 0) != (state[3] > 0):
                            beep(700, 10)
                    if (s1, s2) != (state[5], state[6]):
                        if phase == PH_OVER:
                            beep(400, 250)
                        else:
                            beep(600, 80)
                    if phase == PH_PLAY and state[7] == PH_SERVE:
                        beep(1100, 40)
                state = [bx / 16.0, by / 16.0, vx, vy, p1, s1, s2, phase]
                letzter_state = now
            elif typ == T_BYE:
                funk.peer_weg(host)
                return "GEGNER WEG"

        # --- eigener Schlaeger (sofort, ohne auf den Host zu warten) ---
        p2_y -= joystick_y(v0) * PADDLE_SPEED * dt
        if p2_y < COURT_TOP:
            p2_y = COURT_TOP
        elif p2_y > COURT_BOT - PADDLE_H:
            p2_y = COURT_BOT - PADDLE_H

        if state is not None and state[7] == PH_OVER and los.neu():
            restart_zaehler = (restart_zaehler + 1) & 0xFF
            beep(900, 40)
            letzte_y16 = None          # sofort senden
        else:
            los.neu()

        # --- Schlaeger senden (bei Aenderung, sonst alle 100 ms) ---
        y16 = int(p2_y * 16)
        if (y16 != letzte_y16 and ticks_diff(now, letztes_senden) >= SENDE_MS) \
                or ticks_diff(now, letztes_senden) >= 100:
            letztes_senden = now
            letzte_y16 = y16
            seq = (seq + 1) & 0xFF
            struct.pack_into(FMT_PADDLE, puffer, 0, MAGIC, T_PADDLE, seq,
                             y16, restart_zaehler)
            funk.senden(host, puffer)

        funk.beacon(SPIEL, 1000)

        # --- Anzeige ---
        weg_ms = ticks_diff(now, letzter_state)
        if weg_ms > 5000:
            funk.peer_weg(host)
            return "VERBINDUNG WEG"

        if state is None:
            feld.zeichnen(0, 0, 64, 37, 25, p2_y, "WARTE AUF HOST")
            rgb(0, 0, 255)
        else:
            bx, by, vx, vy, p1, s1, s2, phase = state
            leds_anzeigen(s1, s2)
            if phase == PH_OVER:
                if not ende_gezeigt:
                    zeichne_ende(s1, s2, feld.links, feld.rechts, False)
                    ende_gezeigt = True
                    feld.ungueltig()
                rgb(0, 0, 255)
            else:
                ende_gezeigt = False
                if phase == PH_PLAY:
                    # Ball zwischen zwei Paketen selbst weiterrechnen
                    t = min(weg_ms, 120) / 1000.0
                    bx += vx * t
                    by += vy * t
                    if by < COURT_TOP + 1:
                        by = 2 * (COURT_TOP + 1) - by
                    elif by > COURT_BOT - 1:
                        by = 2 * (COURT_BOT - 1) - by
                hinweis = None
                if weg_ms > 1000:
                    hinweis = "VERBINDUNG..."
                elif phase == PH_WAIT:
                    hinweis = "PAUSE"
                feld.zeichnen(s1, s2, bx, by, p1, p2_y, hinweis)
                if weg_ms > 1000:
                    rgb(255, 0, 0)
                else:
                    rgb(0, 255, 0)

        bild_begrenzen(now)


# =====================================================================
#  START
# =====================================================================
def main():
    v0 = kalibrieren()
    funk = Funk()
    meldung = None
    while True:
        rolle, partner, name = lobby(funk, v0, meldung)
        funk.leeren()
        if rolle == HOST:
            meldung = host_loop(funk, v0, partner, name)
        else:
            meldung = gast_loop(funk, v0, partner, name)
        beep_aus()
        leds_aus()
        rgb(0, 0, 0)
        meldung_zeigen(meldung)
        meldung = None


if __name__ == "__main__":
    main()

# OTA updates of the Hub Python firmware (not the MicroPython runtime).
import os
import json
import time

FILES = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")
UPDATE = "/hubupdate"


def manifest_pruefen(meta):
    files = meta.get("dateien", [])
    if len(files) != len(FILES) or set(d.get("name") for d in files) != set(FILES):
        raise ValueError("Invalid firmware file list")
    if len(meta.get("id", "")) != 64 or any(c not in "0123456789abcdef" for c in meta["id"]):
        raise ValueError("Invalid firmware ID")
    for d in files:
        if not isinstance(d.get("groesse"), int) or not 0 < d["groesse"] <= 256 * 1024 or len(d.get("sha256", "")) != 64:
            raise ValueError("Invalid firmware file")
    if sum(d["groesse"] for d in files) > 512 * 1024:
        raise ValueError("Firmware too large")


def installieren(netz, meta, oled):
    import hub_apps as ha
    import machine
    manifest_pruefen(meta)
    try:
        os.stat(UPDATE + "/pending.json")
    except OSError:
        pass
    else:
        raise OSError("Neustart zum Update-Fortsetzen")
    # Stage + temporary replacement of the largest file + filesystem reserve.
    biggest = max(d["groesse"] for d in meta["dateien"])
    need = sum(d["groesse"] for d in meta["dateien"]) + 16384
    for name in FILES:
        try:
            size = os.stat("/" + name)[6]
            need += size
            biggest = max(biggest, size)
        except OSError:
            pass
    need += biggest
    ha.loeschen(UPDATE)
    if ha.frei() < need:
        raise OSError("Not enough flash")
    os.mkdir(UPDATE)
    for i, d in enumerate(meta["dateien"]):
        ha.meldung(oled, "Hub update", d["name"][:16])
        netz.datei_laden("firmware/" + meta["id"] + "/" + d["name"], UPDATE + "/" + d["name"], d,
                         lambda x: ha.balken(oled, 54, (i + x) / len(FILES)))
        if d["name"].endswith(".py"):
            with open(UPDATE + "/" + d["name"]) as f:
                source = f.read()
            compile(source, d["name"], "exec")
            source = None
            import gc
            gc.collect()
    with open(UPDATE + "/hub_version.json") as f:
        if json.load(f).get("version") != meta["version"]:
            raise ValueError("Firmware version mismatch")
    with open(UPDATE + "/pending.neu", "w") as f:
        json.dump(meta, f)
    getattr(os, "sync", lambda: None)()
    os.rename(UPDATE + "/pending.neu", UPDATE + "/pending.json")
    getattr(os, "sync", lambda: None)()
    # Installation here follows an explicit confirmation and may retry a release
    # previously rejected by the recovery bootstrap.
    try:
        os.remove("/hubbackup/fehlgeschlagen.json")
    except OSError:
        pass
    ha.meldung(oled, "Hub update", "Restarting ...")
    machine.reset()


def pruefen(netz=None, automatisch=False):
    """Check before entering a game or gallery. Offline always remains usable."""
    import hub_apps as ha
    import hub_online
    k = hub_online.konfig_lesen()
    if not k:
        return
    eigen = netz is None
    netz = netz or hub_online.Netz(k, 30000)
    try:
        if eigen:
            netz.verbinden()
            netz.melden()
        meta = netz.firmware()
        if not meta or not ha.neuer(meta.get("version"), ha.HUB_VERSION):
            return
        failed = hub_online._json_lesen("/hubbackup/fehlgeschlagen.json", {})
        if automatisch and failed.get("version") == meta.get("version"):
            return
        manifest_pruefen(meta)
        oled = ha.oled_neu()
        ein = ha.Eingabe()
        while True:
            choice = ha.menue(oled, ein, "HUB-UPDATE", ["v" + ha.HUB_VERSION, "> v" + meta["version"]], ["Install", "Later"])
            if choice != 0:
                return
            try:
                netz.bis = time.ticks_add(time.ticks_ms(), 300000)
                installieren(netz, meta, oled)
                return
            except Exception as error:
                print("Hub update:", error)
                ha.fehler_dialog(oled, ein, "Update failed", error)
    except Exception as error:
        print("Hub update offline:", error)
        hub_online.diagnose(error)
    finally:
        if eigen:
            netz.trennen()


# =====================================================================
#  Schlanke Funk-Modi: WLAN-Setup und Repeater
# =====================================================================
#  Der WLAN-Treiber braucht viel zusammenhaengenden Speicher. Nach Galerie
#  und Hub-Modulen ist der zu zerstueckelt ("WiFi Out of Memory", das Board
#  blieb stehen). Darum laufen diese Modi nach einem Neustart: main.py
#  startet den Treiber vor allen Hub-Imports und ruft funk_modus() auf.
#  Dieser Teil kommt deshalb ohne hub_apps und hub_online aus - die sind
#  zu gross, um neben dem Treiber noch kompiliert zu werden. Er steht in
#  hub_update.py, weil die Firmware-Dateiliste fest ist (OTA).
# =====================================================================
import machine

KONFIG = "/hub_online.json"
CACHE = "/hubdaten"
STANDARD_URL = "https://esphub-steel.vercel.app"
AN = 1                      # Taster aktiv high (wie hub_apps.AN)


def board_id():
    return "".join("%02x" % b for b in machine.unique_id())


def konfig_lesen():
    try:
        with open(KONFIG) as f:
            k = json.load(f)
        return k if k.get("url") else None
    except (OSError, ValueError):
        return None


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


class Tasten:
    """Wie hub_apps.Eingabe, nur Taster: hoch, runter, ok, zurueck."""

    def __init__(self):
        from machine import Pin
        self.pins = ((Pin(17, Pin.IN), "hoch"), (Pin(16, Pin.IN), "runter"), (Pin(5, Pin.IN), "ok"),
                     (Pin(2, Pin.IN), "ok"), (Pin(4, Pin.IN), "zurueck"))
        self.alt = ()

    def gedrueckt(self):
        return [n for p, n in self.pins if p.value() == AN]

    def lesen(self):
        g = self.gedrueckt()
        e = None
        for k in g:
            if k not in self.alt:
                e = k
                break
        self.alt = g
        return e

    def warte_los(self):
        while self.gedrueckt():
            time.sleep_ms(20)
        self.alt = ()


class _Anzeige:
    """Die paar Bildschirm-Helfer aus hub_apps, die die Funk-Modi brauchen."""

    @staticmethod
    def kopfzeile(oled, text, rechts=""):
        oled.fill(0)
        oled.fill_rect(0, 0, 128, 10, 1)
        oled.text(text[:16], 1, 1, 0)
        if rechts:
            oled.text(rechts, 127 - 8 * len(rechts), 1, 0)

    @staticmethod
    def meldung(oled, z1, z2="", z3=""):
        oled.fill(0)
        for i, z in enumerate((z1, z2, z3)):
            if z:
                oled.text(z[:16], 64 - 4 * len(z[:16]), 16 + 12 * i, 1)
        oled.show()

    @staticmethod
    def fehler_dialog(oled, ein, titel, error):
        print(titel + ":", error)
        text = str(error)[:80]
        _Anzeige.kopfzeile(oled, titel)
        for i in range(0, min(len(text), 64), 16):
            oled.text(text[i:i + 16], 0, 14 + 10 * (i // 16), 1)
        oled.text("S5/S4 = OK", 0, 56, 1)
        oled.show()
        ein.warte_los()
        while ein.lesen() not in ("ok", "zurueck"):
            time.sleep_ms(20)
        ein.warte_los()


ha = _Anzeige


def _oled():
    from machine import Pin, I2C
    from ssd1306 import SSD1306_I2C
    return SSD1306_I2C(128, 64, I2C(0, scl=Pin(22), sda=Pin(21), freq=400000))


class _Netz:
    """Eigenes WLAN + requests fuer den Repeater-Betrieb (statt hub_online.Netz)."""

    def __init__(self, k):
        self.k = k
        self.req = None

    def verbinden(self):
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            sta.connect(self.k.get("wlan", ""), self.k.get("passwort", ""))
            start = time.ticks_ms()
            while not sta.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > 15000:
                    raise OSError("Wi-Fi unavailable")
                time.sleep_ms(100)
        try:
            import requests
        except ImportError:
            import urequests as requests
        self.req = requests


def funk_modus(modus):
    """Von main.py aufgerufen, Treiber laeuft schon. Jeder Modus endet mit
    einem Neustart in die normale Galerie (ohne Treiber im Speicher)."""
    import gc
    gc.collect()
    print("Hub radio mode:", modus, "free:", gc.mem_free())
    oled = _oled()
    ein = Tasten()
    try:
        if modus == "auto":
            ha.meldung(oled, "Looking for", "a repeater ...")
            if repeater_suchen(auto=True):
                ha.meldung(oled, "Online via", "repeater")
                time.sleep_ms(1000)
        elif modus == "wlan":
            wlan_einrichten(oled, ein)
        elif modus == "suche":
            repeater_einrichten(oled, ein)
        else:
            k = konfig_lesen()
            if not k or k.get("modus") == "repeater" or not k.get("wlan"):
                raise OSError("Needs own Wi-Fi")
            ha.meldung(oled, "Repeater", "connecting ...")
            netz = _Netz(k)
            netz.verbinden()
            gc.collect()
            print("Repeater ready, free:", gc.mem_free())
            repeater_betreiben(oled, ein, netz)
    except Exception as e:
        ha.fehler_dialog(oled, ein, "Wi-Fi", e)
    ha.meldung(oled, "Restarting ...")
    time.sleep_ms(300)
    machine.reset()


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


SETUP_MS = 300000


def _setup_bildschirm(oled, ssid, password, ip, rest_ms, zeile=""):
    """Live screen: the running countdown shows the board still responds."""
    s = max(0, rest_ms) // 1000
    ha.kopfzeile(oled, "WI-FI SETUP", "%d:%02d" % (s // 60, s % 60))
    oled.text(ssid[:16], 0, 13, 1)
    oled.text(("PW " + password)[:16], 0, 23, 1)
    oled.text(ip[:16], 0, 33, 1)
    oled.hline(0, 44, 128, 1)
    oled.text((zeile or "S4 = Cancel")[:16], 0, 52, 1)
    oled.show()


def _setup_antwort(client, status, page):
    try:
        body = ('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP-Hub Wi-Fi</title><style>body{font:18px system-ui;max-width:30rem;margin:2rem auto;padding:1rem}label,input,button{display:block;margin:1rem 0}input,button{font:inherit;padding:.6rem;box-sizing:border-box;max-width:100%}</style>' + page).encode()
        client.sendall(('HTTP/1.1 ' + status + '\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nX-Frame-Options: DENY\r\nContent-Security-Policy: default-src \'none\'; style-src \'unsafe-inline\'; form-action \'self\'; frame-ancestors \'none\'\r\nConnection: close\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode() + body)
    except OSError:
        pass


class _Umleitung(Exception):
    pass


def _dns_antwort(q, ip):
    """Jede DNS-Frage mit der eigenen IP beantworten. So merkt das Handy,
    dass es ein Anmelde-Netz ist, und oeffnet die Setup-Seite von selbst."""
    if len(q) < 17 or q[2] & 0x80:
        return None
    i = 12
    while i < len(q) and q[i]:
        i += q[i] + 1
    if i + 5 > len(q):
        return None
    frage = q[12:i + 5]
    if q[i + 1:i + 3] != b"\x00\x01":              # nur A-Eintraege, sonst leer
        return q[:2] + b"\x81\x80\x00\x01\x00\x00\x00\x00\x00\x00" + frage
    return (q[:2] + b"\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + frage +
            b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes(int(x) for x in ip.split(".")))


def _setup_anfrage(client, ip, csrf):
    """Read one request. Returns (page, (wlan, passwort) or None)."""
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
    if headers.get("host") not in (ip, ip + ":80"):
        if method == "GET":
            raise _Umleitung()      # Anmelde-Pruefung des Handys -> Setup-Seite
        raise ValueError("Request did not come from the setup page")
    if headers.get("origin", "http://" + ip) != "http://" + ip:
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
        # The check runs after this reply: joining the home network moves the
        # setup network to its channel, so the phone may drop off briefly.
        return ("<h1>Checking Wi-Fi ...</h1><p>Watch the board display. If the details work, "
                "the board saves them and restarts. Otherwise reconnect to the setup network "
                "and open this page again.</p>"), (wlan, pw)
    if method == "GET" and path == "/":
        return ('<h1>Set up ESP-Hub</h1><form method="post"><input type="hidden" name="csrf" value="' + csrf + '"><label>Wi-Fi name<input name="wlan" maxlength="32" required autocomplete="off"></label><label>Wi-Fi password<input type="password" name="passwort" maxlength="63" autocomplete="new-password"></label><button>Connect and save</button></form><p>Leave the password blank for open Wi-Fi. Press S4 on the board to cancel.</p>'), None
    raise ValueError("Unknown page")


def wlan_einrichten(oled, ein):
    """Explicit, password-protected AP; credentials stay on this board."""
    import network
    import socket
    import select
    import binascii
    password = binascii.hexlify(os.urandom(6)).decode()
    csrf = binascii.hexlify(os.urandom(16)).decode()
    ssid = "ESP-Hub-" + board_id()[-4:]
    ap = network.WLAN(network.AP_IF)
    server = None
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(False)
        # Switch the AP on before configuring it: MicroPython builds differ
        # in whether config() works while the Wi-Fi driver is stopped.
        ap.active(True)
        ap.config(essid=ssid, password=password, authmode=3)
        ip = ap.ifconfig()[0]
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, 80))
        server.listen(2)
        # accept() with settimeout() can block for good on the ESP32 - then
        # neither S4 nor the five-minute limit react and the board looks
        # frozen. A non-blocking socket plus poll() keeps the loop running.
        server.setblocking(False)
        poller = select.poll()
        poller.register(server, select.POLLIN)
        dns = None
        try:
            dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            dns.bind((ip, 53))
            dns.setblocking(False)
            poller.register(dns, select.POLLIN)
        except OSError:
            dns = None              # ohne DNS: IP von Hand im Browser eingeben
        start = time.ticks_ms()
        shown = None
        ein.warte_los()
        while True:
            rest = SETUP_MS - time.ticks_diff(time.ticks_ms(), start)
            if rest <= 0:
                return False
            if rest // 1000 != shown:
                shown = rest // 1000
                _setup_bildschirm(oled, ssid, password, ip, rest)
            if ein.lesen() == "zurueck":
                return False
            bereit = [e[0] for e in poller.poll(30)]
            if dns is not None and any(b is dns for b in bereit):
                try:
                    q, adresse = dns.recvfrom(512)
                    a = _dns_antwort(q, ip)
                    if a:
                        dns.sendto(a, adresse)
                except OSError:
                    pass
            if not any(b is server for b in bereit):
                continue
            try:
                client, address = server.accept()
            except OSError:
                continue
            daten = None
            try:
                page, daten = _setup_anfrage(client, ip, csrf)
                status = "200 OK"
            except _Umleitung:
                try:
                    client.sendall(("HTTP/1.1 302 Found\r\nLocation: http://" + ip + "/\r\nCache-Control: no-store\r\n"
                                    "Content-Length: 0\r\nConnection: close\r\n\r\n").encode())
                except OSError:
                    pass
                client.close()
                continue
            except Exception:
                # No request text or submitted password is reflected into HTML/logs.
                page = '<h1>Setup was not saved</h1><p>Check your Wi-Fi details and connection.</p><a href="/">Try again</a>'
                status = "400 Bad Request"
            _setup_antwort(client, status, page)
            client.close()
            if daten is None:
                continue
            # Verify the new network before replacing the old configuration.
            _setup_bildschirm(oled, ssid, password, ip, rest, "Checking Wi-Fi")
            sta.active(True)
            sta.connect(daten[0], daten[1])
            begonnen = time.ticks_ms()
            while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), begonnen) < 10000:
                if ein.lesen() == "zurueck":
                    return False
                time.sleep_ms(100)
            if sta.isconnected():
                config = konfig_lesen() or {"url": STANDARD_URL, "auth": ""}
                config.update(wlan=daten[0], passwort=daten[1])
                config.pop("modus", None)
                config.pop("auto", None)
                _json_schreiben(KONFIG, config)
                ha.meldung(oled, "Wi-Fi saved", "Restarting ...")
                time.sleep_ms(800)
                machine.reset()
                return True
            try:
                sta.disconnect()
            except OSError:
                pass
            sta.active(False)
            _setup_bildschirm(oled, ssid, password, ip, rest, "Failed - retry")
            time.sleep_ms(1500)
            shown = None
    except Exception as error:
        ha.fehler_dialog(oled, ein, "Wi-Fi setup", error)
        return False
    finally:
        if server:
            server.close()
        if dns:
            dns.close()
        sta.active(False)
        ap.active(False)


# =====================================================================
#  Repeater: Boards ohne eigenes WLAN gehen ueber ein anderes Board online
# =====================================================================
#  Ein Board mit WLAN startet in Board info "Be a repeater". Andere Boards
#  waehlen bei "Set up Wi-Fi" den Punkt "Via repeater". Ihre HTTP-Anfragen
#  gehen dann per ESP-NOW an den Repeater, der sie ueber sein WLAN an den
#  Hub-Server schickt und die Antwort Stueck fuer Stueck zurueckfunkt.
#
#  Rahmen (max. 250 Bytes):
#    HR? <nonce>                 Suche (Broadcast, Client)
#    HR! <nonce>                 Antwort des Repeaters
#    HQ/HS id seq(2) letzt daten Anfrage / Antwort, Stueck fuer Stueck
#    HA id seq(2)                Quittung fuer ein Stueck
#    HX id                       Abbruch (Client schliesst die Antwort)
#  Stueck 0 ist ein JSON-Kopf, danach folgt der Body. Jedes Stueck wird
#  quittiert, so laeuft kein Empfangspuffer ueber und grosse Downloads
#  brauchen nicht mehr RAM als ein Stueck.
#
#  Der Repeater leitet nur an seine eigene Server-URL (und Store-URL)
#  weiter, nie an beliebige Adressen.
# =====================================================================
STUECK = 240
BROADCAST = b"\xff" * 6
MERKER = CACHE + "/_repeater.json"   # zuletzt gefundener Repeater


class Abbruch(Exception):
    pass


def _rahmen(typ, mid, seq, letzt, daten=b""):
    return typ + bytes((mid, seq >> 8, seq & 255, 1 if letzt else 0)) + daten


def _quittung(mid, seq):
    return b"HA" + bytes((mid, seq >> 8, seq & 255))


class Funk:
    """ESP-NOW auf dem Kanal der STA-Schnittstelle."""

    def __init__(self, kanal=None):
        import network
        import espnow
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        try:
            # Mit WLAN-Verbindung verpasst der Stromsparmodus ESP-NOW-Rahmen
            self.sta.config(pm=self.sta.PM_NONE)
        except (AttributeError, OSError, ValueError):
            pass
        if kanal:
            self.kanal(kanal)
        self.e = espnow.ESPNow()
        self.e.active(True)
        self.peers = set()
        self.peer(BROADCAST)

    def kanal(self, k=None):
        if k is None:
            return self.sta.config("channel")
        try:
            self.sta.disconnect()
        except OSError:
            pass
        self.sta.config(channel=k)

    def peer(self, mac):
        if mac not in self.peers:
            try:
                self.e.add_peer(mac)
            except OSError:
                pass
            self.peers.add(mac)

    def senden(self, mac, msg):
        self.peer(mac)
        try:
            return self.e.send(mac, msg, True)
        except OSError:
            return False

    def empfangen(self, ms):
        try:
            return self.e.recv(ms)
        except OSError:
            return None, None

    def aus(self):
        try:
            self.e.active(False)
        except Exception:
            pass


def _mit_quittung(funk, mac, msg, mid, seq, geduldig=False):
    """Ein Stueck senden, bis es quittiert ist. geduldig: ohne Quittung
    trotzdem weiter (der Empfaenger hat es wohl, ist aber beschaeftigt)."""
    for _ in range(8):
        funk.senden(mac, msg)
        ende = time.ticks_add(time.ticks_ms(), 300)
        while time.ticks_diff(ende, time.ticks_ms()) > 0:
            m, a = funk.empfangen(30)
            if not a or m != mac or len(a) < 3:
                continue
            if a[:2] == b"HA" and len(a) >= 5 and a[2] == mid and ((a[3] << 8) | a[4]) == seq:
                return
            if a[:2] == b"HX" and a[2] == mid:
                raise Abbruch()
            if msg[:2] == b"HS" and a[:2] == b"HQ" and len(a) >= 5:
                if a[2] == mid:
                    # Wiederholtes Stueck der Anfrage: deren Quittung ging verloren
                    funk.senden(mac, _quittung(mid, (a[3] << 8) | a[4]))
                    continue
                # Neue Anfrage: der Client ist mit dieser Antwort fertig,
                # nur die letzte Quittung ging verloren. Er wiederholt sie.
                raise Abbruch()
            if msg[:2] == b"HQ" and a[:2] == b"HS" and a[2] == mid:
                return              # die Antwort kommt schon: Anfrage ist da
    if not geduldig:
        raise OSError("Repeater not responding")


def _strom(funk, mac, typ, mid, quelle):
    """Stuecke aus quelle() senden; quelle liefert b"" am Ende."""
    seq = 0
    jetzt = quelle()
    while True:
        naechstes = quelle() if jetzt else b""
        # Letztes Stueck einer Anfrage: der Repeater fragt evtl. schon den
        # Server und hoert nicht zu - dann entscheidet das Warten auf die Antwort
        _mit_quittung(funk, mac, _rahmen(typ, mid, seq, not naechstes, jetzt), mid, seq,
                      typ == b"HQ" and not naechstes)
        if not naechstes:
            return
        jetzt = naechstes
        seq += 1


def _stuecke(kopf, body):
    """Quelle: erst der Kopf als eigenes Stueck, dann der Body."""
    teile = [kopf]
    pos = [0]

    def quelle():
        if teile:
            return teile.pop()
        t = body[pos[0]:pos[0] + STUECK]
        pos[0] += len(t)
        return t
    return quelle


class _Empfang:
    """Stuecke einer Nachricht der Reihe nach annehmen und quittieren."""

    def __init__(self, funk, mac, typ, mid):
        self.funk, self.mac, self.typ, self.mid = funk, mac, typ, mid
        self.seq = 0
        self.fertig = False

    def annehmen(self, a):
        """Gibt die Daten eines neuen Stuecks zurueck, sonst None."""
        if a[:2] != self.typ or len(a) < 6 or a[2] != self.mid:
            return None
        seq = (a[3] << 8) | a[4]
        if seq == self.seq - 1:                   # Quittung ging verloren
            self.funk.senden(self.mac, _quittung(self.mid, seq))
            return None
        if seq != self.seq:
            return None
        self.funk.senden(self.mac, _quittung(self.mid, seq))
        self.seq += 1
        self.fertig = a[5] == 1
        return a[6:]

    def naechstes(self, ms):
        ende = time.ticks_add(time.ticks_ms(), ms)
        while time.ticks_diff(ende, time.ticks_ms()) > 0:
            m, a = self.funk.empfangen(50)
            if a and m == self.mac:
                d = self.annehmen(a)
                if d is not None:
                    return d
        raise OSError("Repeater timeout")


# ---------------------------------------------------------------------
#  Client: steht in Netz.req und spricht wie requests
# ---------------------------------------------------------------------
class _Roh:
    def __init__(self, antwort):
        self.a = antwort

    def read(self, n=-1):
        return self.a.lesen(n)


class Antwort:
    def __init__(self, client, empfang, ms):
        self.c, self.emp = client, empfang
        self.puffer = b""
        kopf = json.loads(empfang.naechstes(ms))
        self.status_code = kopf.get("s", 502)
        self.raw = _Roh(self)
        self._inhalt = None

    def lesen(self, n=-1):
        while not self.emp.fertig and (n < 0 or len(self.puffer) < n):
            self.puffer += self.emp.naechstes(8000)
        if n < 0:
            n = len(self.puffer)
        t, self.puffer = self.puffer[:n], self.puffer[n:]
        return t

    @property
    def content(self):
        if self._inhalt is None:
            self._inhalt = self.lesen()
        return self._inhalt

    @property
    def text(self):
        return self.content.decode()

    def json(self):
        return json.loads(self.content)

    def close(self):
        if not self.emp.fertig:
            self.c.funk.senden(self.c.mac, b"HX" + bytes((self.emp.mid,)))
            self.emp.fertig = True


class RepeaterClient:
    def __init__(self):
        self.funk = None
        self.mac = None
        self.mid = 0

    def verbinden(self, rest=None):
        """Repeater suchen: zuerst der zuletzt benutzte Kanal."""
        merker = {}
        try:
            with open(MERKER) as f:
                merker = json.load(f)
        except (OSError, ValueError):
            pass
        kanaele = list(range(1, 14))
        if merker.get("kanal") in kanaele:
            kanaele.remove(merker["kanal"])
            kanaele.insert(0, merker["kanal"])
        self.funk = Funk(kanaele[0])
        nonce = os.urandom(4)
        kanaele = kanaele[:1] * 3 + kanaele + kanaele      # Funkpakete gehen verloren
        for k in kanaele:
            if rest:
                rest()
            self.funk.kanal(k)
            self.funk.senden(BROADCAST, b"HR?" + nonce)
            ende = time.ticks_add(time.ticks_ms(), 100)
            while time.ticks_diff(ende, time.ticks_ms()) > 0:
                m, a = self.funk.empfangen(30)
                if a == b"HR!" + nonce:
                    self.mac = m
                    self.funk.peer(m)
                    if merker.get("kanal") != k:
                        try:
                            os.mkdir(CACHE)
                        except OSError:
                            pass
                        with open(MERKER, "w") as f:
                            json.dump({"kanal": k}, f)
                    return k
        raise OSError("No repeater found")

    def request(self, methode, url, timeout=5, data=None, headers=None):
        self.mid = (self.mid + 1) & 255
        kopf = json.dumps({"m": methode, "u": url, "h": headers or {}}).encode()
        if len(kopf) > STUECK:
            raise OSError("Repeater: request header too long")
        body = data.encode() if isinstance(data, str) else (data or b"")
        try:
            _strom(self.funk, self.mac, b"HQ", self.mid, _stuecke(kopf, body))
        except Abbruch:
            raise OSError("Repeater aborted")
        # Der Repeater braucht selbst bis zu ~8 s fuer HTTPS
        return Antwort(self, _Empfang(self.funk, self.mac, b"HS", self.mid), timeout * 1000 + 9000)

    def beenden(self):
        if self.funk:
            self.funk.aus()
            try:
                self.funk.sta.active(False)
            except Exception:
                pass
        self.funk = None


# ---------------------------------------------------------------------
#  Repeater-Betrieb (Board mit eigenem WLAN)
# ---------------------------------------------------------------------
def _erlaubt(url, konfig):
    for basis in (konfig.get("url"), konfig.get("store")):
        if basis and url.startswith(basis.rstrip("/") + "/"):
            return True
    return False


def _weiterleiten(funk, mac, mid, kopf, body, req, konfig):
    try:
        info = json.loads(kopf)
        url = info["u"]
        if not _erlaubt(url, konfig):
            raise ValueError("URL not allowed")
    except (ValueError, KeyError):
        fehler = json.dumps({"error": "Repeater: request refused"}).encode()
        _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": 403}).encode(), fehler))
        return
    try:
        r = req.request(info.get("m", "GET"), url, timeout=8, data=body or None, headers=info.get("h") or {})
    except Exception:
        fehler = json.dumps({"error": "Repeater: server unreachable"}).encode()
        _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": 502}).encode(), fehler))
        return
    try:
        roh = getattr(r, "raw", None)
        if roh is None:                          # Simulator: alles auf einmal
            _strom(funk, mac, b"HS", mid, _stuecke(json.dumps({"s": r.status_code}).encode(), r.content))
            return
        teile = [json.dumps({"s": r.status_code}).encode()]

        def quelle():
            if teile:
                return teile.pop()
            return roh.read(STUECK) or b""
        _strom(funk, mac, b"HS", mid, quelle)
    finally:
        r.close()


def repeater_betreiben(oled, ein, netz, stopp=None):
    """Bis S4 Anfragen anderer Boards weiterleiten. netz ist verbunden."""
    funk = Funk()
    kanal = funk.kanal()
    laufend = {}        # mac -> [_Empfang, kopf, body]
    erledigt = {}       # mac -> id der zuletzt beantworteten Anfrage
    zaehler = 0
    gezeigt = None
    ein.warte_los()
    try:
        while True:
            if gezeigt != zaehler:
                gezeigt = zaehler
                ha.kopfzeile(oled, "REPEATER", "ch%d" % kanal)
                oled.text("Other boards:", 0, 14, 1)
                oled.text("Set up Wi-Fi >", 0, 24, 1)
                oled.text("Via repeater", 0, 34, 1)
                oled.hline(0, 44, 128, 1)
                oled.text(("%d req  S4=Stop" % zaehler)[:16], 0, 52, 1)
                oled.show()
            if ein.lesen() == "zurueck" or (stopp and stopp()):
                return zaehler
            m, a = funk.empfangen(30)
            if not a:
                continue
            if a[:3] == b"HR?" and len(a) == 7:
                funk.senden(m, b"HR!" + a[3:])
                continue
            if a[:2] != b"HQ" or len(a) < 6:
                continue
            mid, seq = a[2], (a[3] << 8) | a[4]
            if erledigt.get(m) == mid:
                # Spaete Wiederholung einer schon beantworteten Anfrage
                funk.senden(m, _quittung(mid, seq))
                continue
            z = laufend.get(m)
            if seq == 0 and (z is None or z[0].mid != mid):
                z = laufend[m] = [_Empfang(funk, m, b"HQ", mid), None, b""]
            if z is None:
                continue
            d = z[0].annehmen(a)
            if d is None:
                continue
            if z[1] is None:
                z[1] = d
            else:
                z[2] += d
                if len(z[2]) > 16384:            # kein Board schickt so viel
                    del laufend[m]
                    continue
            if z[0].fertig:
                del laufend[m]
                erledigt[m] = mid
                try:
                    _weiterleiten(funk, m, mid, z[1], z[2], netz.req, netz.k)
                except (OSError, Abbruch):
                    pass
                zaehler += 1
    finally:
        funk.aus()


def repeater_suchen(auto=False):
    """Repeater suchen; gefunden -> modus=repeater speichern. Kanal oder False."""
    c = RepeaterClient()
    try:
        kanal = c.verbinden()
    except OSError:
        return False
    finally:
        c.beenden()
    config = konfig_lesen() or {"url": STANDARD_URL, "auth": ""}
    config["modus"] = "repeater"
    if auto:
        config["auto"] = True
    _json_schreiben(KONFIG, config)
    return kanal


def repeater_einrichten(oled, ein):
    """'Via repeater': Repeater suchen und die Einstellung speichern."""
    ha.meldung(oled, "Searching", "repeater ...", "")
    kanal = repeater_suchen()
    if not kanal:
        ha.fehler_dialog(oled, ein, "Repeater", "No repeater found. Start 'Be a repeater' on a board with Wi-Fi.")
        return False
    ha.meldung(oled, "Repeater found", "channel %d" % kanal, "saved")
    time.sleep_ms(1500)
    return True

# =====================================================================
#  ESP-Hub: Galerie, App-Store und Board-Info
# =====================================================================
#  Wird nur geladen, wenn kein Spiel laeuft - kostet Spielen keinen RAM.
# =====================================================================
import gc
import time
from machine import Pin, ADC, PWM
import hub_apps as ha
import hub_online

ZULETZT_DATEI = "/hub_zuletzt.txt"
LED_PINS = (13, 12, 14, 27, 26, 25, 33, 32)   # P7 ... P0
ZEILEN = 4
ZEILE_Y = 12
ZEILE_H = 10
STORE = "\x01store"            # Sondereintraege in der Liste
INFO = "\x01info"


class _Ton:
    def __init__(self):
        self.poti = ADC(Pin(39))
        try:
            self.poti.atten(ADC.ATTN_11DB)
        except Exception:
            pass
        try:
            self.pwm = PWM(Pin(15), freq=2000, duty_u16=0)
        except Exception:
            self.pwm = None

    def piep(self, f, ms=18):
        w = self.poti.read_u16()
        if self.pwm is None or w < 2000:         # RP3 ganz links = stumm
            return
        self.pwm.freq(f)
        self.pwm.duty_u16(4000 + w * 29000 // 65535)
        time.sleep_ms(ms)
        self.pwm.duty_u16(0)


def pfeil(oled, x, y, c):
    """Update-Pfeil (7x8)."""
    oled.vline(x + 3, y + 1, 7, c)
    oled.hline(x + 2, y + 2, 3, c)
    oled.hline(x + 1, y + 3, 5, c)
    oled.pixel(x + 3, y, c)


def wolke(oled, x, y, c):
    oled.fill_rect(x + 3, y, 4, 2, c)
    oled.fill_rect(x + 1, y + 2, 9, 3, c)
    oled.fill_rect(x, y + 4, 11, 3, c)


def lies(datei):
    try:
        with open(datei) as f:
            return f.read().strip()
    except OSError:
        return ""


# =====================================================================
#  GALERIE
# =====================================================================
def galerie(start_datei, neustart):
    for p in LED_PINS + (19, 23, 18):
        Pin(p, Pin.OUT, value=0)
    ton = _Ton()
    oled = ha.oled_neu()
    # Joystick-Mitte messen (beim Einschalten loslassen)
    jx, jy = ADC(Pin(34)), ADC(Pin(35))
    x0 = y0 = 0
    for _ in range(16):
        x0 += jx.read_u16()
        y0 += jy.read_u16()
        time.sleep_ms(3)
    ein = ha.Eingabe(x0 // 16, y0 // 16)
    online = hub_online.konfig_lesen() is not None

    def laden():
        liste = ha.apps()
        koepfe = {n: ha.kopf(n) for n in liste}
        kat = hub_online.katalog_lokal()
        updates = {}
        for n in liste:
            koepfe[n]["lokal"] = not ha.vertraut(n)
            a = kat.get(n)
            # lokale Apps bekommen keine Updates aus dem Store
            if a and not koepfe[n]["lokal"] and ha.neuer(a.get("version"), koepfe[n]["version"]):
                updates[n] = a
        return liste + ([STORE] if online else []) + [INFO], koepfe, updates

    # Auftraege aus dem Web (Fern-Installation) zuerst erledigen. Nach dem
    # Einschalten einmal nachfragen; nach einem Spiel hat der Hub gerade
    # abgeglichen und kennt die Auftraege schon.
    import machine
    kalt = getattr(machine, "reset_cause", lambda: 0)() != getattr(machine, "SOFT_RESET", 5)
    if online and (kalt or auftraege_offen()):
        auftraege_ausfuehren(oled)

    eintraege, koepfe, updates = laden()
    zuletzt = lies(ZULETZT_DATEI)
    wahl = eintraege.index(zuletzt) if zuletzt in eintraege else 0
    oben = 0
    frei = ha.frei()

    def zeichnen():
        ha.kopfzeile(oled, "ESP-HUB", ha.kb(frei) if frei else "")
        if online:
            wolke(oled, 62, 2, 0)
        for i in range(ZEILEN):
            n = oben + i
            if n >= len(eintraege):
                break
            e = eintraege[n]
            y = ZEILE_Y + i * ZEILE_H
            c = 0 if n == wahl else 1
            if n == wahl:
                oled.fill_rect(0, y - 1, 122, ZEILE_H, 1)
            if e == STORE:
                text = "+ App-Store"
            elif e == INFO:
                text = "i Board-Info"
            else:
                text = koepfe[e]["name"][:13]
            oled.text(text, 2, y, c)
            if e in updates:
                pfeil(oled, 113, y, c)
        if len(eintraege) > ZEILEN:
            h = max(4, ZEILEN * ZEILE_H * ZEILEN // len(eintraege))
            y = ZEILE_Y - 1 + (ZEILEN * ZEILE_H - h) * oben // (len(eintraege) - ZEILEN)
            oled.fill_rect(124, y, 3, h, 1)
        oled.hline(0, 53, 128, 1)
        e = eintraege[wahl]
        if e in (STORE, INFO):
            oled.text("S5 = Oeffnen", 16, 56, 1)
        else:
            v = koepfe[e]["version"] or "?"
            links = "v" + v + (">" + updates[e]["version"] if e in updates else "")
            oled.text(links[:8], 0, 56, 1)
            oled.text("S4 Menue", 64, 56, 1)
        oled.show()
        for i, p in enumerate(LED_PINS):
            Pin(p).value(1 if i == wahl % 8 else 0)

    zeichnen()
    ein.warte_los()       # ein noch gehaltenes S4+S5 loest nichts aus
    while True:
        e = ein.lesen()
        if e in ("hoch", "runter"):
            wahl = (wahl + (-1 if e == "hoch" else 1)) % len(eintraege)
            oben = min(max(oben, wahl - ZEILEN + 1), wahl)
            ton.piep(1800 if e == "hoch" else 1500)
            zeichnen()
        elif e in ("ok", "zurueck"):
            sel = eintraege[wahl]
            if sel == STORE:
                store(oled, ein, ton)
            elif sel == INFO:
                info(oled, ein)
            elif e == "ok":
                starten(oled, sel, koepfe[sel], ton, start_datei, neustart)
            else:
                app_menue(oled, ein, ton, sel, koepfe[sel], updates.get(sel), start_datei, neustart)
            eintraege, koepfe, updates = laden()
            wahl = min(wahl, len(eintraege) - 1)
            oben = min(max(0, min(oben, wahl)), max(0, len(eintraege) - ZEILEN))
            frei = ha.frei()
            gc.collect()
            zeichnen()
        time.sleep_ms(15)


def starten(oled, name, k, ton, start_datei, neustart):
    ha.kopfzeile(oled, "STARTE")
    t = k["name"][:16]
    oled.text(t, 64 - 4 * len(t), 14, 1)
    if k["version"]:
        v = "v" + k["version"]
        oled.text(v, 64 - 4 * len(v), 24, 1)
    oled.hline(0, 34, 128, 1)
    oled.text("Menue: S4+S16", 12, 38, 1)
    oled.text("Ende:  S4+S5", 12, 48, 1)
    oled.text("(halten)", 32, 57, 1)
    oled.show()
    ton.piep(1300, 40)
    ton.piep(2000, 60)
    with open(start_datei, "w") as f:
        f.write(name)
    with open(ZULETZT_DATEI, "w") as f:
        f.write(name)
    time.sleep_ms(1200)
    neustart()


def app_menue(oled, ein, ton, name, k, update, start_datei, neustart):
    gekoppelt = hub_online.konfig_lesen() is not None and hub_online.board_status().get("konto")
    while True:
        punkte = ["Starten"]
        if update:
            punkte.append("Update auf " + update["version"])
        if k.get("lokal") and gekoppelt:
            punkte += ["In Konto laden", "Zur Pruefung"]
        punkte += ["Daten loeschen", "Deinstallieren", "Zurueck"]
        w = ha.menue(oled, ein, k["name"], ha.info_zeilen(name, k, lokal=k.get("lokal")), punkte)
        p = punkte[w] if w >= 0 else "Zurueck"
        if p in ("In Konto laden", "Zur Pruefung"):
            ziel = "privat" if p == "In Konto laden" else "pruefung"
            if ha.frage(oled, ein, "HOCHLADEN", k["name"],
                        "in dein Konto?" if ziel == "privat" else "zur Pruefung?"):
                hochladen(oled, name, ziel)
            continue
        if p == "Starten":
            starten(oled, name, k, ton, start_datei, neustart)
        elif p.startswith("Update"):
            if installieren(oled, [update]):
                return
        elif p == "Daten loeschen":
            if ha.frage(oled, ein, "SPIELSTAND", "Deinen Spiel-", "stand loeschen?"):
                ha.daten_loeschen(name)
                ha.meldung(oled, "Spielstand", "geloescht")
                time.sleep_ms(900)
        elif p == "Deinstallieren":
            if ha.frage(oled, ein, "DEINSTALLIEREN", k["name"], "entfernen?"):
                ha.app_loeschen(name)
                ha.meldung(oled, k["name"], "entfernt")
                time.sleep_ms(900)
                return
        else:
            return


# =====================================================================
#  APP-STORE
# =====================================================================
def installieren(oled, apps, netz=None):
    """Apps aus dem Store laden. Gibt True zurueck, wenn alles geklappt hat."""
    eigenes_netz = netz is None
    try:
        if eigenes_netz:
            ha.meldung(oled, "App-Store", "verbinde ...")
            netz = hub_online.Netz(hub_online.konfig_lesen())
            netz.verbinden()
        for a in apps:
            # Platz fuer die neue Datei (+ Reserve) muss da sein, die alte
            # Version wird erst nach erfolgreichem Download ersetzt
            if ha.frei() < a["groesse"] + 8192:
                ha.meldung(oled, "Zu wenig", "Speicher!", ha.kb(a["groesse"]) + " noetig")
                time.sleep_ms(2000)
                return False
            ha.meldung(oled, "Lade", a["name"][:16], "v" + a["version"])
            ziel = ha.datei(a["id"])
            netz.app_laden(a, ziel + ".neu", lambda x: ha.balken(oled, 54, x))
            ha.loeschen(ziel)
            import os
            os.rename(ziel + ".neu", ziel)
            ha.installiert_merken(a["id"], a["sha256"])     # vertrauenswuerdig
        ha.meldung(oled, "Fertig!", "%d App%s" % (len(apps), "" if len(apps) == 1 else "s"))
        time.sleep_ms(900)
        return True
    except Exception as e:
        ha.meldung(oled, "Fehler", str(e)[:16], str(e)[16:32])
        time.sleep_ms(2500)
        return False
    finally:
        if eigenes_netz and netz is not None:
            netz.trennen()


def store(oled, ein, ton):
    k = hub_online.konfig_lesen()
    if k is None:
        return
    ha.meldung(oled, "App-Store", "verbinde ...")
    netz = hub_online.Netz(k)
    try:
        netz.verbinden()
        netz.melden()
        kat = netz.katalog()
    except Exception as e:
        netz.trennen()
        ha.meldung(oled, "Store offline", str(e)[:16], str(e)[16:32])
        time.sleep_ms(2500)
        return
    try:
        wahl = 0
        while True:
            installiert = {n: ha.kopf(n)["version"] for n in ha.apps()}
            lokal = [n for n in installiert if not ha.vertraut(n)]
            apps = sorted(kat.values(), key=lambda a: a["name"].lower())
            updates = [a for a in apps if a["id"] in installiert and a["id"] not in lokal
                       and ha.neuer(a["version"], installiert[a["id"]])]
            punkte, ziele = [], []
            if updates:
                punkte.append("Alle updaten (%d)" % len(updates))
                ziele.append(None)
            for a in apps:
                if a["id"] not in installiert:
                    marke = "+"
                elif a["id"] in lokal:
                    marke = "L"
                elif a in updates:
                    marke = "^"
                else:
                    marke = " "
                punkte.append(marke + " " + a["name"][:13])
                ziele.append(a)
            punkte.append("Zurueck")
            ziele.append("zurueck")
            w = ha.menue(oled, ein, "APP-STORE " + ha.kb(ha.frei()),
                         ["+neu ^Upd L lokal"], punkte, wahl)
            if w < 0 or ziele[w] == "zurueck":
                return
            wahl = w
            if ziele[w] is None:
                installieren(oled, updates, netz)
                continue
            a = ziele[w]
            iv = installiert.get(a["id"])
            if iv is None:
                tun = "Installieren"
            elif a["id"] in lokal:
                tun = "Mit Store ersetz"
            elif ha.neuer(a["version"], iv):
                tun = "Update v" + iv + ">" + a["version"]
            else:
                tun = "Neu laden"
            info = a.get("info", "")
            d = ha.menue(oled, ein, a["name"],
                         ["v%s  %s" % (a["version"], ha.kb(a["groesse"])), info[:16], info[16:32]],
                         [tun, "Zurueck"])
            if d == 0:
                installieren(oled, [a], netz)
    finally:
        netz.trennen()


# =====================================================================
#  AUFTRAEGE (Fern-Installation aus dem Web-Portal)
# =====================================================================
def auftraege_offen():
    a = hub_online.board_status().get("auftraege") or {}
    return bool(a.get("install") or a.get("deinstall"))


def auftraege_ausfuehren(oled, netz=None):
    """Holt die aktuellen Auftraege, installiert/entfernt und meldet zurueck."""
    eigen = netz is None
    try:
        if eigen:
            ha.meldung(oled, "Online", "abgleichen ...")
            netz = hub_online.Netz(hub_online.konfig_lesen())
            netz.verbinden()
        antwort = netz.melden() or {}
        auf = antwort.get("auftraege") or {}
        erledigt = {"install": [], "deinstall": []}
        for name in auf.get("deinstall", []):
            if name in ha.apps():
                ha.meldung(oled, "Entferne", ha.anzeigename(name)[:16])
                ha.app_loeschen(name)
            erledigt["deinstall"].append(name)
        if auf.get("install"):
            kat = netz.katalog()
            apps = [kat[n] for n in auf["install"] if n in kat]
            if apps and installieren(oled, apps, netz):
                erledigt["install"] += [a["id"] for a in apps]
            erledigt["install"] += [n for n in auf["install"] if n not in kat]
        netz.melden(erledigt)
        return True
    except Exception as e:
        ha.meldung(oled, "Auftraege", str(e)[:16], str(e)[16:32])
        time.sleep_ms(2000)
        return False
    finally:
        if eigen and netz is not None:
            netz.trennen()


def hochladen(oled, name, ziel):
    k = hub_online.konfig_lesen()
    ha.meldung(oled, "Lade hoch ...")
    netz = hub_online.Netz(k)
    try:
        netz.verbinden()
        r = netz.hochladen(name, ziel)
        if ziel == "privat":
            # liegt jetzt im Konto -> gleiche Pruefsumme = vertrauenswuerdig
            ha.installiert_merken(name, ha.pruefsumme(ha.datei(name)))
            ha.meldung(oled, "Im Konto!", "v" + str(r.get("version", "")), "Hub-Dienste an")
        else:
            ha.meldung(oled, "Eingereicht!", "wartet auf", "Freigabe")
    except Exception as e:
        ha.meldung(oled, "Fehler", str(e)[:16], str(e)[16:32])
    finally:
        netz.trennen()
    time.sleep_ms(2000)


# =====================================================================
#  BOARD-INFO
# =====================================================================
def koppeln(oled, ein):
    """Zeigt den Code, den man im Web-Portal eingibt."""
    ha.meldung(oled, "Koppeln", "verbinde ...")
    netz = hub_online.Netz(hub_online.konfig_lesen())
    try:
        netz.verbinden()
        netz.melden()
        start = time.ticks_ms()
        naechst = 0
        code = None
        ein.warte_los()
        while time.ticks_diff(time.ticks_ms(), start) < 600000:
            if time.ticks_diff(time.ticks_ms(), naechst) >= 0:
                naechst = time.ticks_add(time.ticks_ms(), 3000)
                k = netz.kopplung()
                if k.get("code"):
                    code = k["code"]
                    ha.kopfzeile(oled, "KOPPELN")
                    oled.text("Im Portal fuer", 8, 14, 1)
                    kt = str(k.get("konto", ""))[:16]
                    oled.text(kt, 64 - 4 * len(kt), 24, 1)
                    z = " ".join(code)
                    oled.fill_rect(10, 35, 108, 13, 1)
                    oled.text(z, 64 - 4 * len(z), 38, 0)
                    oled.text("S4 = Abbrechen", 8, 56, 1)
                    oled.show()
                elif k.get("gekoppelt"):
                    netz.melden()
                    ha.meldung(oled, "Gekoppelt mit" if code else "Schon gekoppelt", str(k["gekoppelt"])[:16])
                    time.sleep_ms(2500)
                    return
                elif code:
                    ha.meldung(oled, "Code abgelaufen", "im Portal neu", "anfordern")
                    time.sleep_ms(2500)
                    return
                else:
                    ha.meldung(oled, "Erst im Portal", "Code anfordern", "S4 = Abbrechen")
            if ein.lesen() == "zurueck":
                return
            time.sleep_ms(30)
    except Exception as e:
        ha.meldung(oled, "Fehler", str(e)[:16], str(e)[16:32])
        time.sleep_ms(2500)
    finally:
        netz.trennen()


def info(oled, ein):
    k = hub_online.konfig_lesen()
    status = ""
    while True:
        gc.collect()
        konto = hub_online.board_status().get("konto")
        zeilen = ["ID " + hub_online.board_id(),
                  "Flash " + ha.kb(ha.frei()) + " RAM " + ha.kb(gc.mem_free()),
                  status or (("Konto: " + konto) if konto else ("Online: an" if k else "Online: aus"))]
        punkte = (["Jetzt abgleichen", "Koppeln", "Verbindung testen"] if k else []) + ["Zurueck"]
        w = ha.menue(oled, ein, "BOARD #%04d" % hub_online.board_nr(), zeilen, punkte)
        if w < 0 or punkte[w] == "Zurueck":
            return
        status = ""
        if punkte[w] == "Koppeln":
            koppeln(oled, ein)
        elif punkte[w] == "Jetzt abgleichen":
            status = "Abgleich OK" if auftraege_ausfuehren(oled) else "Abgleich Fehler"
        else:
            ha.meldung(oled, "Verbinde ...")
            ok, text = hub_online.verbindung_testen()
            status = ("OK " if ok else "") + text

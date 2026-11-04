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


def wolke(oled, x, y, c, voll=True):
    """Volle Wolke: zuletzt wirklich online. Leere Wolke: WLAN eingetragen,
    aber noch nicht geprueft oder zuletzt keine Verbindung."""
    oled.fill_rect(x + 3, y, 4, 2, c)
    oled.fill_rect(x + 1, y + 2, 9, 3, c)
    oled.fill_rect(x, y + 4, 11, 3, c)
    if not voll:
        oled.fill_rect(x + 4, y + 1, 2, 1, 1 - c)
        oled.fill_rect(x + 2, y + 3, 7, 1, 1 - c)
        oled.fill_rect(x + 1, y + 4, 9, 2, 1 - c)


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

    eintraege, koepfe, updates = laden()
    zuletzt = lies(ZULETZT_DATEI)
    wahl = eintraege.index(zuletzt) if zuletzt in eintraege else 0
    oben = 0
    frei = ha.frei()

    def zeichnen():
        ha.kopfzeile(oled, "ESP-HUB", ha.kb(frei) if frei else "")
        if online:
            wolke(oled, 62, 2, 0, hub_online.verbindung() == "online")
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
                text = "i Board info"
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
            oled.text("S5 = Open", 16, 56, 1)
        else:
            v = koepfe[e]["version"] or "?"
            links = "v" + v + (">" + updates[e]["version"] if e in updates else "")
            oled.text(links[:8], 0, 56, 1)
            oled.text("S4 Menu", 64, 56, 1)
        oled.show()
        for i, p in enumerate(LED_PINS):
            Pin(p).value(1 if i == wahl % 8 else 0)

    zeichnen()
    # Only a working local gallery confirms a new firmware, never an HTTP reply.
    import sys
    confirm = sys.modules.get("_hub_boot", {}).get("confirm")
    if confirm:
        confirm()
    ein.warte_los()       # ein noch gehaltenes S4+S5 loest nichts aus
    firmware_check = time.ticks_ms()
    aktiv = firmware_check
    erster_abgleich = True
    while True:
        # Local navigation and game starts always take priority. Automatic online
        # work only runs after 30 s without input, then at most every five minutes.
        # The first check comes after 5 s so the cloud icon soon shows the real state.
        if online and time.ticks_diff(time.ticks_ms(), aktiv) >= (5000 if erster_abgleich else 30000) and (erster_abgleich or time.ticks_diff(time.ticks_ms(), firmware_check) >= 300000):
            erster_abgleich = False
            auftraege_ausfuehren(oled, automatisch=True)
            firmware_check = time.ticks_ms()
            eintraege, koepfe, updates = laden()
            wahl = min(wahl, len(eintraege) - 1)
            oben = min(oben, wahl)
            frei = ha.frei()
            zeichnen()
        e = ein.lesen()
        if e:
            aktiv = time.ticks_ms()
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
            online = hub_online.konfig_lesen() is not None
            zeichnen()
        time.sleep_ms(15)


def starten(oled, name, k, ton, start_datei, neustart):
    problem = ha.kompatibilitaet(k)
    if problem:
        ha.fehler_dialog(oled, ha.Eingabe(), "Not compatible", problem)
        return
    ha.kopfzeile(oled, "STARTING")
    t = k["name"][:16]
    oled.text(t, 64 - 4 * len(t), 14, 1)
    if k["version"]:
        v = "v" + k["version"]
        oled.text(v, 64 - 4 * len(v), 24, 1)
    oled.hline(0, 34, 128, 1)
    oled.text("Menu: S4+S16", 12, 38, 1)
    oled.text("Exit: S4+S5", 12, 48, 1)
    oled.text("(hold)", 32, 57, 1)
    oled.show()
    ton.piep(1300, 40)
    ton.piep(2000, 60)
    with open(start_datei, "w") as f:
        f.write(name)
    with open(ZULETZT_DATEI, "w") as f:
        f.write(name)
    time.sleep_ms(150)
    neustart()


def app_menue(oled, ein, ton, name, k, update, start_datei, neustart):
    gekoppelt = hub_online.konfig_lesen() is not None and hub_online.board_status().get("konto")
    while True:
        punkte = ["Start"]
        if update:
            punkte.append("Update to " + update["version"])
        if k.get("lokal") and gekoppelt:
            punkte += ["Private upload", "Submit review"]
        punkte += ["Delete save", "Uninstall", "Back"]
        w = ha.menue(oled, ein, k["name"], ha.info_zeilen(name, k, lokal=k.get("lokal")), punkte)
        p = punkte[w] if w >= 0 else "Back"
        if p in ("Private upload", "Submit review"):
            ziel = "privat" if p == "Private upload" else "pruefung"
            if ha.frage(oled, ein, "UPLOAD", k["name"],
                        "to your account?" if ziel == "privat" else "for review?"):
                hochladen(oled, name, ziel)
            continue
        if p == "Start":
            starten(oled, name, k, ton, start_datei, neustart)
        elif p.startswith("Update"):
            if installieren(oled, [update]):
                return
        elif p == "Delete save":
            if ha.frage(oled, ein, "SAVE DATA", "Delete your", "saved progress?"):
                ha.daten_loeschen(name)
                ha.meldung(oled, "Save data", "deleted")
                time.sleep_ms(900)
        elif p == "Uninstall":
            if ha.frage(oled, ein, "UNINSTALL", k["name"], "remove app?"):
                ha.app_loeschen(name)
                ha.meldung(oled, k["name"], "removed")
                time.sleep_ms(900)
                return
        else:
            return


# =====================================================================
#  APP-STORE
# =====================================================================
def installieren(oled, apps, netz=None, vor_commit=None, still=False):
    """Apps aus dem Store laden. Gibt True zurueck, wenn alles geklappt hat."""
    eigenes_netz = netz is None
    try:
        if eigenes_netz:
            ha.meldung(oled, "App-Store", "connecting ...")
            netz = hub_online.Netz(hub_online.konfig_lesen(), 300000)
            netz.verbinden()
        netz.bis = time.ticks_add(time.ticks_ms(), 300000)
        for a in apps:
            problem = ha.kompatibilitaet(a)
            if problem:
                raise ValueError(problem)
            if a.get("dateien"):
                paket_installieren(netz, a, oled, vor_commit)
                continue
            # Platz fuer die neue Datei (+ Reserve) muss da sein, die alte
            # Version wird erst nach erfolgreichem Download ersetzt
            if ha.frei() < a["groesse"] + 8192:
                raise OSError("Not enough flash: " + ha.kb(a["groesse"]) + " required")
            ha.meldung(oled, "Downloading", a["name"][:16], "v" + a["version"])
            ha.paketpfad(a["id"])  # validate the ID for legacy entries too
            ziel = "/gal_" + a["id"] + ".py"
            netz.app_laden(a, ziel + ".neu", lambda x: ha.balken(oled, 54, x))
            import os
            if vor_commit:
                vor_commit()
            os.rename(ziel + ".neu", ziel)
            ha.loeschen(ha.paketpfad(a["id"]))
            ha.installiert_merken(a["id"], a["sha256"])     # vertrauenswuerdig
        ha.meldung(oled, "Done!", "%d App%s" % (len(apps), "" if len(apps) == 1 else "s"))
        time.sleep_ms(900)
        return True
    except Exception as e:
        hub_online.diagnose(e)
        if still:
            raise
        ha.fehler_dialog(oled, ha.Eingabe(), "Installation", e)
        return False
    finally:
        if eigenes_netz and netz is not None:
            netz.trennen()


def paket_installieren(netz, app, oled, vor_commit=None):
    import os
    import json
    name = app["id"]
    target = ha.paketpfad(name)
    stage = ha.PAKETE + "/.neu_" + name
    old = ha.PAKETE + "/.alt_" + name
    files = app["dateien"]
    if not 0 < len(files) <= 128 or len(app.get("paket", "")) != 64 or any(c not in "0123456789abcdef" for c in app["paket"]):
        raise ValueError("Invalid app manifest")
    seen = set()
    total = 0
    for d in files:
        p = d.get("name", "")
        if not p or p in seen or p == "manifest.json" or any(not part or part in (".", "..") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for c in part) for part in p.split("/")):
            raise ValueError("Invalid app file path")
        if not isinstance(d.get("groesse"), int) or not 0 <= d["groesse"] <= 512 * 1024:
            raise ValueError("Invalid app file size")
        seen.add(p)
        total += d["groesse"]
    if "main.py" not in seen or total > 512 * 1024:
        raise ValueError("Invalid app package")
    for d in app.get("geteilt", []):
        if d.get("name") not in ("ssd1306.py", "bmp280.py") or ha.pruefsumme("/" + d["name"]) != d["sha256"]:
            raise ValueError("Update Hub first: drivers")
    ha.loeschen(stage)
    if ha.frei() < total + 16384:
        raise OSError("Not enough flash")
    try:
        os.mkdir(ha.PAKETE)
    except OSError:
        pass
    os.mkdir(stage)
    for i, d in enumerate(files):
        parts = d["name"].split("/")
        parent = stage
        for part in parts[:-1]:
            parent += "/" + part
            try:
                os.mkdir(parent)
            except OSError:
                pass
        ha.meldung(oled, "Installing app", d["name"][:16])
        netz.datei_laden("apps/" + name, stage + "/" + d["name"], d,
                         lambda x: ha.balken(oled, 54, (i + x) / len(files)),
                         "&datei=" + d["name"] + "&paket=" + app["paket"])
    with open(stage + "/manifest.json", "w") as f:
        json.dump(app, f)
    if vor_commit:
        vor_commit()
    ha.loeschen(old)
    try:
        os.stat(target)
    except OSError:
        pass
    else:
        os.rename(target, old)
    os.rename(stage, target)
    ha.loeschen(old)
    ha.loeschen("/gal_" + name + ".py")
    ha.installiert_merken(name, app["sha256"])


def store(oled, ein, ton):
    k = hub_online.konfig_lesen()
    if k is None:
        return
    ha.meldung(oled, "App-Store", "connecting ...")
    netz = hub_online.Netz(k)
    try:
        netz.verbinden()
        netz.melden()
        kat = netz.katalog()
    except Exception as e:
        netz.trennen()
        ha.fehler_dialog(oled, ein, "Store offline", e)
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
                punkte.append("Update all (%d)" % len(updates))
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
            punkte.append("Back")
            ziele.append("zurueck")
            w = ha.menue(oled, ein, "APP-STORE " + ha.kb(ha.frei()),
                         ["+new ^Upd L local"], punkte, wahl)
            if w < 0 or ziele[w] == "zurueck":
                return
            wahl = w
            if ziele[w] is None:
                installieren(oled, updates, netz)
                continue
            a = ziele[w]
            problem = ha.kompatibilitaet(a)
            if problem:
                ha.fehler_dialog(oled, ein, "Requirements", problem)
                continue
            iv = installiert.get(a["id"])
            if iv is None:
                tun = "Install"
            elif a["id"] in lokal:
                tun = "Replace with store"
            elif ha.neuer(a["version"], iv):
                tun = "Update v" + iv + ">" + a["version"]
            else:
                tun = "Reload"
            info = a.get("info", "")
            d = ha.menue(oled, ein, a["name"],
                         ["v%s  %s" % (a["version"], ha.kb(a["groesse"])), info[:16], info[16:32]],
                         [tun, "Back"])
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


def auftraege_ausfuehren(oled, netz=None, automatisch=False):
    """Holt die aktuellen Auftraege, installiert/entfernt und meldet zurueck."""
    eigen = netz is None
    try:
        if eigen:
            ha.meldung(oled, "Online", "syncing ...")
            netz = hub_online.Netz(hub_online.konfig_lesen(), 12000 if automatisch else 300000)
            netz.verbinden()
        antwort = netz.melden() or {}
        auf = antwort.get("auftraege") or {}
        kat = netz.katalog()
        import hub_update
        hub_update.pruefen(netz, automatisch)
        netz.bis = time.ticks_add(time.ticks_ms(), 12000 if automatisch else 300000)
        erledigt = {"install": [], "deinstall": []}
        for name in auf.get("deinstall", []):
            try:
                netz.auftrag_status("deinstall", name, "installation")
                if name in ha.apps():
                    ha.meldung(oled, "Removing", ha.anzeigename(name)[:16])
                    ha.app_loeschen(name)
                netz.auftrag_status("deinstall", name, "fertig")
                erledigt["deinstall"].append(name)
            except Exception as error:
                reason = hub_online.diagnose(error).get("fehler", "Uninstall failed")
                try:
                    netz.auftrag_status("deinstall", name, "fehler", reason)
                except Exception:
                    pass
        if auf.get("install"):
            for name in auf["install"]:
                try:
                    if name not in kat:
                        raise ValueError("App no longer in store")
                    job = antwort.get("jobs", {}).get("install", {}).get(name)
                    if isinstance(job, dict) and job.get("version") != kat[name].get("version", ""):
                        raise ValueError("App changed: create a new request")
                    if isinstance(job, dict) and job.get("paket") and job["paket"] != (kat[name].get("paket") or kat[name]["sha256"]):
                        raise ValueError("Package changed: create a new request")
                    netz.auftrag_status("install", name, "download")
                    netz.bis = time.ticks_add(time.ticks_ms(), 300000)
                    installieren(oled, [kat[name]], netz, lambda: netz.auftrag_status("install", name, "installation"), True)
                    netz.auftrag_status("install", name, "fertig")
                    erledigt["install"].append(name)
                except Exception as error:
                    reason = hub_online.diagnose(error).get("fehler", "Installation failed")
                    try:
                        netz.auftrag_status("install", name, "fehler", reason)
                    except Exception:
                        pass
        # Share one WLAN session across saves, catalog and firmware check.
        names = [name for name in ha.apps() if ha.vertraut(name)]
        import os
        for filename in os.listdir(hub_online.CACHE):
            name = filename[:-5]
            if filename.endswith(".json") and not name.startswith("_") and ha.gueltige_id(name) and name not in names and name not in ha.apps():
                if hub_online.Speicher(name).offen():
                    names.append(name)
        cursor_file = hub_online.CACHE + "/_sync_cursor.json"
        cursor = hub_online._json_lesen(cursor_file, {}).get("index", 0)
        if names:
            cursor %= len(names)
            for i in range(min(1, len(names)) if automatisch else len(names)):
                index = (cursor + i) % len(names)
                netz.rest()
                if not hub_online.Speicher(names[index]).abgleichen(False, netz):
                    raise OSError("Save sync failed")
                hub_online._json_schreiben(cursor_file, {"index": (index + 1) % len(names)})
        netz.melden(erledigt)
        hub_online.diagnose(erfolg=True)
        return True
    except Exception as e:
        hub_online.diagnose(e)
        if not automatisch:
            ha.fehler_dialog(oled, ha.Eingabe(), "Sync", e)
        return False
    finally:
        if eigen and netz is not None:
            netz.trennen()


def hochladen(oled, name, ziel):
    k = hub_online.konfig_lesen()
    ha.meldung(oled, "Uploading ...")
    netz = hub_online.Netz(k)
    try:
        netz.verbinden()
        r = netz.hochladen(name, ziel)
        if ziel == "privat":
            # liegt jetzt im Konto -> gleiche Pruefsumme = vertrauenswuerdig
            ha.installiert_merken(name, ha.pruefsumme(ha.datei(name)))
            ha.meldung(oled, "In your account!", "v" + str(r.get("version", "")), "Hub services on")
        else:
            ha.meldung(oled, "Submitted!", "waiting for", "approval")
    except Exception as e:
        ha.fehler_dialog(oled, ha.Eingabe(), "Upload", e)
        return
    finally:
        netz.trennen()
    time.sleep_ms(2000)


# =====================================================================
#  BOARD-INFO
# =====================================================================
def koppeln(oled, ein):
    """Zeigt den Code, den man im Web-Portal eingibt."""
    ha.meldung(oled, "Pair", "connecting ...")
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
                netz.bis = time.ticks_add(time.ticks_ms(), 15000)
                k = netz.kopplung()
                if k.get("code"):
                    code = k["code"]
                    ha.kopfzeile(oled, "PAIR BOARD")
                    oled.text("In portal for", 8, 14, 1)
                    kt = str(k.get("konto", ""))[:16]
                    oled.text(kt, 64 - 4 * len(kt), 24, 1)
                    z = " ".join(code)
                    oled.fill_rect(10, 35, 108, 13, 1)
                    oled.text(z, 64 - 4 * len(z), 38, 0)
                    oled.text("S4 = Cancel", 8, 56, 1)
                    oled.show()
                elif k.get("gekoppelt"):
                    netz.melden()
                    ha.meldung(oled, "Paired with" if code else "Already paired", str(k["gekoppelt"])[:16])
                    time.sleep_ms(2500)
                    return
                elif code:
                    ha.meldung(oled, "Code expired", "Request again", "in the portal")
                    time.sleep_ms(2500)
                    return
                else:
                    ha.meldung(oled, "Request a code", "in the portal", "S4 = Cancel")
            if ein.lesen() == "zurueck":
                return
            time.sleep_ms(30)
    except Exception as e:
        ha.fehler_dialog(oled, ein, "Pair", e)
    finally:
        netz.trennen()


def funk_neustart(oled, merker):
    """Funk-Modi laufen nach einem Neustart, bevor der Hub Speicher belegt
    (siehe FUNK_MODI in main.py)."""
    import machine
    with open(merker, "w") as f:
        f.write("1")
    ha.meldung(oled, "Restarting ...")
    time.sleep_ms(300)
    machine.reset()


def info(oled, ein):
    k = hub_online.konfig_lesen()
    status = ""
    while True:
        gc.collect()
        konto = hub_online.board_status().get("konto")
        zeilen = ["ID " + hub_online.board_id(),
                  "Flash " + ha.kb(ha.frei()) + " RAM " + ha.kb(gc.mem_free()),
                  status or (("Account: " + konto) if konto else ("Online: off" if not k else
                  {"online": "Online: OK", "offline": "Online: failed"}.get(hub_online.verbindung(), "Online: unchecked")
                  + (" (rep)" if k.get("modus") == "repeater" else "")))]
        punkte = (["Hub v" + ha.HUB_VERSION, "Sync now", "Pair", "Test connection"] if k else ["Hub v" + ha.HUB_VERSION]) + ["Set up Wi-Fi"]
        if k and k.get("modus") != "repeater":
            punkte.append("Be a repeater")
        punkte += ["Diagnostics", "Back"]
        w = ha.menue(oled, ein, "BOARD #%04d" % hub_online.board_nr(), zeilen, punkte)
        if w < 0 or punkte[w] == "Back":
            return
        status = ""
        if punkte[w].startswith("Hub v"):
            import hub_update
            hub_update.pruefen()
        elif punkte[w] == "Pair":
            koppeln(oled, ein)
        elif punkte[w] == "Sync now":
            status = "Sync OK" if auftraege_ausfuehren(oled) else "Sync failed"
        elif punkte[w] == "Set up Wi-Fi":
            wahl = ha.menue(oled, ein, "SET UP WI-FI", ["Own network or", "another board"], ["Own Wi-Fi", "Via repeater", "Back"])
            if wahl in (0, 1):
                funk_neustart(oled, "/hubwifi.txt" if wahl == 0 else "/hubsuche.txt")
        elif punkte[w] == "Be a repeater":
            funk_neustart(oled, "/hubrepeater.txt")
        elif punkte[w] == "Diagnostics":
            d = hub_online._json_lesen(hub_online.DIAGNOSE, {})
            age = max(0, time.ticks_diff(time.ticks_ms(), hub_online.LETZTER_SYNC) // 1000) if hub_online.LETZTER_SYNC is not None else None
            z = ["Sync %ds ago" % age if age is not None else ("Synced last boot" if "sync" in d else "Never synced"), "Pending: %d apps" % hub_online.offene_daten(), "Flash " + ha.kb(ha.frei()), "RAM " + ha.kb(gc.mem_free())]
            error = d.get("fehler", "No errors")
            z += [error[i:i + 16] for i in range(0, len(error), 16)]
            while ha.menue(oled, ein, "DIAGNOSTICS", [], z + ["Back"]) not in (-1, len(z)):
                pass
        else:
            ha.meldung(oled, "Connecting ...")
            ok, text = hub_online.verbindung_testen()
            status = ("OK " if ok else "") + text
            if not ok:
                ha.fehler_dialog(oled, ein, "Connection", text)

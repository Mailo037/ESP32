# OTA updates of the Hub Python firmware (not the MicroPython runtime).
import os
import json
import time

FILES = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")
UPDATE = "/hubupdate"


def manifest_pruefen(meta):
    files = meta.get("dateien", [])
    if len(files) != len(FILES) or set(d.get("name") for d in files) != set(FILES):
        raise ValueError("Firmware-Dateiliste ungueltig")
    if len(meta.get("id", "")) != 64 or any(c not in "0123456789abcdef" for c in meta["id"]):
        raise ValueError("Firmware-ID ungueltig")
    for d in files:
        if not isinstance(d.get("groesse"), int) or not 0 < d["groesse"] <= 256 * 1024 or len(d.get("sha256", "")) != 64:
            raise ValueError("Firmware-Datei ungueltig")
    if sum(d["groesse"] for d in files) > 512 * 1024:
        raise ValueError("Firmware zu gross")


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
    need = sum(d["groesse"] for d in meta["dateien"]) + max(d["groesse"] for d in meta["dateien"]) + 16384
    ha.loeschen(UPDATE)
    if ha.frei() < need:
        raise OSError("Zu wenig Flash")
    os.mkdir(UPDATE)
    for i, d in enumerate(meta["dateien"]):
        ha.meldung(oled, "Hub-Update", d["name"][:16])
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
            raise ValueError("Firmware-Version stimmt nicht")
    with open(UPDATE + "/pending.neu", "w") as f:
        json.dump(meta, f)
    getattr(os, "sync", lambda: None)()
    os.rename(UPDATE + "/pending.neu", UPDATE + "/pending.json")
    getattr(os, "sync", lambda: None)()
    ha.meldung(oled, "Hub-Update", "Neustart ...")
    machine.reset()


def pruefen():
    """Check before entering a game or gallery. Offline always remains usable."""
    import hub_apps as ha
    import hub_online
    k = hub_online.konfig_lesen()
    if not k:
        return
    netz = hub_online.Netz(k)
    try:
        netz.verbinden()
        netz.melden()
        meta = netz.firmware()
        if not meta or not ha.neuer(meta.get("version"), ha.HUB_VERSION):
            return
        manifest_pruefen(meta)
        oled = ha.oled_neu()
        ein = ha.Eingabe()
        while True:
            choice = ha.menue(oled, ein, "HUB-UPDATE", ["v" + ha.HUB_VERSION, "> v" + meta["version"]], ["Installieren", "Spaeter"])
            if choice != 0:
                return
            try:
                installieren(netz, meta, oled)
                return
            except Exception as error:
                print("Hub-Update:", error)
                ha.meldung(oled, "Update-Fehler", "Erneut / Spaeter")
                time.sleep_ms(1500)
    except Exception as error:
        print("Hub-Update offline:", error)
    finally:
        netz.trennen()

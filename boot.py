# Stable recovery bootstrap. Installed by mpremote; never replaced by OTA.
# A pending, completely downloaded firmware is applied before importing the Hub.
import os
import sys
import json

UPDATE = "/hubupdate"
PENDING = UPDATE + "/pending.json"
FILES = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")


def sha256(path):
    import hashlib
    import binascii
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            part = f.read(1024)
            if not part:
                break
            h.update(part)
    return binascii.hexlify(h.digest()).decode()


def recover():
    try:
        os.stat(PENDING)
    except OSError:
        return
    with open(PENDING) as f:
        meta = json.load(f)
    files = meta.get("dateien", [])
    if len(files) != len(FILES) or set(d.get("name") for d in files) != set(FILES):
        raise ValueError("Firmware-Manifest ungueltig")
    # Check the complete staged set before changing any live file.
    for d in files:
        src = UPDATE + "/" + d["name"]
        if os.stat(src)[6] != d["groesse"] or sha256(src) != d["sha256"]:
            raise ValueError("Firmware-Pruefsumme: " + d["name"])
    for d in files:
        target = "/" + d["name"]
        try:
            if sha256(target) == d["sha256"]:
                continue
        except OSError:
            pass
        # Keep staged sources until ALL files are committed. Reboot resumes this loop.
        with open(UPDATE + "/" + d["name"], "rb") as src, open(target + ".hubnew", "wb") as dst:
            while True:
                part = src.read(1024)
                if not part:
                    break
                dst.write(part)
        if sha256(target + ".hubnew") != d["sha256"]:
            raise ValueError("Firmware-Schreibfehler")
        getattr(os, "sync", lambda: None)()
        os.rename(target + ".hubnew", target)
    getattr(os, "sync", lambda: None)()
    os.remove(PENDING)
    getattr(os, "sync", lambda: None)()
    # Cleanup is optional; a failed cleanup must not block a completed update.
    for d in files:
        try:
            os.remove(UPDATE + "/" + d["name"])
        except OSError:
            pass


try:
    recover()
except Exception as error:
    sys._hub_update_fehler = True
    print("Hub-Update unterbrochen. Neustarten zum Fortsetzen:", error)

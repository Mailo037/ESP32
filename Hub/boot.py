# Stable recovery bootstrap. Installed by mpremote; never replaced by OTA.
# A pending, completely downloaded firmware is applied before importing the Hub.
import os
import sys
import json

UPDATE = "/hubupdate"
PENDING = UPDATE + "/pending.json"
FILES = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")
BACKUP = "/hubbackup"
TRIAL = BACKUP + "/trial.json"
STATE = {}
# Native MicroPython modules may have fixed globals. sys.modules is mutable on
# both ESP32 and WASM; use it as the private handoff instead of sys attributes.
sys.modules["_hub_boot"] = STATE


def read(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError:
        return default


def write(path, value):
    with open(path + ".neu", "w") as f:
        json.dump(value, f)
    getattr(os, "sync", lambda: None)()
    os.rename(path + ".neu", path)
    getattr(os, "sync", lambda: None)()


def copy(source, target):
    with open(source, "rb") as src, open(target + ".hubnew", "wb") as dst:
        while True:
            part = src.read(1024)
            if not part:
                break
            dst.write(part)
    if sha256(source) != sha256(target + ".hubnew"):
        raise ValueError("Firmware write failed")
    getattr(os, "sync", lambda: None)()
    os.rename(target + ".hubnew", target)


def backup():
    # Snapshot must be complete before the first live file is changed.
    if read(BACKUP + "/manifest.json") is not None:
        return
    try:
        os.mkdir(BACKUP)
    except OSError:
        pass
    files = []
    for name in FILES:
        try:
            size = os.stat("/" + name)[6]
        except OSError:
            continue
        copy("/" + name, BACKUP + "/" + name)
        files.append({"name": name, "groesse": size, "sha256": sha256("/" + name)})
    write(BACKUP + "/manifest.json", files)


def rollback(state):
    files = read(BACKUP + "/manifest.json")
    if not files:
        raise ValueError("No recovery snapshot available")
    for d in files:
        if d["name"] not in FILES or sha256(BACKUP + "/" + d["name"]) != d["sha256"]:
            raise ValueError("Recovery snapshot damaged")
    write(TRIAL, dict(state, modus="restore"))
    for d in files:
        copy(BACKUP + "/" + d["name"], "/" + d["name"])
    previous = set(d["name"] for d in files)
    for name in FILES:
        if name not in previous:
            try:
                os.remove("/" + name)
            except OSError:
                pass
    write(BACKUP + "/fehlgeschlagen.json", {"version": state.get("version", "")})
    # Remove a pending commit too; otherwise the rejected version would return.
    try:
        os.remove(PENDING)
    except OSError:
        pass
    write(TRIAL, dict(state, modus="fertig"))
    retire()


def retire():
    try:
        os.remove(BACKUP + "/manifest.json")
    except OSError:
        pass
    for name in FILES:
        try:
            os.remove(BACKUP + "/" + name)
        except OSError:
            pass
    try:
        os.remove(TRIAL)
    except OSError:
        pass
    getattr(os, "sync", lambda: None)()


def bestaetigen():
    if read(TRIAL) is not None:
        write(TRIAL, {"modus": "fertig"})
        retire()
        import machine
        machine.reset()  # clears the trial watchdog on the next boot


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
    failed = read(BACKUP + "/fehlgeschlagen.json", {})
    if failed.get("version") and failed["version"] == meta.get("version"):
        # Older restored updaters do not know the failed-release marker.
        # Reject their repeat attempt before touching working firmware.
        os.remove(PENDING)
        getattr(os, "sync", lambda: None)()
        return
    files = meta.get("dateien", [])
    if len(files) != len(FILES) or set(d.get("name") for d in files) != set(FILES):
        raise ValueError("Invalid firmware manifest")
    # Check the complete staged set before changing any live file.
    for d in files:
        src = UPDATE + "/" + d["name"]
        if os.stat(src)[6] != d["groesse"] or sha256(src) != d["sha256"]:
            raise ValueError("Firmware checksum: " + d["name"])
    backup()
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
            raise ValueError("Firmware write failed")
        getattr(os, "sync", lambda: None)()
        os.rename(target + ".hubnew", target)
    getattr(os, "sync", lambda: None)()
    if read(TRIAL) is None:
        write(TRIAL, {"version": meta.get("version", ""), "versuche": 0})
    os.remove(PENDING)
    getattr(os, "sync", lambda: None)()
    # Cleanup is optional; a failed cleanup must not block a completed update.
    for d in files:
        try:
            os.remove(UPDATE + "/" + d["name"])
        except OSError:
            pass


try:
    state = read(TRIAL)
    if state and state.get("modus") == "fertig":
        retire()
        state = None
    if state and (state.get("modus") == "restore" or state.get("versuche", 0) >= 2):
        rollback(state)
    else:
        recover()
        state = read(TRIAL)
        if state:
            STATE["trial"] = True
            state["versuche"] = state.get("versuche", 0) + 1
            write(TRIAL, state)
            import machine
            if hasattr(machine, "WDT"):
                STATE["wdt"] = machine.WDT(timeout=15000)
    STATE["confirm"] = bestaetigen
except Exception as error:
    STATE["error"] = True
    print("Hub update interrupted. Restart to resume:", error)

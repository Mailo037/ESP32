# Kopiert die ESP-Hub-Firmware und explizit angegebene Spiele auf ein espBoard.
#
#   pip install mpremote
#   python installieren.py              (Port automatisch suchen)
#   python installieren.py COM3         (Windows)
#   python installieren.py /dev/ttyUSB0 mein_spiel.py
#
# Aus jedem Ordner mit main.py wird gal_<Ordner>.py, z. B.
# ESP-Pong/main.py -> gal_ESP_Pong.py. Weitere .py-Dateien hinter dem Port
# kommen ebenfalls als gal_<Name>.py dazu. Liegt hub_online.json da
# (Vorlage: hub_online.beispiel.json), wird sie mitkopiert und der Hub
# speichert online. Thonny vorher schliessen.
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent
HUB = REPO
OHNE = {"Hub", "simulator", "docs"}


def gal_name(name):
    name = re.sub(r"[^A-Za-z0-9]", "_", name)
    return name if name.startswith("gal_") else "gal_" + name


def main():
    if importlib.util.find_spec("mpremote") is None:
        sys.exit("mpremote is missing. Install it with: python -m pip install mpremote")
    args = sys.argv[1:]
    port = args.pop(0) if args and not args[0].endswith(".py") else "auto"

    # Hub-Module vorkompiliert (.mpy, siehe mpy_bauen.py): sonst fehlt beim
    # Kompilieren auf dem Board der Speicher fuer den WLAN-Treiber
    kopien = [(HUB / n, n) for n in ("boot.py", "main.py", "hub_main.mpy", "hub_apps.mpy", "hub_galerie.mpy", "hub_online.mpy",
                                     "hub_update.mpy", "ssd1306.py", "bmp280.py", "hub_version.json")]
    for quelle, ziel in kopien:
        if not quelle.exists():
            sys.exit("%s fehlt - erst python mpy_bauen.py ausfuehren" % ziel)
    if (HUB / "hub_online.json").exists():          # Online-Speicher (nicht im Repo)
        kopien.append((HUB / "hub_online.json", "hub_online.json"))
    for ordner in sorted(REPO.iterdir()):
        if ordner.is_dir() and ordner.name not in OHNE and (ordner / "main.py").exists():
            kopien.append((ordner / "main.py", gal_name(ordner.name) + ".py"))
    # Spiele aus diesem Repo gelten als vertrauenswuerdig (Hub-Dienste,
    # Updates). Eigene Dateien hinter dem Port laufen als "lokal".
    vertraut = {ziel[4:-3]: hashlib.sha256(q.read_bytes()).hexdigest()
                for q, ziel in kopien if ziel.startswith("gal_")}
    for datei in args:
        p = pathlib.Path(datei)
        kopien.append((p, gal_name(p.stem) + ".py"))

    befehl = [sys.executable, "-m", "mpremote", "connect", port]
    for quelle, ziel in kopien:
        print("%-28s -> :%s" % (quelle.relative_to(REPO) if quelle.is_relative_to(REPO) else quelle, ziel))
        befehl += ["fs", "cp", str(quelle), ":" + ziel, "+"]
    # Liste der vertrauenswuerdigen Apps auf dem Board ergaenzen (nicht ersetzen)
    befehl += ["exec", "import json, os\n"
               "try:\n os.mkdir('/hubdaten')\nexcept OSError:\n pass\n"
               "try:\n d = json.load(open('/hubdaten/_installiert.json'))\nexcept Exception:\n d = {}\n"
               "d.update(%s)\n"
               "f = open('/hubdaten/_installiert.json', 'w'); json.dump(d, f); f.close()\n"
               "# Alte Hub-Module als Quelltext entfernen: .py hat beim Import Vorrang vor .mpy\n"
               "for p in ('/hub_apps.py', '/hub_galerie.py', '/hub_online.py', '/hub_update.py', '/hub_main.py'):\n"
               " try:\n  os.remove(p)\n except OSError:\n  pass\n"
               "# A complete USB install supersedes any interrupted OTA trial.\n"
               "for p in ('/hubupdate/pending.json', '/hubbackup/trial.json', '/hubbackup/manifest.json', '/hubbackup/fehlgeschlagen.json'):\n"
               " try:\n  os.remove(p)\n except OSError:\n  pass\n"
               "getattr(os, 'sync', lambda: None)()" % json.dumps(vertraut),
               "+", "reset"]
    try:
        subprocess.run(befehl, check=True)
    except FileNotFoundError:
        sys.exit("mpremote missing: pip install mpremote")
    except subprocess.CalledProcessError as e:
        sys.exit("mpremote failed with code %d (check port and close Thonny)" % e.returncode)
    print("Done - the board will start in the gallery.")


if __name__ == "__main__":
    main()

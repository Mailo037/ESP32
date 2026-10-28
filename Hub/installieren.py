# Kopiert den ESP-Hub und alle Spiele aus diesem Repo auf ein espBoard.
#
#   pip install mpremote
#   python Hub/installieren.py              (Port automatisch suchen)
#   python Hub/installieren.py COM3         (Windows)
#   python Hub/installieren.py /dev/ttyUSB0 mein_spiel.py
#
# Aus jedem Ordner mit main.py wird gal_<Ordner>.py, z. B.
# ESP-Pong/main.py -> gal_ESP_Pong.py. Weitere .py-Dateien hinter dem Port
# kommen ebenfalls als gal_<Name>.py dazu. Liegt Hub/hub_online.json da
# (Vorlage: hub_online.beispiel.json), wird sie mitkopiert und der Hub
# speichert online. Thonny vorher schliessen.
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
HUB = REPO / "Hub"
OHNE = {"Hub", "simulator", "docs"}


def gal_name(name):
    name = re.sub(r"[^A-Za-z0-9]", "_", name)
    return name if name.startswith("gal_") else "gal_" + name


def main():
    args = sys.argv[1:]
    port = args.pop(0) if args and not args[0].endswith(".py") else "auto"

    kopien = [(HUB / "main.py", "main.py"), (HUB / "ssd1306.py", "ssd1306.py"),
              (HUB / "hub_online.py", "hub_online.py")]
    if (HUB / "hub_online.json").exists():          # Online-Speicher (nicht im Repo)
        kopien.append((HUB / "hub_online.json", "hub_online.json"))
    for ordner in sorted(REPO.iterdir()):
        if ordner.is_dir() and ordner.name not in OHNE and (ordner / "main.py").exists():
            kopien.append((ordner / "main.py", gal_name(ordner.name) + ".py"))
    for datei in args:
        p = pathlib.Path(datei)
        kopien.append((p, gal_name(p.stem) + ".py"))

    befehl = ["mpremote", "connect", port]
    for quelle, ziel in kopien:
        print("%-28s -> :%s" % (quelle.relative_to(REPO) if quelle.is_relative_to(REPO) else quelle, ziel))
        befehl += ["fs", "cp", str(quelle), ":" + ziel, "+"]
    befehl += ["reset"]
    try:
        subprocess.run(befehl, check=True)
    except FileNotFoundError:
        sys.exit("mpremote fehlt: pip install mpremote")
    except subprocess.CalledProcessError as e:
        sys.exit("mpremote meldet Fehler %d (Port richtig? Thonny geschlossen?)" % e.returncode)
    print("Fertig - das Board startet mit der Galerie.")


if __name__ == "__main__":
    main()

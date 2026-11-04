"""Hub-Module zu .mpy vorkompilieren (MicroPython-Bytecode).

    pip install mpy-cross==1.29.0.post2     (muss zur MicroPython-Version passen)
    python mpy_bauen.py

Die .mpy-Dateien liegen neben dem Quelltext und werden mit eingecheckt:
install.py, installieren.py und release_erstellen.py nehmen sie von dort."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULE = ("hub_main", "hub_apps", "hub_galerie", "hub_online", "hub_update")


def main():
    for name in MODULE:
        subprocess.run([sys.executable, "-m", "mpy_cross", "-o", str(ROOT / (name + ".mpy")), str(ROOT / (name + ".py"))],
                       check=True, cwd=ROOT)
        print(name + ".mpy", (ROOT / (name + ".mpy")).stat().st_size)


if __name__ == "__main__":
    main()

"""Create the ZIP uploaded in Admin > Firmware. Does not publish anything.

Files come from the last commit, not the working copy: on Windows the working
copy may have CRLF line endings, and the checksums must match a USB install
from GitHub byte for byte."""
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
FILES = ("main.py", "hub_main.mpy", "hub_apps.mpy", "hub_galerie.mpy", "hub_online.mpy", "hub_update.mpy", "ssd1306.py", "bmp280.py", "hub_version.json")


def committed(name):
    return subprocess.check_output(["git", "show", "HEAD:Hub/" + name], cwd=ROOT)


def main():
    version = json.loads(committed("hub_version.json"))["version"]
    output = ROOT / "releases" / ("esp-hub-" + version + ".zip")
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.writestr(name, committed(name))
    print(output)


if __name__ == "__main__":
    main()

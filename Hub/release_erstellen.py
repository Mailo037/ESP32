"""Create the ZIP uploaded in Admin > Firmware. Does not publish anything."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
FILES = ("main.py", "hub_apps.py", "hub_galerie.py", "hub_online.py", "hub_update.py", "ssd1306.py", "bmp280.py", "hub_version.json")


def main():
    version = json.loads((ROOT / "hub_version.json").read_text())["version"]
    output = ROOT / "releases" / ("esp-hub-" + version + ".zip")
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
    print(output)


if __name__ == "__main__":
    main()

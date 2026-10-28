# espBoard-Simulator

Das espBoard im Browser – mit **echtem MicroPython** (WebAssembly). Die Seite
lädt die Programm-Ordner live aus GitHub (Branch `main`, sonst der
Standard-Branch) und führt `main.py` unverändert aus.

**Öffnen:** <https://mailo037.github.io/ESP32-Programme/>
(GitHub Pages muss dafür einmal eingeschaltet werden, siehe unten).

## Was geht

- Board nach dem echten Vorbild: 8 LEDs P7…P0, Potis RP3/RP0, Tasterkreuz
  S17/S4/S5/S16, Joystick mit Taster S2, RGB-LED P8, OLED, Summer
- Jedes Programm-Verzeichnis mit `main.py` erscheint automatisch in der Auswahl.
- **Hub** (voreingestellt): Der Simulator legt alle anderen Ordner als
  `gal_<Ordner>.py` dazu, wie der optionale Spiele-Import des Hub-Installers auf dem echten Board.
- Der Flash bleibt bei `machine.reset()` / `soft_reset()` erhalten, z. B. für
  Bestenlisten und den Spielwechsel im Hub. *Start* lädt alles frisch aus GitHub.
  Neue Programme einfach als Ordner ins Repo legen.
- **Zwei Boards** gleichzeitig – sie finden sich per ESP-NOW (für ESP-Pong).
- **Messprotokoll live:** Spannungen an MP4, MP0, MP3, MP6, MP7
- Konsole wie in Thonny: `print()`-Ausgaben und Fehlermeldungen mit Zeilennummer
- Option „Echtes I²C-Tempo“: Display-Übertragungen dauern so lange wie am ESP32,
  dann sieht man auch, was Teil-Updates bringen

Bedienung: Pfeiltasten = Joystick, Leertaste = Joystick-Taster, W/A/S/D =
S17/S4/S16/S5, Q/E und Z/C = Potis. Oder alles mit Maus und Finger.

## GitHub Pages einschalten (einmalig)

1. Im Repo auf **Settings → Pages**.
2. *Source:* **Deploy from a branch**, Branch **simulator**, Ordner **/ (root)** → *Save*.
3. Nach ca. einer Minute ist die Seite unter
   `https://mailo037.github.io/ESP32-Programme/` erreichbar.

Lokal geht es auch: im Repo-Ordner `python -m http.server` starten und
<http://localhost:8000/> öffnen. Direkt als Datei (Doppelklick) geht
es nicht, weil der Browser dann keine Worker und keinen gemeinsamen Speicher erlaubt.

## So funktioniert es

| Datei | Aufgabe |
|---|---|
| `index.html`, `app.js` | Board zeichnen, Eingaben, Programmliste aus GitHub, Worker starten |
| `worker.js` | Ein Board = ein Web Worker mit MicroPython. Endlosschleifen und `sleep_ms` blockieren dort nicht die Seite |
| `simcore.js` | Nachbau des SSD1306-Controllers (bekommt die echten I²C-Bytes) und ESP-NOW-Postfächer |
| `py/_sim_*.py` | Ersatz für `machine`, `time`, `network`, `espnow` – leiten alles an den Worker weiter |
| `py/_boot.py` | Setzt die Ersatz-Module ein und startet `main.py` als `__main__` |
| `coi-serviceworker.js` | Setzt auf GitHub Pages die Header für `SharedArrayBuffer` |
| `mp/` | MicroPython-WebAssembly 1.27.0 (MIT-Lizenz) |

Was **nicht** nachgebaut ist: echtes WLAN, Bluetooth, `machine.Timer`,
Interrupts und der BMP280 (der Sockel ist auf vielen Boards leer – die Programme
kommen damit klar). Die Rechengeschwindigkeit im Browser ist höher als auf dem
ESP32; das Display-Tempo wird mit „Echtes I²C-Tempo“ nachgebildet.

## Getrennter Simulator-Branch

Die Web-Dateien liegen in diesem Branch direkt im Stamm. GitHub Pages kann
den Branch `simulator` mit Ordner `/ (root)` verwenden, sobald er gepusht ist.
Die Programme werden weiterhin aus dem Online-Repository geladen; die
Umstellung der lokalen Verzeichnisstruktur aendert die Online-Quelle nicht.

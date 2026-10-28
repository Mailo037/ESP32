# 3D-Render v2.0 für das BZTG espBoard

MicroPython-Demo für ESP32 mit SSD1306-OLED (128×64).  
Zeigt sechs Drahtgitter-Formen, die sich mit dem Joystick drehen lassen:

- Würfel
- Dreieck
- Pyramide
- Oktaeder
- Tetraeder *(neu)*
- Ikosaeder *(neu, 12 Ecken, 30 Kanten)*

Mit dem **Joystick-Taster** klickst du dich durch die Formen; die LEDs oben
zeigen, welche Form gerade dran ist.

## Neu in v2.0

- Schnellerer OLED-Treiber (Adressbefehle in einer I²C-Übertragung) und
  Bildratenbegrenzung über `MAX_FPS` statt fester Pause – dadurch mehr FPS.
- Weniger Speicher-Neuanlagen pro Bild (Punkteliste wird wiederverwendet).
- Neue Formen Tetraeder und Ikosaeder, LED-Anzeige der Form.
- Neue Einstellungen `ACHSEN_TAUSCHEN`, `X_UMDREHEN`, `Y_UMDREHEN`, `I2C_FREQ`.

## Dateien in diesem Ordner

| Datei | Zweck |
|---|---|
| `main.py` | Das eigentliche Programm |
| `ssd1306.py` | OLED-Treiber (wird benötigt) |
| `vorschau.svg` | Vorschau am PC (nicht auf den ESP kopieren, zeigt v1) |
| `README.md` | Diese Anleitung |

## Auf den ESP kopieren

`main.py` und `ssd1306.py` müssen beide in den **Root-Ordner** des ESP, nicht in einen Unterordner.

**Mit Thonny:**

1. `main.py` öffnen.
2. Datei → Speichern unter → MicroPython-Gerät → Dateiname `main.py`.
3. `ssd1306.py` genauso auf das Gerät speichern.
4. Board neu starten (Stop/Restart oder Reset-Taste).

**Mit mpremote:**

```powershell
mpremote connect COM3 cp main.py :main.py
mpremote connect COM3 cp ssd1306.py :ssd1306.py
mpremote connect COM3 reset
```

## Bedienung

| Eingabe | Funktion |
|---|---|
| Joystick links/rechts | Drehen um die Y-Achse |
| Joystick oben/unten | Drehen um die X-Achse |
| Joystick-Taster | Nächste Form |
| S16 | Ansicht zurücksetzen |
| S17 | Auto-Drehung an/aus |
| S4 | Zoom kleiner |
| S5 | Zoom größer |

Beim Start den Joystick **loslassen**, damit die Mittelstellung kalibriert wird.

## Anpassen

In `main.py` oben einstellbar:

- `SCALE` – Größe der Formen
- `PERSP` – Perspektive (`0` = orthographisch)
- `DREH_TEMPO` – Drehgeschwindigkeit bei Vollausschlag
- `AUTO_TEMPO` – Geschwindigkeit der Auto-Drehung
- `TOTZONE` – Joystick-Totzone
- `MAX_FPS` – Obergrenze der Bildrate
- `I2C_FREQ` – OLED-Takt (viele Displays schaffen 800000–1000000)
- `ACHSEN_TAUSCHEN`, `X_UMDREHEN`, `Y_UMDREHEN` – Joystick anpassen

Neue Formen: In `SHAPES` einen Eintrag `("NAME", VERTICES, KANTEN)` ergänzen.  
Die Koordinaten liegen etwa im Bereich `-1 … +1`.

## Hinweise

- Die Tasten werden als **active-high** angenommen. Falls gedrückt `0` gelesen wird, in `main.py` `TASTEN_AKTIV_HIGH = False` setzen.
- Wenn die Joystick-Achsen vertauscht sind, `ACHSEN_TAUSCHEN = True` setzen. Ist eine Richtung falsch, `X_UMDREHEN` bzw. `Y_UMDREHEN` auf `True`.
- Das OLED hängt an I2C: SDA = GPIO 21, SCL = GPIO 22, Standardadresse `0x3C`.
- Ein BMP280 wird für diese Demo **nicht** benötigt.

Mehr zum Board: [`docs/espBoard.md`](../docs/espBoard.md)

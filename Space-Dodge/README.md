# Space Dodge v2.0 – Weltraum-Shooter für das espBoard

Weiche den fallenden Gegnern aus, schieß sie ab, setz Schild und Bombe ein
und trag dich in die Bestenliste ein. Nutzt fast alles, was auf dem Board ist:
Joystick, vier Taster, beide Potis, acht LEDs, RGB-LED, Summer und BMP280.

## Dateien

| Datei | Zweck |
|---|---|
| `main.py` | Das Spiel |
| `ssd1306.py` | OLED-Treiber |

Beide in den **Root-Ordner** des ESP kopieren (Thonny: *Speichern unter* →
*MicroPython-Gerät*, oder `mpremote connect COM3 cp main.py :main.py + cp ssd1306.py :ssd1306.py + reset`).
Die Bestenliste legt das Spiel selbst als `bestenliste.txt` auf dem ESP an.

## Bedienung

| Eingabe | Funktion |
|---|---|
| Joystick | Raumschiff steuern |
| **S17** (oben) | Schießen |
| **S4** (links) | Bombe – kostet 5 Energie, zerstört alle Gegner |
| Joystick-Taster | Schutzschild (verbraucht Energie) |
| **S5** (rechts) | Pause · im Titelbild: Bestenliste |
| **S16** (unten) | Start / weiter · im Titelbild S4 = Steuerung |
| Poti `RP3` (links) | Lautstärke |
| Poti `RP0` (rechts) | Schwierigkeit |

| Anzeige | Bedeutung |
|---|---|
| 8 LEDs | Munition (die nächste LED blinkt beim Nachladen) |
| Balken unten im OLED | Energie für Schild und Bombe |
| RGB-LED | grün = ok, blau = Schild, rot = getroffen, orange = letztes Leben |
| Titelbild unten rechts | Temperatur vom BMP280 |

**Cheatcode** im Titelbild: Joystick ↑ ↑ ← → ← → (änderbar über `CHEAT_CODE`).

## Neu in v2.0

- **Gleiches Spieltempo bei jeder Bildrate:** Alle Bewegungen rechnen jetzt mit
  der vergangenen Zeit statt pro Bild. Vorher lief das Spiel langsamer, sobald
  viele Gegner auf dem Schirm waren. Mit `SPIEL_TEMPO` lässt sich das Tempo
  insgesamt einstellen.
- **Schnellerer OLED-Treiber** (weniger I²C-Befehle pro Bild), Bildrate über
  `MAX_FPS` begrenzt, `I2C_FREQ` einstellbar.
- **Temperatur ohne Zusatzdatei:** Der BMP280 wird direkt ausgelesen –
  vorher brauchte es eine `bmp280.py`, die nicht dabei war, deshalb fehlte
  die Temperatur.
- LEDs, RGB-LED und Display-Invertierung werden nur noch geschrieben, wenn sich
  etwas ändert. Der Summer verstummt jetzt auch in der Pause.
- Kleine Fehler behoben: „Rekord“ auf dem Game-Over-Bild zeigt bei neuem Rekord
  die neue Punktzahl; kaputte Zeilen in `bestenliste.txt` bringen das Spiel
  nicht mehr durcheinander; „Joystick loslassen“ wird beim Start angezeigt.

## Einstellungen (oben in `main.py`)

Munition (`MUNITION_MAX`, `NACHLADEN_PRO_SEKUNDE`, `SCHUSS_PAUSE_MS` …),
Bestenliste (`NAME_LAENGE`, `PLAETZE`), LED-Animation, Cheat-Modus sowie neu:

| Konstante | Standard | Bedeutung |
|---|---|---|
| `SPIEL_TEMPO` | 1.0 | 1.3 = schneller, 0.8 = langsamer |
| `MAX_FPS` | 50 | Obergrenze der Bildrate |
| `I2C_FREQ` | 400000 | OLED-Takt; viele Displays schaffen 800000–1000000 |
| `TASTEN_AKTIV_HIGH` | True | Taster liefern gedrückt 3,3 V |

## Hardware

Siehe [`docs/espBoard.md`](../docs/espBoard.md).

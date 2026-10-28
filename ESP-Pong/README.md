# ESP-Pong v2.0 – Multiplayer-Pong für beliebig viele espBoards

Beliebig viele ESP32-Boards finden sich in einer **Lobby** und spielen paarweise
**Pong** gegeneinander – direkt über **ESP-NOW**, ohne Router und ohne Schul-WLAN.

![Vorschau](vorschau.svg)

## Neu in v2.0

- **Lobby:** Alle Boards im Raum erscheinen in einer Liste – mit Nummer,
  Status (`FREI`, `HOST`, `SPIEL`, `WARTE`) und Signalstärke (je mehr Balken,
  desto näher).
- **Board-Nummer:** Jedes Board hat eine eigene vierstellige Nummer (z. B. `#4128`).
  Sie wird aus der MAC-Adresse berechnet und bleibt nach dem Neustart gleich.
  Wer mag, setzt oben in `main.py` einen eigenen `NAME`.
- **Host-Auswahl:** Mit S16 eröffnest du ein Spiel. Die anderen sehen dich als
  `HOST` und können mit dem Joystick-Taster beitreten. Oder du lädst ein freies
  Board direkt ein.
- **Mehrere Spiele gleichzeitig:** Die Boards reden nach dem Verbinden nur noch
  direkt miteinander, so stören sich mehrere Paare im selben Raum nicht.
- **Deutlich flüssiger:**
  - Das Display bekommt nur noch die Stellen geschickt, die sich bewegen
    (Ball, Schläger) statt jedes Mal das ganze Bild. Pro Bild gehen statt
    ~1 KB nur noch einige Dutzend Byte über I²C – vorher waren ~23 ms pro Bild
    nur für das Display weg, jetzt rechnerisch meist 1–2 ms.
  - Der Host schickt auch die Ballgeschwindigkeit mit. Der Gast rechnet den
    Ball zwischen zwei Paketen selbst weiter, dadurch ruckelt nichts mehr.
  - Pakete werden ohne Warten auf die Quittung gesendet, WLAN-Stromsparen ist
    aus, es werden keine neuen Speicherblöcke pro Bild angelegt.
- **RGB-LED:** grün = verbunden, blau = wartet, rot = Verbindung weg.
- **Verbindungsabbruch:** nach 1 s Pause, nach 5 s automatisch zurück in die Lobby.

## Dateien

| Datei | Zweck |
|---|---|
| `main.py` | Das Spiel (auf **jedes** Board kopieren) |
| `ssd1306.py` | Schneller OLED-Treiber (auf **jedes** Board kopieren) |
| `vorschau.svg` | Vorschau der Bildschirme (nur PC) |

## Auf die Boards kopieren

Auf **jedes** Board kommen dieselben zwei Dateien in den **Root-Ordner**.

**Mit Thonny:** Datei öffnen → *Speichern unter* → *MicroPython-Gerät* →
`main.py` bzw. `ssd1306.py` → Board neu starten.

**Mit mpremote:**

```powershell
mpremote connect COM3 cp main.py :main.py + cp ssd1306.py :ssd1306.py + reset
```

> Falls beim Start `MemoryError` erscheint (sehr knapper Speicher), `main.py`
> in `pong.py` umbenennen, mit `mpy-cross pong.py` übersetzen, `pong.mpy`
> hochladen und als `main.py` nur die Zeile `import pong; pong.main()` verwenden.

## Bedienung

**Beim Start:** Joystick **loslassen**, dann wird die Mittelstellung gemessen.

### Lobby

| Eingabe | Funktion |
|---|---|
| Joystick hoch/runter | Board in der Liste auswählen |
| Joystick-Taster auf `HOST` | Diesem Spiel beitreten |
| Joystick-Taster auf `FREI` | Dieses Board einladen |
| **S16** | Selbst Host werden (Spiel eröffnen) |
| **S4** | Abbrechen / Einladung ablehnen |
| Einladung erhalten | Joystick-Taster = annehmen, S4 = ablehnen (nach 10 s automatisch nein) |

Status in der Liste:

| Status | Bedeutung |
|---|---|
| `FREI` | Board ist in der Lobby → kann eingeladen werden |
| `HOST` | Board hat ein Spiel eröffnet → man kann beitreten |
| `WARTE` | Board hat gerade jemanden eingeladen |
| `SPIEL` | Board spielt schon |

### Im Spiel

| Eingabe | Funktion |
|---|---|
| Joystick hoch/runter | Eigenen Schläger bewegen (Host = links, Gast = rechts) |
| Joystick-Taster | Nach Spielende: neue Runde (sonst automatisch nach 15 s) |
| **S4** | Match verlassen, zurück zur Lobby |

Wer zuerst **5 Punkte** hat, gewinnt. Der Ball wird bei jedem Schlägertreffer
5 % schneller; wo er den Schläger trifft, bestimmt den Abprallwinkel.

## Punkte-LEDs

- **linke 4 LEDs** = Punkte vom Host (links), **rechte 4 LEDs** = Punkte vom Gast
- die Balken wachsen von außen zur Mitte, bei `4 : 4` leuchten alle acht
- in der Lobby sind alle LEDs aus

`LED_PINS` steht in der echten Reihenfolge auf dem Board (P7 = GPIO 13 links …
P0 = GPIO 32 rechts). Sind die Hälften trotzdem vertauscht: `LEDS_UMDREHEN = True`.

## Einstellungen (oben in `main.py`)

| Konstante | Standard | Bedeutung |
|---|---|---|
| `NAME` | `""` | Eigener Name (max. 8 Zeichen), leer = `#Nummer` |
| `WIN_SCORE` | 5 | Punkte für den Sieg (max. 4 LEDs pro Seite) |
| `PADDLE_SPEED` | 95 | Schlägertempo in Pixel/s |
| `BALL_START` / `BALL_MAX` | 85 / 150 | Balltempo in Pixel/s |
| `BALL_PLUS` | 1.05 | Tempo-Faktor pro Treffer |
| `MAX_FPS` | 100 | Obergrenze der Bildrate |
| `I2C_FREQ` | 400000 | OLED-Takt; viele Displays laufen auch mit 800000–1000000 |
| `TX_POWER` | 8 | Sendeleistung in dBm |
| `KANAL` | 1 | WLAN-Kanal – auf allen Boards gleich lassen |
| `STROMSPAREN_AUS` | True | WLAN-Stromsparen aus = weniger Verzögerung, etwas mehr Strom |
| `HOCH_POSITIV` | True | Richtung der Joystick-Achse |
| `TOTZONE` | 9000 | Joystick-Totzone |
| `RGB_AN` / `RGB_HELL` | True / 40 | RGB-LED nutzen / Helligkeit |

## Wichtig: Stromversorgung

ESP-NOW nutzt das WLAN-Funkteil, das kurz 200–300 mA zieht. Startet das Board mit
`Brownout detector was triggered` neu, ist die Versorgung zu schwach – **kein
Softwarefehler**. Abhilfe steht in [`docs/espBoard.md`](../docs/espBoard.md#stromversorgung-und-wlan).

## Technik

- Alle Boards senden zweimal pro Sekunde ein **Beacon** an alle
  (`ff:ff:ff:ff:ff:ff`): Status, Nummer, Name. Daraus baut die Lobby ihre Liste,
  die Signalstärke kommt aus `ESPNow.peers_table`.
- Beitreten: Gast schickt `JOIN`, Host antwortet `ACCEPT`. Danach sprechen die
  beiden nur noch direkt (Unicast) miteinander.
- Der **Host** rechnet die Ballphysik und schickt ~60× pro Sekunde (und sofort bei
  jedem Abprall) den Spielstand. Der **Gast** schickt seine Schlägerposition.
- Alle Pakete beginnen mit dem Byte `0xB7`, damit fremde ESP-NOW-Programme
  (oder ESP-Pong v1.x) nicht stören.

| Paket | Richtung | Inhalt |
|---|---|---|
| `BEACON` (1) | an alle | Status, Nummer, Name |
| `JOIN` (2) / `ACCEPT` (3) / `DENY` (4) | Gast ↔ Host | Beitreten / ok / nein |
| `INVITE` (5) | Board → Board | Einladung |
| `STATE` (6) | Host → Gast | Ball x/y, Geschwindigkeit x/y (×16), Host-Schläger, Punkte, Phase |
| `PADDLE` (7) | Gast → Host | Schläger y (×16), Neustart-Zähler |
| `BYE` (8) | beide | Match verlassen |

## Fehlersuche

| Problem | Ursache / Lösung |
|---|---|
| Board rebootet beim Start von ESP-NOW | Brownout – siehe Stromversorgung |
| Andere Boards erscheinen nicht | Alle Boards brauchen **v2.0**; gleicher `KANAL`; keine Verbindung zu einem Access Point |
| „KEINE ANTWORT“ beim Beitreten | Board zu weit weg oder gerade in einem anderen Zustand – nochmal versuchen |
| Schläger bewegt sich verkehrt | `HOCH_POSITIV` umstellen |
| Taster reagieren nicht | `TASTEN_AKTIV_HIGH` prüfen (Board: active-high → `True`) |
| Ball zu schnell / langsam | `BALL_START`, `BALL_MAX`, `BALL_PLUS` anpassen |

## Hardware

Siehe [`docs/espBoard.md`](../docs/espBoard.md) – Bauteile, Pinbelegung, Messprotokoll.

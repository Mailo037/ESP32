# ESP-Hub v1.0 – Spiele-Galerie für das espBoard

Nicht mehr für jedes Spiel `main.py` austauschen: Auf dem Board liegt der
Hub als `main.py`, die Spiele daneben als `gal_*.py`. Nach dem Einschalten
erscheint eine Galerie, dort wählst du das Spiel aus.

```
┌────────────────────────┐
│ESP-HUB              2/4│
│  3D Render             │
│> ESP Pong              │
│  Geometry Dash         │
│  Space Dodge           │
│────────────────────────│
│      S5 = Starten      │
└────────────────────────┘
```

## Bedienung

| Wo | Eingabe | Funktion |
|---|---|---|
| Galerie | Joystick ↑/↓ oder S17/S16 | Spiel auswählen |
| Galerie | **S5**, Joystick → oder Joystick-Taster | Spiel starten |
| im Spiel | **S4 + S5 zusammen halten** (0,4 s) | Spiel sofort beenden, zurück zur Galerie |
| überall | Poti `RP3` (links) | Lautstärke, ganz links = stumm |

Die LED-Reihe zeigt, welcher Eintrag gewählt ist. Die Galerie merkt sich das
zuletzt gespielte Spiel.

## Installieren

**Am einfachsten** (kopiert Hub und alle Spiele aus diesem Repo):

```powershell
pip install mpremote
python Hub/installieren.py COM3
```

**Von Hand mit Thonny:** In den Root-Ordner des ESP speichern:

| Datei aus dem Repo | Name auf dem ESP |
|---|---|
| `Hub/main.py` | `main.py` |
| `Hub/ssd1306.py` | `ssd1306.py` |
| `ESP-Pong/main.py` | `gal_ESP_Pong.py` |
| `Space-Dodge/main.py` | `gal_Space_Dodge.py` |
| `Geometry-Dash/main.py` | `gal_Geometry_Dash.py` |
| `3D-Render/main.py` | `gal_3D_Render.py` |

## Eigenes Spiel hinzufügen

Datei `gal_MeinSpiel.py` auf den ESP laden, fertig. In der Galerie heißt sie
„MeinSpiel“, aus `_` werden Leerzeichen. Das Spiel muss dafür nicht
angepasst werden, jedes normale `main.py` funktioniert.

Damit **S4 + S5** wirkt, muss das Spiel ab und zu `time.ticks_ms()` oder
`time.sleep_ms()` aufrufen. Jede Spielschleife tut das ohnehin.

## Sandbox

Jedes Spiel läuft abgeschottet vom Hub:

- **Frischer Interpreter:** Vor und nach jedem Spiel macht der Hub einen
  Soft-Reset. Kein Spiel erbt Speicher, Pins oder ESP-NOW-Zustand vom
  vorigen, und große Spiele bekommen den ganzen RAM.
- **Eigener Namensraum:** Das Spiel sieht keine Variablen oder Funktionen des Hubs.
  `import main` ist gesperrt.
- **Eigener Ordner:** `open()` und `os.listdir/remove/rename/…` zeigen nur in
  `/daten/<Spiel>/`. `main.py`, `boot.py` und die `gal_`-Dateien kann ein Spiel
  weder lesen noch löschen, und `..` ist verboten. Bestenlisten und Rekorde
  liegen deshalb z. B. in `/daten/Space_Dodge/bestenliste.txt`.
- **Beenden klappt immer:** S4 + S5 löst eine Ausnahme aus, die nicht von
  `Exception` erbt. Ein `except Exception:` im Spiel fängt sie also nicht ab.
  Verschluckt ein Spiel sie trotzdem mit einem nackten `except:`, startet der
  Hub nach 1 s das ganze Board neu.
- **Absturz:** Die Fehlermeldung erscheint auf dem OLED, mit **S5** geht es
  zurück zur Galerie.

Das ist ein Schutz gegen Versehen, keine echte Sicherheitsgrenze.
MicroPython kennt keine getrennten Prozesse, und ein absichtlich böses Programm
käme über Umwege (z. B. `import vfs`) trotzdem an den Flash.

## So funktioniert es

1. Die Galerie schreibt den Namen des Spiels in `hub_start.txt` und macht
   einen Soft-Reset.
2. `main.py` startet neu, findet `hub_start.txt` und löscht die Datei sofort.
   Bei einem Absturz landet man so wieder in der Galerie, nicht in einer
   Endlosschleife.
3. Der Hub ersetzt `time`, `os` und `open` durch die Sandbox-Versionen und
   führt `gal_<Spiel>.py` in einem leeren Namensraum aus.
4. Spielende, S4 + S5 oder Fehler: Soft-Reset, und die Galerie erscheint.

Im [Simulator](https://mailo037.github.io/ESP32-Programme/) ist „Hub“ jetzt
voreingestellt. Er packt automatisch alle Ordner als `gal_`-Dateien dazu.

## Hardware

Siehe [`docs/espBoard.md`](../docs/espBoard.md).

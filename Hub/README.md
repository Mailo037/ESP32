# ESP-Hub v1.1 – Spiele-Galerie für das espBoard

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
│    S5 Start S4 Info    │
└────────────────────────┘
```

## Bedienung

| Wo | Eingabe | Funktion |
|---|---|---|
| Galerie | Joystick ↑/↓ oder S17/S16 | Spiel auswählen |
| Galerie | **S5**, Joystick → oder Joystick-Taster | Spiel starten |
| Galerie | **S4** | Info: Board-Nummer, Board-ID, Online-Speicher testen (S5) |
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
| `Hub/hub_online.py` | `hub_online.py` |
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

## Speichern: `import hub`

Spiele aus der Galerie bekommen das Modul `hub`. Außerhalb des Hubs gibt
es das Modul nicht, deshalb so einbinden:

```python
try:
    import hub
except ImportError:
    hub = None
```

| Funktion | Was sie tut |
|---|---|
| `hub.laden(k, standard)` / `hub.speichern(k, wert)` | Spielstand **dieses Boards** (Zahlen, Text, Listen, Dicts; max. 4 KB pro Spiel) |
| `hub.eintragen(liste, punkte, name)` | Bestenliste, je Board zählt der beste Wert. `True` bei neuem persönlichen Rekord |
| `hub.bestenliste(liste, n)` | `[(name, punkte, eigener), …]`, beste zuerst, über **alle Boards** |
| `hub.global_laden(k)` / `hub.global_setzen(k, w)` | Werte, die für alle Boards gleich sind |
| `hub.global_addieren(k, n=1)` | Zähler für alle Boards, z. B. „Spiele insgesamt“. Online wird atomar addiert, gleichzeitige Boards gehen also nicht verloren |
| `hub.board_id()` / `hub.board_nr()` | `"246f28b01230"` / `4656`. Die Nummer ist dieselbe wie in ESP-Pong |
| `hub.online()` | Hat der letzte Abgleich geklappt? |
| `hub.sync()` | Sofort abgleichen. Blockiert 1–5 s und schaltet WLAN ein, also nicht mitten in einem ESP-NOW-Spiel aufrufen |

Alle Funktionen außer `sync()` arbeiten **nur lokal und sofort**, ohne
Wartezeit im Spiel. Den Abgleich übernimmt der Hub:

- **beim Spielstart:** Daten holen, damit Bestenlisten aktuell sind („Online-Daten laden …“)
- **beim Spielende** (auch nach S4 + S5): Neues hochladen („Speichere online …“)
- **ohne Netz:** Alles bleibt lokal in `/hubdaten/` und wird beim nächsten
  erfolgreichen Abgleich nachgeholt, auch für andere Spiele.

Schon eingebaut: **Space Dodge** zeigt nach der eigenen Bestenliste (S5 im
Titelbild) eine zweite Seite „ONLINE“ mit allen Boards. **Geometry Dash**
zeigt pro Level `Du 87% Top 100%`.

### Pro Board: die eFuse-MAC

Alles wird unter der **Board-ID** gespeichert. Das ist die MAC-Adresse, die
ab Werk im eFuse des ESP32 eingebrannt ist (`machine.unique_id()`). Neu
flashen, umbenennen oder Dateien löschen ändert sie nicht. Spiele können die
ID nur lesen. Die WLAN-MAC lässt sich per Software umstellen, deshalb
nimmt der Hub sie nicht.

Grenze: Der Server kann nicht prüfen, ob eine Anfrage wirklich von diesem Board
kommt. Wer die URL kennt, kann mit dem PC auch unter fremder ID schreiben.
Für Klassen-Bestenlisten reicht das. Für mehr Schutz das Passwort (`auth`)
setzen und die URL nicht weitergeben.

## Online-Speicher einrichten

Ohne Einrichtung speichert der Hub nur lokal. Für online gibt es zwei Wege:

**A) PC im selben WLAN, ohne Konto:**

```powershell
python Hub/server/hub_server.py --auth GEHEIM
```

`http://<IP des PCs>:8080/` im Browser zeigt dann alle Bestenlisten.
Die Daten liegen in `Hub/server/hub_daten.json`.

**B) Firebase Realtime Database (kostenlos, im Internet):**

1. Auf [console.firebase.google.com](https://console.firebase.google.com) ein
   Projekt anlegen und *Realtime Database* erstellen.
2. Unter *Regeln* den Inhalt von [`server/firebase-regeln.json`](server/firebase-regeln.json)
   einfügen. Die Regeln lassen nur gültige Board-IDs und Bestenlisten-Einträge zu.
3. Die Datenbank-URL notieren (`https://….firebasedatabase.app`).

Danach `Hub/hub_online.beispiel.json` nach `Hub/hub_online.json` kopieren
und WLAN, Passwort und URL eintragen. `installieren.py` kopiert die Datei mit
aufs Board. Von Hand: als `hub_online.json` in den Root-Ordner speichern.
`hub_online.json` ist in `.gitignore`, das WLAN-Passwort landet also nicht auf
GitHub. Ein Spiel kann die Datei nicht lesen (Sandbox).

In der Galerie zeigt eine kleine **Wolke** in der Kopfzeile, dass der
Online-Speicher eingerichtet ist. **S4** öffnet die Info-Seite, dort testet
**S5** die Verbindung.

Im **Simulator** gibt es dafür das Feld *Online-Speicher*. Das WLAN „steht“
dort immer, die Anfragen schickt der Browser. Die Seite läuft über https,
deshalb geht dort nur eine https-Adresse (Firebase). Den PC-Server erreicht
der Browser nur, wenn der Simulator selbst über http läuft.

## Sandbox

Jedes Spiel läuft abgeschottet vom Hub:

- **Frischer Interpreter:** Vor und nach jedem Spiel macht der Hub einen
  Soft-Reset. Kein Spiel erbt Speicher, Pins oder ESP-NOW-Zustand vom
  vorigen, und große Spiele bekommen den ganzen RAM.
- **Eigener Namensraum:** Das Spiel sieht keine Variablen oder Funktionen des Hubs.
  `import main` und `import hub_online` sind gesperrt. Ein Spiel bekommt nur `import hub`.
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

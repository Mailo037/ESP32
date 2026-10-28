# ESP-Hub v2.0 – Spiele-Galerie mit App-Store für das espBoard

Auf dem Board liegt der Hub als `main.py`, jedes Spiel ist eine eigene Datei
`gal_<Name>.py`. Nach dem Einschalten erscheint die Galerie. Neue Spiele
kommen aus dem **App-Store**, aus dem **Web-Portal** oder einfach per Hochladen.

```
┌────────────────────────┐
│ESP-HUB  ☁         1.2M │   ☁ = online eingerichtet, rechts: freier Flash
│ ESP Pong               │
│>Geometry Dash         ↑│   ↑ = Update verfügbar
│ Space Dodge            │
│ + App-Store            │
│────────────────────────│
│v1.1>1.2       S4 Menue │
└────────────────────────┘
```

## Bedienung

| Wo | Eingabe | Funktion |
|---|---|---|
| Galerie | Joystick ↑/↓ oder S17/S16 | auswählen |
| Galerie | **S5**, Joystick → oder Joystick-Taster | starten / öffnen |
| Galerie | **S4** | App-Menü: Version, Größe, Daten, genutzte Dienste, Update, Spielstand löschen, Deinstallieren |
| im Spiel | **S4 + S16 halten** | App-Menü, das Spiel pausiert: Weiter, Schließen, Spielstand löschen, Deinstallieren |
| im Spiel | **S4 + S5 halten** | Spiel sofort beenden |
| überall | Poti `RP3` (links) | Lautstärke, ganz links = stumm |

Tipp für das Menü im Spiel: erst S16, dann S4 drücken. Viele Spiele reagieren
selbst auf S4, zum Beispiel ESP-Pong mit „zurück zur Lobby“.

Das App-Menü im Spiel friert das Spiel ein und stellt danach das Bild wieder her.
Die Zeit im Menü rechnet der Hub aus `ticks_ms()` heraus, damit das Spiel keinen
Zeitsprung macht.

Einträge am Ende der Galerie:

- **+ App-Store:** alle Apps aus dem Store. `+` = neu, `^` = Update,
  `L` = gleiche App liegt lokal, „Alle updaten“.
- **i Board-Info:** Board-Nummer und ID, freier Flash und RAM, Konto,
  *Jetzt abgleichen*, *Koppeln*, *Verbindung testen*.

## Installieren

```powershell
pip install mpremote
python installieren.py COM3
```

Das kopiert den Hub (`main.py`, `hub_apps.py`, `hub_galerie.py`, `hub_online.py`,
`ssd1306.py`) auf das Board. Spiele werden ueber den Online-App-Store installiert;
dieser Branch enthaelt keine Spiele. Optional lassen sich eigene `.py`-Dateien
hinter dem Port angeben. Liegt
`hub_online.json` da, kopiert das Skript sie mit.

## Online: Vercel-Bridge + Firebase

```
espBoard ──https──▶ Vercel (esphub-steel.vercel.app) ──▶ Firebase Realtime Database
   nur Board-ID + Board-Schlüssel        prüft alles          Zugangsdaten nur in Vercel
```

Das Board spricht **nur mit Vercel**. Die Firebase-Zugangsdaten liegen
ausschließlich in den Vercel-Umgebungsvariablen. Weder das Board noch ein
Browser bekommt sie zu sehen, und im Repo stehen sie auch nicht. Einrichtung:
[Service-Anleitung](../esp-service/README.md).

Auf dem Board in `hub_online.json` (Vorlage `hub_online.beispiel.json`):

```json
{ "wlan": "WLAN-Name", "passwort": "WLAN-Passwort", "url": "https://esphub-steel.vercel.app", "auth": "" }
```

`auth` ist nur nötig, wenn in Vercel `HUB_TOKEN` gesetzt ist.

Die Webseite hat zwei Teile:

| Adresse | Für wen | Was |
|---|---|---|
| `/` | alle | **Portal:** App-Galerie, Bestenlisten, Konto anlegen, *Meine Boards* (koppeln, installierte Apps, genutzte Dienste, Fern-Installation und Deinstallation), *Meine Apps* (`.py`/`.zip` hochladen: privat oder zur Prüfung) |
| `/admin` | nur du (Passwort `ADMIN_TOKEN`) | Übersicht, alle Boards (Apps, Speicher, Konto, Original-Hub?), sperren und zurücksetzen, Apps (hochladen, ausblenden, Code ansehen), Einreichungen freigeben oder ablehnen, Konten, Speicherlimits, Regel für veränderte Hubs, Bestenlisten mit Höchstpunkten |

### Board koppeln

1. Im Portal ein Konto anlegen.
2. *Meine Boards*: die Board-ID eingeben (steht am Board unter **Board-Info**)
   und auf „Code anfordern“ klicken.
3. Am Board: Board-Info → **Koppeln**. Das Display zeigt einen 6-stelligen Code.
4. Den Code im Portal eingeben. Nach 5 falschen Versuchen verfällt die Anfrage,
   nach 10 Minuten auch.

Danach kannst du im Portal Apps installieren und entfernen. Das Board erledigt
die Aufträge beim nächsten Abgleich: nach dem Einschalten, bei Spielstart oder
-ende oder über Board-Info → *Jetzt abgleichen*.

### Wann gleicht das Board ab?

- **Einschalten:** anmelden, Aufträge holen und ausführen
- **Spielstart:** Spielstände und Bestenlisten holen, App-Katalog für die Update-Anzeige
- **Spielende** (auch nach S4+S5): Neues hochladen
- **ohne Netz:** Alles bleibt lokal in `/hubdaten/` und wird später nachgeholt

## Vertrauenswürdige und lokale Apps

| | vertrauenswürdig | lokal |
|---|---|---|
| Herkunft | App-Store, eigenes Konto, `installieren.py` | selbst aufgespielt oder veränderte Datei |
| erkannt an | SHA-256 der Datei passt zum Store oder zur Installation | Prüfsumme passt nicht |
| `import hub` (Speicher, Bestenlisten) | ja | **nein**, `ImportError` |
| Updates aus dem Store | ja | nein |
| Online-Abgleich | ja | nein |

Lokale Apps laufen ganz normal in der Sandbox, nur ohne Hub-Dienste. Ist das
Board gekoppelt, bietet das App-Menü einer lokalen App zwei Punkte:

- **In Konto laden:** Die App liegt dann privat in deinem Konto, ist sofort
  vertrauenswürdig und auf deinen anderen Boards installierbar.
- **Zur Prüfung:** Die App geht an den Admin. Nach der Freigabe steht sie für alle
  im Store.

## Für Spiele: `import hub`

```python
try:
    import hub          # nur in der Galerie und nur für vertrauenswürdige Apps
except ImportError:
    hub = None
```

| Funktion | Was sie tut |
|---|---|
| `hub.laden(k, standard)` / `hub.speichern(k, wert)` | Spielstand dieses Boards |
| `hub.eintragen(liste, punkte, name)` | Bestenliste, je Board zählt der beste Wert |
| `hub.bestenliste(liste, n)` | `[(name, punkte, eigener), …]` über alle Boards |
| `hub.global_laden/global_setzen/global_addieren` | Werte für alle Boards; `addieren` zählt atomar hoch |
| `hub.speicher_info()` | `(belegt, maximal)` in Bytes, das Limit legt der Admin fest |
| `hub.board_id()` / `hub.board_nr()` | eFuse-MAC / Nummer wie in ESP-Pong |
| `hub.online()` / `hub.sync()` | Status / sofort abgleichen (blockiert 1–5 s) |

Alles außer `sync()` arbeitet lokal und sofort, der Hub gleicht vor und nach dem
Spiel ab.

Kopfzeilen einer App, alle optional:

```python
# HUB-NAME: Mein Spiel
# HUB-VERSION: 1.2
# HUB-INFO: Kurze Beschreibung für Store und Galerie
```

## Sicherheit

**Was das System verhindert:**

- **Sandbox:** Ein Spiel sieht nur `/daten/<Spiel>/`. `main.py`, die Hub-Module,
  `hub_online.json` (WLAN-Passwort) und `/hubdaten/` (Board-Schlüssel) sind
  für Spiele unerreichbar. Ein Spiel kann den Hub also nicht verändern.
- **Board-Schlüssel:** Bei der ersten Anmeldung vergibt der Server einen
  geheimen Schlüssel, nur dieses Board kennt ihn. Danach weist der Server jede
  Anfrage unter dieser Board-ID ohne den Schlüssel ab. Fremde können also nicht
  unter deiner ID speichern, und der Kopplungscode erscheint nur auf dem echten Board.
- **Server prüft alles selbst:** nur die eigene ID, Speicherlimits pro App und
  Board, Größen, erlaubte Pfade, Höchstpunkte pro Bestenliste. Gesperrte Boards
  und Konten bekommen nichts mehr.
- **Veränderter Hub:** Das Board meldet SHA-256-Prüfsummen seiner Hub-Dateien.
  Der Server vergleicht sie mit dem Original aus GitHub. Im Admin legst du fest,
  was mit veränderten Hubs passiert: *erlauben* (nur markieren), *nur lesen* oder
  *sperren*.

**Ehrliche Grenze:** Wer ein Board in der Hand hat, kann darauf alles ändern.
Bei MicroPython sind alle Dateien lesbar und überschreibbar. Ein gezielt
umgebauter Hub kann richtige Prüfsummen vortäuschen und mit seinem eigenen
Schlüssel im Rahmen der Regeln schreiben, zum Beispiel einen Fantasie-Rekord
unterhalb der Höchstpunkte. Dagegen helfen nur Höchstpunkte, Sperren und das
Löschen einzelner Einträge im Admin. Einen echten Schutz gäbe es nur mit Secure
Boot und Flash-Verschlüsselung des ESP32 und einem fest in die Firmware
eingebauten Hub. Das ist aufwändig und hier nicht umgesetzt.

## Eigener Server statt Vercel (ohne Konto)

`python ../esp-service/server/hub_server.py --auth GEHEIM` speichert alles in einer
JSON-Datei auf dem PC und hat einen App-Store aus den Repo-Ordnern. Portal,
Admin, Kopplung und Limits gibt es dort nicht. Als `url` dann
`http://<PC-IP>:8080` eintragen.

## Simulator

Im [Simulator](https://mailo037.github.io/ESP32-Programme/) ist „Hub“
voreingestellt. Alle Ordner sind als vertrauenswürdige `gal_`-Dateien dabei. Im
Feld *Online-Speicher* kann man die Vercel-Adresse eintragen, die Anfragen
schickt dann der Browser.

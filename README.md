# ESP-Hub-Backend (Vercel)

Bridge zwischen den Boards und Firebase, dazu das Portal (`/`) und der Admin
(`/admin`). Läuft ohne Abhängigkeiten auf der Node-Laufzeit von Vercel.

Live: **https://esphub-steel.vercel.app** (Vercel-Projekt `esphub`)

## Branch `service` mit Vercel verbinden

Dieser Branch ist ein eigenstaendiges Service-Projekt. `api/`, `lib/`,
`package.json` und `vercel.json` liegen direkt im Repository-Stamm.

1. Den lokalen Branch zuerst nach GitHub veroeffentlichen:
   `git push -u origin service` (im Ordner `esp-service`).
2. In Vercel das Repository `Mailo037/ESP32` verbinden oder beim
   bestehenden Projekt die Einstellungen anpassen.
3. **Root Directory:** Repository-Stamm (`.`); einen bisherigen Eintrag
   `Hub/vercel` entfernen. **Framework Preset:** Other. Build und Output
   werden durch `vercel.json` festgelegt; keine Dashboard-Overrides verwenden.
4. Unter **Settings -> Environments -> Production -> Branch Tracking** den
   Branch **service** eintragen und speichern.
5. Die unten genannten Pflichtvariablen fuer **Production** setzen bzw.
   beim bestehenden Projekt beibehalten. Danach den Branch `service` deployen.

Weitere Pushes auf `service` loesen automatisch ein Production-Deployment aus.
Die `vercel.json` erlaubt Git-Deployments fuer `service` und deaktiviert sie
fuer andere Branches, sofern diese Konfiguration auf dem betreffenden Branch
vorliegt. Die Branch-Tracking-Einstellung selbst wird im Vercel-Projekt gesetzt.
Ein vorhandener Ignored Build Step darf `service` nicht ueberspringen.

**Quellen getrennt vom Deployment-Branch:** `GITHUB_BRANCH=programs` laedt die
Spiele. `HUB_GITHUB_BRANCH=hub` (Standard) laedt aktuelle Hub-Dateien aus dessen
Stamm. Registrierte Firmware-Releases verwenden ihre gespeicherten Pruefsummen;
fuer alte Hubs der Version 2.0 bleibt `main/Hub/` als Originalquelle erhalten.
`service` ist ausschliesslich der Deployment-Branch.

Der Build Command ist jetzt `node scripts/build-static.mjs`, das Output Directory
ist `public` (beides in `vercel.json`). Keine Dashboard-Overrides dafuer setzen.

## Simulator unter /simulator

Der Service liefert den Simulator unter `/simulator`. Die Liste enthaelt
freigegebene oeffentliche GitHub- und Upload-Apps. Nach Anmeldung im Portal
kommen die eigenen privaten Apps hinzu. Fremde private und versteckte Apps
bleiben ausgeschlossen. ZIP-Projekte laden Module und binaere Assets;
gemeinsame Treiber kommen aus dem aktiven Firmware-Release bzw. dem Hub-Branch.
Apps starten per Klick, nicht automatisch beim Besuch.

Read-only-Endpunkte: `/portal/simulator/apps`,
`/portal/simulator/apps/<ID>?paket=<Hash>` und `/portal/simulator/treiber`.
Die Paket-ID bindet den Download an den angezeigten Projektstand.

Der Simulator wird im separaten Branch entwickelt. Vor einem Service-Commit
`npm run sync:simulator` ausfuehren (Quelle ist standardmaessig der benachbarte
Ordner `esp-simulator`), dann beide Branches committen und pushen. Die Kopie
in `simulator/` ist versioniert, damit Vercel unabhaengig bauen kann.
`npm run build` kopiert nur statische Simulator-Dateien nach `public/simulator`;
die API-Quellen bleiben ausserhalb. Vercel setzt COOP-/COEP-Header fuer WASM
und SharedArrayBuffer.

Dokumentation: [Vercel Git-Deployments](https://vercel.com/docs/git) und
[Branch-Regeln](https://vercel.com/docs/project-configuration/git-configuration).

## Hub-Firmware und Projekt-ZIPs

Unter **Admin -> Firmware** koennen ausschliesslich angemeldete Admins neue
Firmware-ZIPs mit Version (X.Y.Z) und Hinweisen erstellen. Erst der separate
Schritt **Veroeffentlichen** aktiviert das Update fuer die Boards. Dieselbe
Versionsnummer kann nicht fuer unterschiedliche Firmware-Dateien verwendet
werden; Downgrades und paralleles Ueberschreiben der aktiven Version werden
abgewiesen. Alte Releases bleiben fuer bereits gestartete Downloads erhalten.

Die ZIP wird im Hub-Projekt mit `python release_erstellen.py` erstellt und
enthaelt genau `main.py`, `hub_apps.py`, `hub_galerie.py`, `hub_online.py`,
`hub_update.py`, `ssd1306.py`, `bmp280.py` und `hub_version.json`.
`boot.py` wird einmalig per USB installiert und nicht per OTA ersetzt.
Auch den initialen Release 2.1.0 hochladen und veroeffentlichen, damit dessen
Pruefsummen als offizieller Hub-Stand registriert sind.

Die neuen Board-Endpunkte `GET /firmware` und
`GET /firmware/<Release-ID>/<Datei>` verlangen eine gueltige Board-Anmeldung.
Sie bleiben fuer authentifizierte, nicht gesperrte Boards auch bei abweichenden
Firmware-Pruefsummen erreichbar, damit diese sich aktualisieren koennen.
Firmware-Releases, Versionsindex und aktives Manifest liegen unter
`esphub_admin/firmware`. Die vorhandenen gesperrten Firebase-Regeln bleiben
passend: Schreibzugriff erfolgt ausschliesslich ueber den Service.

**App-Uploads im Admin und Portal sind jetzt ZIPs**, keine Auswahl mehrerer
Python-Dateien. Module und Assets bleiben zusammen mit `main.py` erhalten,
auch bei privaten Apps und der anschliessenden Admin-Freigabe. Grenzen:
1 MB ZIP-Datei, 512 KB entpackt, maximal 128 Eintraege. Pfad-Traversierung,
Symlinks, doppelte Dateinamen, beschaedigte CRCs und ZIP-Bomben werden abgelehnt.
Projektdateien werden separat und nur ueber den autorisierten App-Katalog mit
Paket-ID ausgeliefert, damit ein Update waehrend des Downloads keine gemischte
Installation erzeugt.

`ssd1306.py` und `bmp280.py` werden im Stamm oder in `lib/` nur dann entfernt,
wenn ihr Hash dem entsprechenden Treiber des aktiven Hub-Releases entspricht.
Ohne aktiven Release gelten die Hashes aus `shared-drivers.json` als Bootstrap
fuer Hub 2.1.0. Diese Datei muss bei Aenderungen der Bootstrap-Treiber angepasst
werden; nach Aktivierung eines Releases werden dessen Hashes verwendet.
Abweichende Treiber werden vollstaendig gespeichert. Der Katalog zaehlt nur
die verbleibenden App-Dateien als Installationsgroesse.

Die bisherige GitHub-Quelle fuer Spiele bleibt erhalten. Firmware-Updates
verwenden dagegen die vom Admin hochgeladenen Releases. Die Pruefsummen
registrierter Firmware-Versionen werden gegen ihren eigenen Release geprueft,
damit ein aelterer offizieller Hub nicht als manipuliert markiert wird.

Lokal pruefen: `npm test` (Mock-Datenbank, keine Live-Schreibzugriffe).

### Echte Firebase-Funktionspruefung

Production-Builds pruefen vor der Veroeffentlichung die Verbindung zum Projekt
`esp32-services`. Der Test verwendet dieselben Server-Routen und Zugangsdaten
wie die App: Registrierung/Login, private ZIP-Projekte, Board-Kopplung,
Installationsauftraege, Spielstaende, Bestenlisten, Quoten und bedingte Writes.
Er legt ausschliesslich zufaellig benannte Diagnose-Daten an, prueft vorher,
dass diese Pfade frei sind, und entfernt sie anschliessend auch bei Fehlern.
Passwoerter, Board-Schluessel und Dienstkonto-Schluessel erscheinen nicht im Log.
Ein Fehler verhindert die Veroeffentlichung; das letzte funktionierende
Production-Deployment bleibt erhalten. Build-Logs enthalten pro Schritt
`FIREBASE CHECK PASS` sowie abschliessend `FIREBASE CHECK COMPLETE`.

Manuell mit korrekt gesetzten Server-Umgebungsvariablen: `npm run check:cloud`.
Der Test ist kein oeffentlicher HTTP-Endpunkt und braucht keine zusaetzlichen
Admin-Zugangsdaten oder geoeffneten Firebase-Regeln. `FIREBASE_DATABASE_URL`
muss die Datenbankinstanz bezeichnen, niemals `console.firebase.google.com`.

## Zugangsdaten

Alles Geheime gehört **nur** in *Vercel → Projekt esphub → Settings →
Environment Variables*. Nicht ins Repo, nicht in den Chat, nicht aufs Board.

| Variable | Pflicht | Inhalt |
|---|---|---|
| `FIREBASE_DATABASE_URL` | ja | URL der Realtime Database, z. B. `https://esp32-services-default-rtdb.europe-west1.firebasedatabase.app` |
| `FIREBASE_SERVICE_ACCOUNT` | ja | kompletter Inhalt der Dienstkonto-JSON (siehe unten), Typ **Sensitive** |
| `ADMIN_TOKEN` | ja | dein Admin-Passwort, mindestens 8 Zeichen, lang und zufällig, Typ **Sensitive** |
| `HUB_TOKEN` | nein | zusätzliches Passwort für die Boards (`auth` in `hub_online.json`) |
| `GITHUB_REPO` / `GITHUB_BRANCH` | nein | Quelle des App-Stores (`Mailo037/ESP32` / `programs`) |
| `GITHUB_TOKEN` | nein | nur bei sehr vielen Abrufen (GitHub-Limit) |

Nach dem Ändern von Variablen einmal neu deployen: *Deployments → … → Redeploy*.

## Firebase einrichten

1. [Firebase-Konsole](https://console.firebase.google.com), Projekt `esp32-services`.
2. **Build → Realtime Database → Datenbank erstellen.** Region egal, z. B. `europe-west1`.
   Die angezeigte URL ist `FIREBASE_DATABASE_URL`.
3. **Regeln:** den Inhalt von [`firebase-regeln.json`](firebase-regeln.json)
   einfügen, also alles gesperrt. Nur der Server greift über das Dienstkonto zu,
   und das Dienstkonto umgeht die Regeln.
4. **Projekteinstellungen (Zahnrad) → Dienstkonten → Neuen privaten Schlüssel
   generieren.** Es wird eine JSON-Datei heruntergeladen. Ihren kompletten Inhalt
   kopierst du in `FIREBASE_SERVICE_ACCOUNT` in Vercel. Danach die Datei vom PC
   löschen.

Die `firebaseConfig` mit `apiKey` aus der Web-App-Einrichtung brauchst du hier
**nicht**. Sie ist für Browser-Apps gedacht und gibt keinen Zugriff auf die Datenbank.

## Ablage in Firebase

```
esphub/<Spiel>/boards/<id>         Spielstände (Limit je App/Board)
esphub/<Spiel>/global              gemeinsame Werte
esphub/<Spiel>/listen/<Liste>/<id> Bestenlisten
esphub_admin/boards/<id>           Anmeldung: Apps, Nutzung, Flash, Hub-Prüfung, Konto, Schlüssel-Hash
esphub_admin/konten/<name>         Konto (scrypt-Passwort-Hash), gekoppelte Boards
esphub_admin/kopplung/<id>         offene Kopplung (10 min)
esphub_admin/auftraege/<id>        Fern-Installation und Deinstallation
esphub_admin/apps/<id>             freigegebene Uploads (Store)
esphub_admin/privat/<konto>/<id>   private Apps eines Kontos
esphub_admin/einreichungen/<id>    Apps zur Prüfung
esphub_admin/limits, belegt, gesperrt, versteckt, hoechstpunkte, einstellungen
```

## Routen

| Route | Wer | Zweck |
|---|---|---|
| `POST /melden` | Board | anmelden (beim ersten Mal: Board-Schlüssel), Apps, Nutzung, Hub-Prüfsummen, Aufträge |
| `GET /apps`, `/apps/<id>` | Board | Store: öffentliche + private Apps des Besitzers |
| `/esphub/<…>.json` | Board | Online-Speicher, geprüft |
| `GET /limits/<id>/<app>` | Board | Speicherlimits |
| `GET /kopplung` | Board | Code für das Display |
| `POST /hochladen` | Board | lokale App ins Konto oder zur Prüfung |
| `/`, `/portal/...` | alle / Konto | Portal |
| `/admin`, `/admin/api/...` | Admin | Verwaltung |

Jede Board-Anfrage trägt `?board=<id>&t=<Schlüssel>`. Admin- und
Portal-Sitzungen laufen über signierte, `HttpOnly`/`Secure`/`SameSite=Strict`-Cookies.
Ändernde Aufrufe brauchen zusätzlich eine eigene Kopfzeile (Schutz gegen CSRF).

## Lokal testen

`api/hub.js` lässt sich mit einem normalen `node:http`-Server starten. Als Firebase
dient dabei `server/hub_server.py`: Es spricht dasselbe REST, also
`FIREBASE_DATABASE_URL=http://127.0.0.1:8080` und `FIREBASE_SECRET=<auth>` setzen.

Der optionale Python-Server hat in diesem reinen Service-Branch keine lokalen
Spiele fuer seinen eigenen App-Katalog. Der Vercel-App-Store laedt sie aus GitHub.

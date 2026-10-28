# ESP-Hub-Backend (Vercel)

Bridge zwischen den Boards und Firebase, dazu das Portal (`/`) und der Admin
(`/admin`). Läuft ohne Abhängigkeiten auf der Node-Laufzeit von Vercel.

Live: **https://esphub-steel.vercel.app** (Vercel-Projekt `esphub`)

## Branch `service` mit Vercel verbinden

Dieser Branch ist ein eigenstaendiges Service-Projekt. `api/`, `lib/`,
`package.json` und `vercel.json` liegen direkt im Repository-Stamm.

1. Den lokalen Branch zuerst nach GitHub veroeffentlichen:
   `git push -u origin service` (im Ordner `esp-service`).
2. In Vercel das Repository `Mailo037/ESP32-Programme` verbinden oder beim
   bestehenden Projekt die Einstellungen anpassen.
3. **Root Directory:** Repository-Stamm (`.`); einen bisherigen Eintrag
   `Hub/vercel` entfernen. **Framework Preset:** Other. Kein Build Command
   und kein Output Directory ueberschreiben; der Service braucht keinen
   Frontend-Build und keine zusaetzlichen npm-Pakete.
4. Unter **Settings -> Environments -> Production -> Branch Tracking** den
   Branch **service** eintragen und speichern.
5. Die unten genannten Pflichtvariablen fuer **Production** setzen bzw.
   beim bestehenden Projekt beibehalten. Danach den Branch `service` deployen.

Weitere Pushes auf `service` loesen automatisch ein Production-Deployment aus.
Die `vercel.json` erlaubt Git-Deployments fuer `service` und deaktiviert sie
fuer andere Branches, sofern diese Konfiguration auf dem betreffenden Branch
vorliegt. Die Branch-Tracking-Einstellung selbst wird im Vercel-Projekt gesetzt.
Ein vorhandener Ignored Build Step darf `service` nicht ueberspringen.

**App-Quelle getrennt vom Deployment-Branch:** `GITHUB_BRANCH` bleibt vorerst
`main`, ebenso der Standardwert im Code. Nicht auf `service` setzen: Dieser
Branch enthaelt weder Spiele noch die Hub-Firmware. Die Pruefsummen werden
weiter aus `main/Hub/` geladen. Die lokalen Branches `programs` und `hub`
sind noch nicht als gemeinsame Online-Quelle konfiguriert.

Dokumentation: [Vercel Git-Deployments](https://vercel.com/docs/git) und
[Branch-Regeln](https://vercel.com/docs/project-configuration/git-configuration).

## Geheimnisse – nur in Vercel

Alles Geheime gehört **nur** in *Vercel → Projekt esphub → Settings →
Environment Variables*. Nicht ins Repo, nicht in den Chat, nicht aufs Board.

| Variable | Pflicht | Inhalt |
|---|---|---|
| `FIREBASE_DATABASE_URL` | ja | URL der Realtime Database, z. B. `https://esp32-services-default-rtdb.europe-west1.firebasedatabase.app` |
| `FIREBASE_SERVICE_ACCOUNT` | ja | kompletter Inhalt der Dienstkonto-JSON (siehe unten), Typ **Sensitive** |
| `ADMIN_TOKEN` | ja | dein Admin-Passwort, mindestens 8 Zeichen, lang und zufällig, Typ **Sensitive** |
| `HUB_TOKEN` | nein | zusätzliches Passwort für die Boards (`auth` in `hub_online.json`) |
| `GITHUB_REPO` / `GITHUB_BRANCH` | nein | Quelle des App-Stores (gesetzt: `Mailo037/ESP32-Programme` / `main`) |
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

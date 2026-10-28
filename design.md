# Design „Graphit“

Gilt für alle Oberflächen des ESP-Hub: Portal (`/`), Admin (`/admin`) und
Simulator (`/simulator`). Ziel: dunkel, ruhig, hochwertig, modern –
vergleichbar mit Vercel oder Linear. Farbe trägt Bedeutung (Status), nicht Deko.

Umsetzung:

- Portal und Admin: gemeinsames Stylesheet, Icons und Bedienelemente in
  [`lib/ui.js`](lib/ui.js) (`UI_KOPF`, `UI_SYMBOLE`, `UI_SKRIPT`).
- Simulator: eigene Kopie der Tokens und Bausteine in `simulator/index.html`
  bzw. `app.js` (Klasse `Auswahl`), weil er im Branch `simulator` separat
  entwickelt wird. Änderungen an den Tokens in beiden Stellen nachziehen.

## Grundregeln

1. **Keine Verläufe, kein Glow, keine Deko-Schatten.** Flächen sind flach,
   Tiefe entsteht nur durch Flächenstufen und 1-px-Linien. Schatten gibt es nur
   bei schwebenden Ebenen (Menü, Dialog, Meldung).
2. **Nur eigene Bedienelemente.** Kein natives `<select>`, kein `confirm()`/
   `prompt()`/`alert()`, kein sichtbarer nativer Datei-Knopf, keine nativen
   Checkboxen oder Zahlen-Pfeile. Stattdessen die Bausteine unten.
3. **Weiß ist der Akzent.** Die Hauptaktion pro Bereich ist ein weißer Button.
   Weitere Aktionen sind grau (`zweit`) oder ohne Rahmen (`geist`).
4. **Farbe nur für Status:** Grün = online/ok/aktiv, Gelb = Update/offen/
   Achtung, Rot = gesperrt/löschen/Fehler.
5. **Zahlen, IDs, Versionen, Größen in Mono** (`Geist Mono`), alles andere in
   `Geist`.
6. **Leere Zustände erklären**, was zu tun ist (gestrichelte Box mit Icon,
   Titel, Satz und ggf. Button) statt einer leeren Tabelle.

Ausnahme: Die Abbildung des espBoards im Simulator bleibt eine realistische
Darstellung der echten Platine (Grün, Bauteile, OLED in Cyan). Sie ist Inhalt,
keine Oberfläche.

## Farben (Tokens)

| Token | Wert | Verwendung |
|---|---|---|
| `--bg` | `#09090b` | Seitenhintergrund, Eingabefelder |
| `--fl` | `#111113` | Karten, Kacheln |
| `--fl2` | `#18181b` | Graue Buttons, Pillen, Menüs, aktiver Navigationspunkt |
| `--li` | `#232327` | Rahmen, Trennlinien |
| `--li2` | `#1c1c20` | Zeilenlinien in Tabellen |
| `--hov` | `#3a3a40` | Rahmen bei Hover/Fokus, gestrichelte Upload-Fläche |
| `--tx` | `#fafafa` | Haupttext, Hauptbutton |
| `--tx2` | `#d4d4d8` | Sekundärtext in Pillen, Werten |
| `--le` | `#8b8b94` | Beschreibungen, Tabellenköpfe, Icons |
| `--ak` / `--ak-tx` | `#fafafa` / `#09090b` | Hauptbutton und Logo-Marke |
| `--ring` | `rgba(250,250,250,.22)` | Fokusring (3 px) |
| `--gr` | `#4ade80` | Online, ok, aktiv |
| `--ge` | `#fbbf24` | Update verfügbar, offen, Hinweis |
| `--rt` | `#f87171` | Gesperrt, Löschen, Fehler |

Getönte Flächen für Status: `color-mix(in srgb, <Farbe> 10%, transparent)`
als Hintergrund, 22 % als Rahmen. `color-scheme: dark` ist gesetzt.

## Typografie

- Schrift: **Geist** (400/500/600/700), Mono: **Geist Mono** (400/500), über
  Google Fonts. Fallback `system-ui` bzw. `ui-monospace`.
- Grundtext 15 px / 1.55. Kleintext 13–14 px, Metadaten 12–12.5 px.
- Seitentitel `h1`: 28 px, 700, Laufweite −0.025em.
- Kartentitel `h2`: 17 px, 600. App-Namen 16 px, 600.
- Kennzahlen in Kacheln: 28 px, 600, `tabular-nums`.

## Abstände und Formen

- Radien: Karten 10 px, Dialog 12 px, Buttons/Felder 7 px, Menüeinträge 6 px,
  Pillen voll rund.
- Karten-Innenabstand 20 px, Abstand zwischen Karten 16 px.
- Inhaltsbreite max. 1240 px, Seitenränder `clamp(16px, 3.2vw, 44px)`.
- Raster für App-Karten: `repeat(auto-fill, minmax(240px, 1fr))`.

## Layout

- **Seitenleiste** (244 px, sticky): Logo-Marke (weißes Quadrat mit Chip-Icon),
  Navigation mit Icons, unten Zusatzlinks und Benutzerbereich.
  Aktiver Punkt: `--fl2`-Hintergrund und weißer Text.
- **Unter 860 px** wird die Seitenleiste zur oberen Leiste; die Navigation
  scrollt horizontal, Zusatzlinks werden ausgeblendet.
- Jeder Bereich beginnt mit einem **Kopf**: `h1`, ein erklärender Satz in
  `--le`, rechts optional Suche oder Hauptaktion.
- Simulator: obere Leiste statt Seitenleiste (die Boards brauchen die Breite),
  rechts eine Spalte mit Info-Karten (340 px), unter 1020 px darunter.

## Bausteine

| Baustein | Klasse | Hinweis |
|---|---|---|
| Karte | `.karte`, `.karte-kopf` | Kopf mit `h2`, Pillen, Aktion rechts (`.rechts`) |
| Kennzahl | `.kacheln` > `.kachel` | Label, große Zahl, Kleintext |
| Button | `.btn` (+ `.zweit`, `.geist`, `.gefahr`, `.gefahr-voll`, `.klein`, `.icon`) | Icons 16 px, Abstand 8 px |
| Pille | `.pill` (+ `.mono`, `.gr`, `.ge`, `.rt`, `.punkt`) | Versionen als `.pill.mono`, Status mit `.punkt` |
| Statuspunkt | `.status` (+ `.an`, `.rot`) | 7 px vor Board-Namen |
| Eingabefeld | `.feld` (+ `.mono`, `.zahl-feld`) | Zahlenfelder ohne Pfeile |
| Beschriftung | `.etikett` | Label über dem Feld, 13 px, `--le` |
| Suche | `.suche` | Icon, Feld, Tastenhinweis `/` |
| Tabelle | `.tabelle` > `table` | Kopf 12.5 px `--le`, Zeilen ohne Streifen, Aktionen rechts (`.aktionen`) |
| Werte-Raster | `.kv` | Kennwerte einer Sache (z. B. Board) in Mono |
| Rangliste | `.r1`–`.r3` + `.rang`, `.punkte` | Gold/Silber/Bronze nur als getönte Ziffernbox |
| Schritte | `ol.schritte` | Nummerierte Anleitung |
| Leerer Zustand | `.leer` | Gestrichelt, mittig |
| Hinweis | `.hinweis` | Gelb getönt, für Warnungen |
| Vorschau | `.bild` | Schwarze 2:1-Fläche wie das OLED; bekannte Spiele als Pixel-SVG, sonst Initialen |

### Eigene Bedienelemente (`UI` in `lib/ui.js`)

- **Auswahl-Menü** – `UI.auswahl(klasse, [[wert, text], …], wert, label)`
  liefert HTML. Der Wert steht in `data-wert`; bei Änderung feuert das Ereignis
  `wahl`. Liste schwebt `position: fixed` (wird in scrollenden Tabellen nicht
  abgeschnitten), klappt bei Platzmangel nach oben. Tastatur: Pfeile, Pos1/Ende,
  Enter, Esc, Tab.
- **Dialog** – `await UI.frage({ titel, text, ok, gefahr })` → `true/false`.
  Mit `eingabe: true` → Text oder `null`. Mit `code: "…"` → Code-Ansicht.
  Esc und Klick auf den Hintergrund brechen ab, Fokus bleibt im Dialog.
  Zerstörende Aktionen immer mit `gefahr: true` (roter Button) und einem
  Satz, was passiert.
- **Meldung** – `UI.meldung(text, fehler)`: unten rechts, Icon grün/rot,
  4 s (Fehler 6 s).
- **Datei-Feld** – `UI.datei(id, titel)`: gestrichelte Fläche mit Upload-Icon,
  Klick oder Ziehen; zeigt danach Dateiname und Größe. Das unsichtbare
  `<input type="file">` behält die `id`, `files[0]` funktioniert wie gewohnt.
- **Schalter** (Simulator) – `label.schalter` mit Checkbox
  (`appearance: none`), 34 × 20 px.

## Icons

Eigene Linien-Icons, 24er-Raster, Strichstärke 1.8, `currentColor`, als
`<symbol>` eingebettet: `<svg class="ic"><use href="#i-name"/></svg>`.
Standardgröße 18 px, in Buttons 16 px. Keine Emojis als Icons.

## Interaktion

- Übergänge 150 ms auf Farbe/Rahmen, keine Bewegungs-Effekte auf Karten.
- Hover: Rahmen `--hov` bzw. Hintergrund eine Stufe heller.
- Fokus: immer sichtbar, 3-px-Ring `--ring`.
- `prefers-reduced-motion` schaltet Übergänge und Animationen ab.
- Scrollbalken schmal, in `--li`.

## Texte

Deutsch, kurz, du-Form, Satzzeichen typografisch (–, …, „“). Buttons sagen,
was passiert („Entkoppeln“, „Release erstellen“), nicht „OK“.

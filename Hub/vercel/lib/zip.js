// Minimaler ZIP-Leser (ohne Pakete): liefert {name: Buffer} fuer die
// Dateien im Archiv. Unterstuetzt "gespeichert" und "deflate".
import zlib from "node:zlib";
import { Fehler } from "./basis.js";

export function zipLesen(buf, maxGesamt = 1024 * 1024) {
  // Ende des zentralen Verzeichnisses suchen
  let e = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { e = i; break; }
  }
  if (e < 0) throw new Fehler(400, "Keine gueltige ZIP-Datei");
  const anzahl = buf.readUInt16LE(e + 10);
  let p = buf.readUInt32LE(e + 16);
  const dateien = {};
  let gesamt = 0;
  for (let n = 0; n < anzahl && n < 200; n++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Fehler(400, "ZIP beschaedigt");
    const methode = buf.readUInt16LE(p + 10);
    const gepackt = buf.readUInt32LE(p + 20);
    const groesse = buf.readUInt32LE(p + 24);
    const lName = buf.readUInt16LE(p + 28), lExtra = buf.readUInt16LE(p + 30), lKomm = buf.readUInt16LE(p + 32);
    const lokal = buf.readUInt32LE(p + 42);
    const name = buf.slice(p + 46, p + 46 + lName).toString("utf8");
    p += 46 + lName + lExtra + lKomm;
    if (name.endsWith("/")) continue;
    gesamt += groesse;
    if (gesamt > maxGesamt) throw new Fehler(413, "ZIP-Inhalt zu gross");
    const start = lokal + 30 + buf.readUInt16LE(lokal + 26) + buf.readUInt16LE(lokal + 28);
    const roh = buf.slice(start, start + gepackt);
    if (methode === 0) dateien[name] = roh;
    else if (methode === 8) dateien[name] = zlib.inflateRawSync(roh, { maxOutputLength: maxGesamt });
    else throw new Fehler(400, "ZIP-Methode " + methode + " nicht unterstuetzt");
  }
  return dateien;
}

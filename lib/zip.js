import zlib from "node:zlib";
import { Fehler } from "./basis.js";

function crc32(data) {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}
export function sichererPfad(name) {
  return typeof name === "string" && name.length <= 160 && name.split("/").every((p) => /^[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(p) && p !== "." && p !== "..");
}
export function zipLesen(buf, maxGesamt = 512 * 1024) {
  const fail = () => { throw new Fehler(400, "ZIP beschaedigt oder nicht unterstuetzt"); };
  if (!Buffer.isBuffer(buf) || buf.length < 22 || buf.length > 1024 * 1024) fail();
  let e = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50 && i + 22 + buf.readUInt16LE(i + 20) === buf.length) { e = i; break; }
  }
  if (e < 0 || buf.readUInt16LE(e + 4) || buf.readUInt16LE(e + 6)) fail();
  const count = buf.readUInt16LE(e + 10), end = buf.readUInt32LE(e + 16) + buf.readUInt32LE(e + 12);
  if (!count || count > 128 || count !== buf.readUInt16LE(e + 8) || end !== e) fail();
  let p = buf.readUInt32LE(e + 16), total = 0;
  const files = Object.create(null), seen = new Set();
  for (let n = 0; n < count; n++) {
    if (p + 46 > end || buf.readUInt32LE(p) !== 0x02014b50) fail();
    const flags = buf.readUInt16LE(p + 8), method = buf.readUInt16LE(p + 10);
    const crc = buf.readUInt32LE(p + 16), packed = buf.readUInt32LE(p + 20), size = buf.readUInt32LE(p + 24);
    const nl = buf.readUInt16LE(p + 28), el = buf.readUInt16LE(p + 30), cl = buf.readUInt16LE(p + 32);
    const offset = buf.readUInt32LE(p + 42), type = (buf.readUInt32LE(p + 38) >>> 16) & 0xf000;
    if (p + 46 + nl + el + cl > end || flags & 1 || ![0, 8].includes(method) || (type && ![0x8000, 0x4000].includes(type))) fail();
    const name = buf.subarray(p + 46, p + 46 + nl).toString("utf8");
    p += 46 + nl + el + cl;
    const directory = name.endsWith("/"), clean = directory ? name.slice(0, -1) : name;
    if (!sichererPfad(clean) || seen.has(clean.toLowerCase())) fail();
    seen.add(clean.toLowerCase());
    if (offset + 30 > buf.readUInt32LE(e + 16) || buf.readUInt32LE(offset) !== 0x04034b50 || buf.readUInt16LE(offset + 8) !== method) fail();
    const localNameLen = buf.readUInt16LE(offset + 26), start = offset + 30 + localNameLen + buf.readUInt16LE(offset + 28);
    if (start + packed > buf.readUInt32LE(e + 16) || buf.subarray(offset + 30, offset + 30 + localNameLen).toString("utf8") !== name) fail();
    if (directory) { if (size) fail(); continue; }
    total += size;
    if (total > maxGesamt) throw new Fehler(413, "ZIP-Inhalt zu gross");
    let raw;
    try { raw = method === 0 ? buf.subarray(start, start + packed) : zlib.inflateRawSync(buf.subarray(start, start + packed), { maxOutputLength: Math.max(1, size) }); }
    catch { fail(); }
    if (raw.length !== size || crc32(raw) !== crc) fail();
    files[name] = raw;
  }
  if (p !== end || !Object.keys(files).length) fail();
  for (const name of Object.keys(files)) {
    const parts = name.split("/");
    while (parts.length > 1) {
      parts.pop();
      if (Object.keys(files).some((f) => f.toLowerCase() === parts.join("/").toLowerCase())) fail();
    }
  }
  return files;
}
export function projektDateien(buf, max) {
  const files = zipLesen(buf, max), names = Object.keys(files), prefix = names[0].split("/")[0] + "/";
  if (names.every((n) => n.startsWith(prefix))) return Object.fromEntries(names.map((n) => [n.slice(prefix.length), files[n]]));
  return files;
}

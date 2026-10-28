// Uses the actual server routes and production Firebase credentials, never prints secrets.
// All writes belong to a uniquely named diagnostic account/board and are cleaned up.
import crypto from "node:crypto";
import { DB, firebase, firebaseVergleichen } from "../lib/basis.js";
import handler from "../api/hub.js";
import { hubPruefsummen } from "../lib/store.js";

const expected = process.env.FIREBASE_PROJECT_ID || "esp32-services";
const id = crypto.randomBytes(6).toString("hex");
const user = "cloudcheck_" + id;
const board = "fe" + crypto.randomBytes(5).toString("hex");
const app = "CloudProbe_" + id;
const diagnostic = "esphub_admin/diagnose/" + id;
const password = crypto.randomBytes(24).toString("base64url");
let cookie = "", key = "";
const check = (condition, label) => { if (!condition) throw new Error(label); };
const pass = (label) => console.log("FIREBASE CHECK PASS: " + label);

function zip(files) {
  const local = [], central = []; let offset = 0;
  for (const [name, value] of Object.entries(files)) {
    const data = Buffer.from(value), n = Buffer.from(name); let crc = 0xffffffff;
    for (const b of data) { crc ^= b; for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1)); }
    crc = (crc ^ 0xffffffff) >>> 0;
    const l = Buffer.alloc(30); l.writeUInt32LE(0x04034b50); l.writeUInt16LE(20, 4); l.writeUInt32LE(crc, 14);
    l.writeUInt32LE(data.length, 18); l.writeUInt32LE(data.length, 22); l.writeUInt16LE(n.length, 26);
    const c = Buffer.alloc(46); c.writeUInt32LE(0x02014b50); c.writeUInt16LE(20, 6); c.writeUInt32LE(crc, 16);
    c.writeUInt32LE(data.length, 20); c.writeUInt32LE(data.length, 24); c.writeUInt16LE(n.length, 28); c.writeUInt32LE(offset, 42);
    local.push(l, n, data); central.push(c, n); offset += 30 + n.length + data.length;
  }
  const directory = Buffer.concat(central), end = Buffer.alloc(22), count = Object.keys(files).length;
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(count, 8); end.writeUInt16LE(count, 10);
  end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, directory, end]);
}

async function request(path, method = "GET", body, auth = "account", expectedStatus = 200) {
  const headers = {};
  if (auth === "account" && cookie) { headers.cookie = cookie; headers["x-hub-konto"] = "1"; }
  let response; const responseHeaders = {};
  const res = { setHeader(k, v) { responseHeaders[k.toLowerCase()] = v; }, end(v) { response = v; } };
  await handler({ url: path, method, body, headers }, res);
  check(res.statusCode === expectedStatus, method + " " + path.split("?")[0] + " failed (HTTP " + res.statusCode + ")");
  const data = response?.length ? JSON.parse(response.toString()) : null;
  return { data, headers: responseHeaders };
}
const boardUrl = (path) => "/" + path + "?board=" + board + (key ? "&t=" + key : "");

async function run() {
  const url = new URL(DB);
  check(url.protocol === "https:" && url.hostname.startsWith(expected + "-") && /\.(firebasedatabase\.app|firebaseio\.com)$/.test(url.hostname), "Database URL does not belong to " + expected);
  check(!url.search && url.pathname === "/", "Database URL must be the instance root");
  const account = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || "null");
  check(account?.project_id === expected, "Service account project does not match " + expected);
  check(process.env.ADMIN_TOKEN?.length >= 8, "ADMIN_TOKEN is required for signed portal sessions");
  pass("configuration for " + expected);

  // Do not touch a pre-existing path, even in the unlikely event of an ID collision.
  const paths = [diagnostic, `esphub_admin/konten/${user}`, `esphub_admin/privat/${user}`,
    `esphub_admin/boards/${board}`, `esphub_admin/kopplung/${board}`, `esphub_admin/auftraege/${board}`,
    `esphub_admin/belegt/${board}`, `esphub/${app}`];
  for (const path of paths) check(await firebase("GET", path) === null, "Diagnostic path already exists");
  let failure;
  try {
    await firebase("PUT", diagnostic, { count: 1, created: { ".sv": "timestamp" } });
    await firebase("PATCH", diagnostic, { count: { ".sv": { increment: 2 } } });
    const stored = await firebase("GET", diagnostic);
    check(stored.count === 3 && typeof stored.created === "number", "Database write/read or server values failed");
    await firebaseVergleichen(diagnostic + "/count", (old) => old + 1);
    check(await firebase("GET", diagnostic + "/count") === 4, "Conditional Firebase write failed");
    pass("OAuth, database read/write, timestamps, increments, ETag publication");

    await request("/portal/registrieren", "POST", { name: user, passwort: password }, "none");
    const login = await request("/portal/anmelden", "POST", { name: user, passwort: password }, "none");
    cookie = login.headers["set-cookie"].split(";")[0];
    const me = (await request("/portal/api/ich")).data;
    check(me.name === user, "Portal session does not identify the diagnostic account");
    pass("account registration, password authentication, signed session");

    const data = zip({ "main.py": "# HUB-NAME: " + app + "\n# HUB-VERSION: 1.0\nimport helper\n",
      "helper.py": "value=42\n", "assets/data.bin": Buffer.from([0, 128, 255]) });
    const upload = (await request("/portal/api/einreichen", "POST", { dateiname: "probe.zip", daten: data.toString("base64"), ziel: "privat" })).data;
    check(upload.id === app, "Private project ID mismatch");
    const catalog = (await request("/portal/simulator/apps")).data;
    const entry = catalog.apps.find((a) => a.id === app && a.privat);
    check(!!entry && !catalog.hinweis, "Private project is missing from online catalog");
    const bundle = (await request("/portal/simulator/apps/" + app + "?paket=" + entry.paket)).data;
    check(bundle.dateien.length === 3 && bundle.dateien.some((f) => f.name === "helper.py"), "Project modules were not persisted");
    const asset = bundle.dateien.find((f) => f.name === "assets/data.bin");
    check(Buffer.from(asset.daten, "base64").equals(Buffer.from([0, 128, 255])), "Binary project asset changed");
    await request("/portal/simulator/apps/" + app + "?paket=" + entry.paket, "GET", undefined, "none", 404);
    pass("ZIP upload, private online catalog, modules/assets, private access enforcement");

    const hashes = await hubPruefsummen("2.1.0");
    const info = { hub: "2.1.0", apps: {}, pruef: hashes, frei: 100000, ram: 100000 };
    key = (await request(boardUrl("melden"), "POST", info, "none")).data.schluessel;
    check(typeof key === "string" && key.length > 20, "Board registration failed");
    await request("/portal/api/koppeln", "POST", { board });
    const pairing = (await request(boardUrl("kopplung"), "GET", undefined, "none")).data;
    await request("/portal/api/koppeln/bestaetigen", "POST", { board, code: pairing.code });
    const own = (await request("/portal/api/ich")).data;
    check(!!own.boards[board], "Board was not paired to its account");
    await request("/portal/api/board/" + board + "/auftrag", "POST", { art: "install", app });
    const registered = (await request(boardUrl("melden"), "POST", info, "none")).data;
    check(registered.auftraege.install.includes(app), "Remote installation order was not persisted");
    pass("board registration, board key, account pairing, remote installation queue");

    const save = "esphub/" + app + "/boards/" + board + ".json";
    await request(boardUrl(save), "PATCH", { score: 42, level: 3 }, "none");
    const loaded = (await request(boardUrl(save), "GET", undefined, "none")).data;
    check(loaded.score === 42 && loaded.level === 3, "Board save data did not round-trip");
    await request(boardUrl("esphub/" + app + "/listen/highscore/" + board + ".json"), "PUT", { n: "CloudCheck", p: 42 }, "none");
    const scores = (await request(boardUrl("esphub/" + app + "/listen.json"), "GET", undefined, "none")).data;
    check(scores.highscore[board].p === 42, "Leaderboard did not round-trip");
    const limits = (await request(boardUrl("limits/" + board + "/" + app), "GET", undefined, "none")).data;
    check(limits.belegt_app > 0, "Board storage accounting was not persisted");
    await request(boardUrl("esphub/" + app + "/boards/000000000000.json"), "GET", undefined, "none", 403);
    pass("board saves, leaderboard, quota accounting, cross-board denial");
  } catch (error) { failure = error; }
  finally {
    // Only these random, preflight-checked diagnostic paths are ever removed.
    const cleanup = await Promise.allSettled(paths.map((path) => firebase("DELETE", path)));
    if (cleanup.some((r) => r.status === "rejected")) throw new Error("Diagnostic cleanup failed; IDs: " + id + ", " + board);
    for (const path of paths) check(await firebase("GET", path) === null, "Diagnostic cleanup incomplete");
    pass("all diagnostic data removed");
  }
  if (failure) throw failure;
  console.log("FIREBASE CHECK COMPLETE: " + expected);
}

await run();

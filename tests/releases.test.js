import test from "node:test";
import assert from "node:assert/strict";
import { deflateRawSync } from "node:zlib";
process.env.FIREBASE_DATABASE_URL = "https://firebase.test";
process.env.FIREBASE_SECRET = "test-only";
process.env.ADMIN_TOKEN = "test-only-admin-password";
const { zipLesen } = await import("../lib/zip.js");
const { appPaket, paketEintrag } = await import("../lib/pakete.js");
const { firmwarePaket, FIRMWARE_DATEIEN, hash } = await import("../lib/firmware.js");
const { adminApi } = await import("../lib/admin.js");
const { portalApi } = await import("../lib/konten.js");
const { sitzungCookie, sha256 } = await import("../lib/basis.js");
const { default: handler } = await import("../api/hub.js");
const { ADMIN_SEITE } = await import("../lib/admin-seite.js");
const { PORTAL_SEITE } = await import("../lib/portal-seite.js");
const { katalogVergessen } = await import("../lib/store.js");

function crc32(b) {
  let c = 0xffffffff;
  for (const byte of b) { c ^= byte; for (let j = 0; j < 8; j++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1)); }
  return (c ^ 0xffffffff) >>> 0;
}
function zip(entries, method = 8) {
  const locals = [], central = []; let offset = 0;
  for (const [name, data] of entries) {
    const raw = Buffer.from(data), n = Buffer.from(name), packed = method === 8 ? deflateRawSync(raw) : raw;
    const l = Buffer.alloc(30); l.writeUInt32LE(0x04034b50); l.writeUInt16LE(20, 4); l.writeUInt16LE(method, 8);
    l.writeUInt32LE(crc32(raw), 14); l.writeUInt32LE(packed.length, 18); l.writeUInt32LE(raw.length, 22); l.writeUInt16LE(n.length, 26);
    const c = Buffer.alloc(46); c.writeUInt32LE(0x02014b50); c.writeUInt16LE(20, 6); c.writeUInt16LE(method, 10);
    c.writeUInt32LE(crc32(raw), 16); c.writeUInt32LE(packed.length, 20); c.writeUInt32LE(raw.length, 24); c.writeUInt16LE(n.length, 28); c.writeUInt32LE(offset, 42);
    locals.push(l, n, packed); central.push(c, n); offset += l.length + n.length + packed.length;
  }
  const directory = Buffer.concat(central), end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}
const db = new Map();
let rejectConditional = false;
globalThis.fetch = async (input, options = {}) => {
  const url = new URL(input);
  if (url.hostname === "api.github.com") return Response.json({ tree: [] });
  assert.equal(url.hostname, "firebase.test", "Tests must never access live infrastructure");
  const key = url.pathname.slice(1, -5), method = options.method || "GET";
  if (method === "PUT" || method === "PATCH") {
    if (rejectConditional && options.headers?.["if-match"]) return new Response("null", { status: 412 });
    const value = JSON.parse(options.body);
    if (method === "PATCH") db.set(key, { ...(db.get(key) || {}), ...value }); else db.set(key, value);
    return Response.json(value);
  }
  return Response.json(db.get(key) ?? null, { headers: { etag: '"test-etag"' } });
};
const cookie = sitzungCookie("hubadmin", "admin", 1).split(";")[0];
const accountCookie = sitzungCookie("hubkonto", "alice", 1).split(";")[0];
const req = (body, headers = {}) => ({ body, headers: { cookie, "x-hub-admin": "1", ...headers } });
const firmwareFiles = () => FIRMWARE_DATEIEN.map((n) => [n, n === "hub_version.json" ? '{"version":"2.1.0"}' : "# " + n]);

test("ZIP limits, duplicate names, paths, truncation and CRC", () => {
  for (const method of [0, 8]) assert.equal(zipLesen(zip([["main.py", "print(1)"]], method))["main.py"].toString(), "print(1)");
  for (const name of ["../main.py", "/main.py", "C:/evil.py", "a/../../x.py", "a\\x.py"]) assert.throws(() => zipLesen(zip([[name, "x"]])), { code: 400 });
  assert.throws(() => zipLesen(zip([["main.py", "a"], ["MAIN.py", "b"]])), { code: 400 });
  assert.throws(() => zipLesen(zip([["main.py", "x".repeat(1000)]]), 100), { code: 413 });
  assert.throws(() => zipLesen(Buffer.from("bad")), { code: 400 });
  const broken = zip([["main.py", "hello"]], 0); broken[37] ^= 1;
  assert.throws(() => zipLesen(broken), { code: 400 });
});
test("ZIP retains modules/assets and removes only byte-identical shared drivers", async () => {
  const shared = Buffer.from("# shared display driver"), sensor = Buffer.from("# shared sensor driver");
  db.set("esphub_admin/firmware/aktiv", { dateien: [{ name: "ssd1306.py", sha256: hash(shared) }, { name: "bmp280.py", sha256: hash(sensor) }] });
  const p = await appPaket("game.zip", zip([["game/main.py", "# HUB-NAME: Game\nimport helper"], ["game/helper.py", "x=1"], ["game/images/pic.bin", Buffer.from([0,1,2])], ["game/ssd1306.py", shared], ["game/lib/bmp280.py", sensor]]));
  assert.deepEqual(p.dateien.map((f) => f.name), ["main.py", "helper.py", "images/pic.bin"]);
  assert.equal(p.geteilt.length, 2);
  const meta = paketEintrag({ eintrag: {} }, p);
  assert.equal(meta.eintrag.groesse, p.dateien.reduce((s, f) => s + Buffer.from(f.daten, "base64").length, 0));
  assert.equal(meta.dateien["images/pic.bin"].length, 3);
  const custom = await appPaket("game.zip", zip([["main.py", "x=1"], ["ssd1306.py", "# custom driver"]]));
  assert.equal(custom.geteilt.length, 0); assert.equal(custom.dateien.length, 2);
  await assert.rejects(appPaket("x.py", Buffer.from("x=1")), { code: 400 });
  await assert.rejects(appPaket("x.zip", zip([["main.py", "x=1"], ["boot.py", "bad"]])), { code: 400 });
  db.delete("esphub_admin/firmware/aktiv");
});
test("Firmware ZIP is complete and versioned; publishing is admin-only, monotonic and conditional", async () => {
  const archive = zip(firmwareFiles());
  assert.equal(firmwarePaket(archive, "2.1.0").dateien.length, 8);
  assert.throws(() => firmwarePaket(archive, "2.2.0"), { code: 400 });
  assert.throws(() => firmwarePaket(zip(firmwareFiles().slice(1)), "2.1.0"), { code: 400 });
  assert.throws(() => firmwarePaket(zip([...firmwareFiles(), ["boot.py", "evil"]]), "2.1.0"), { code: 400 });
  await assert.rejects(adminApi({ headers: {} }, "POST", "firmware"), { code: 401 });
  await assert.rejects(adminApi({ headers: { cookie } }, "POST", "firmware"), { code: 403 });
  await assert.rejects(adminApi(req({}, { cookie: accountCookie }), "POST", "firmware"), { code: 401 });
  const release = await adminApi(req({ dateiname: "fw.zip", daten: archive.toString("base64"), version: "2.1.0" }), "POST", "firmware");
  assert.equal(db.has("esphub_admin/firmware/aktiv"), false);
  rejectConditional = true;
  await assert.rejects(adminApi(req({}), "POST", `firmware/${release.id}/veroeffentlichen`), { code: 409 });
  rejectConditional = false;
  const active = await adminApi(req({}), "POST", `firmware/${release.id}/veroeffentlichen`);
  assert.equal(active.version, "2.1.0"); assert.equal(active.inhalt, undefined);
  await assert.rejects(adminApi(req({}), "POST", `firmware/${release.id}/veroeffentlichen`), { code: 409 });
  const changed = zip(firmwareFiles().map(([n, v]) => [n, n === "main.py" ? "# changed" : v]));
  await assert.rejects(adminApi(req({ dateiname: "fw.zip", daten: changed.toString("base64"), version: "2.1.0" }), "POST", "firmware"), { code: 409 });
});
test("Authenticated firmware download bypasses modification policy but never board authentication", async () => {
  const board = "abcdef123456", secret = "test-board-key";
  db.set(`esphub_admin/boards/${board}/schluessel`, sha256(secret));
  db.set(`esphub_admin/boards/${board}/veraendert`, ["main.py"]);
  db.set("esphub_admin/einstellungen/veraendert", "sperren");
  async function request(path) {
    let body; const headers = {};
    const res = { setHeader(k,v){headers[k]=v;}, end(value){body=value;} };
    await handler({ url: path, method: "GET", headers: {} }, res);
    return { status: res.statusCode, body, headers };
  }
  assert.equal((await request(`/firmware?board=${board}&t=wrong`)).status, 403);
  const active = db.get("esphub_admin/firmware/aktiv");
  const result = await request(`/firmware/${active.id}/main.py?board=${board}&t=${secret}`);
  assert.equal(result.status, 200); assert.equal(hash(result.body), active.dateien.find((f) => f.name === "main.py").sha256);
});
test("Private upload and review preserve the full ZIP project", async () => {
  const archive = zip([["main.py", "# HUB-NAME: TestGame\nprint(1)"], ["helper.py", "x=1"]]);
  const r = await portalApi(req({ dateiname: "game.zip", daten: archive.toString("base64"), ziel: "privat" }, { cookie: accountCookie, "x-hub-konto": "1" }), "POST", "einreichen");
  const saved = db.get(`esphub_admin/privat/alice/${r.id}`);
  assert.equal(saved.dateien.length, 2);
  await adminApi(req({ dateiname: "game.zip", daten: archive.toString("base64") }), "POST", "apps");
  assert.equal(db.get("esphub_admin/apps/TestGame").dateien.length, 2);
});
test("Project file downloads enforce private ownership and an immutable package ID", async () => {
  const board = "123456abcdef", secret = "private-test-key", other = "123456abcdee";
  db.set(`esphub_admin/boards/${board}/schluessel`, sha256(secret));
  db.set(`esphub_admin/boards/${other}/schluessel`, sha256(secret));
  db.set(`esphub_admin/boards/${board}/konto`, "alice");
  const record = db.get("esphub_admin/privat/alice/TestGame");
  db.set("esphub_admin/privat/alice", { TestGame: record });
  const app = paketEintrag({ eintrag: {} }, record);
  katalogVergessen();
  async function request(who, suffix) {
    let body; const res = { setHeader(){}, end(value){body=value;} };
    await handler({ url: `/apps/TestGame?board=${who}&t=${secret}${suffix}`, method: "GET", headers: {} }, res);
    return { status: res.statusCode, body };
  }
  const suffix = "&datei=helper.py&paket=" + app.eintrag.paket;
  const ok = await request(board, suffix);
  assert.equal(ok.status, 200); assert.equal(ok.body.toString(), "x=1");
  assert.equal((await request(board, "&datei=helper.py&paket=old")).status, 409);
  assert.equal((await request(board, "&datei=../main.py&paket=" + app.eintrag.paket)).status, 404);
  assert.equal((await request(other, suffix)).status, 404);
});
test("Admin and portal browser scripts compile", () => {
  for (const html of [ADMIN_SEITE, PORTAL_SEITE]) for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new Function(match[1]);
  assert.ok(ADMIN_SEITE.includes('id="fw-upload"')); assert.ok(PORTAL_SEITE.includes('accept=".zip,application/zip"'));
});
test("Simulator sees public apps and only the authenticated user's private projects", async () => {
  const publicRecord = { code: "print('public')", name: "Public", version: "1.0" };
  db.set("esphub_admin/apps", { Public: publicRecord });
  db.set("esphub_admin/privat/alice", { Secret: { code: "print('private')", name: "Secret", version: "1.0" } });
  katalogVergessen();
  async function request(suffix, headers = {}) {
    let body; const res = { setHeader(){}, end(value){body=value;} };
    await handler({url:'/portal/simulator/'+suffix, method:'GET', headers}, res);
    return {status:res.statusCode, body:JSON.parse(body.toString())};
  }
  const publicList = await request('apps');
  assert.equal(publicList.status,200);
  assert.deepEqual(publicList.body.apps.map((a)=>a.id),['Public']);
  const privateList = await request('apps',{cookie:accountCookie});
  assert.equal(privateList.body.apps.length,2);
  const secret = privateList.body.apps.find((a)=>a.id==='Secret');
  assert.equal((await request('apps/Secret?paket='+secret.sha256)).status,404);
  const content = await request('apps/Secret?paket='+secret.sha256,{cookie:accountCookie});
  assert.equal(content.status,200); assert.equal(content.body.dateien[0].name,'main.py');
  assert.equal((await request('apps/Public?paket=old')).status,409);
  const shared = await request('treiber');
  assert.equal(shared.status,200); assert.deepEqual(shared.body.dateien.map((f)=>f.name),['ssd1306.py','bmp280.py']);
  db.set('esphub_admin/konten/alice/gesperrt',true);
  assert.equal((await request('apps',{cookie:accountCookie})).status,403);
});

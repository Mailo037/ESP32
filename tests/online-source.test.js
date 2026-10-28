import test from "node:test";
import assert from "node:assert/strict";
import { onlineFiles, decodeFiles } from "../online-source.js";
const f = (name, data) => ({ name, daten: Buffer.from(data).toString("base64") });
test("Online projects preserve binary assets, modules and own drivers", () => {
  const app = { dateien: [f("main.py", "import helper"), f("helper.py", "x=1"), f("assets/a.bin", [0, 128, 255]), f("lib/ssd1306.py", "# own")] };
  const files = onlineFiles(app, { dateien: [f("ssd1306.py", "# shared"), f("bmp280.py", "# sensor")] });
  assert.deepEqual([...files["assets/a.bin"]], [0, 128, 255]);
  assert.ok(files["helper.py"]); assert.ok(files["bmp280.py"]);
  assert.equal(files["ssd1306.py"], undefined); assert.ok(files["lib/ssd1306.py"]);
});
test("Missing entry and unsafe paths fail before board execution", () => {
  assert.throws(() => onlineFiles({ dateien: [] }, { dateien: [] }), /main.py/);
  for (const name of ["../main.py", "/main.py", "a/../../x"]) assert.throws(() => decodeFiles([f(name, "x")]));
});

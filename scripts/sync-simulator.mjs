import { cp, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.resolve(process.argv[2] || path.join(root, "../esp-simulator"));
await mkdir(path.join(root, "simulator"), { recursive: true });
for (const name of ["index.html", "app.js", "online-source.js", "worker.js", "simcore.js", "coi-serviceworker.js", "README.md", "py", "mp"])
  await cp(path.join(source, name), path.join(root, "simulator", name), { recursive: true });
console.log("Simulator deployment copy refreshed from", source);

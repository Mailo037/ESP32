import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
if (process.env.VERCEL_ENV === "production") await import("./check-firebase.mjs");
// Publish only simulator assets; server sources and test files stay outside public/.
await mkdir("public/simulator", { recursive: true });
for (const name of ["index.html", "app.js", "online-source.js", "worker.js", "simcore.js", "coi-serviceworker.js", "py", "mp"])
  await cp("simulator/" + name, "public/simulator/" + name, { recursive: true });
const html = await readFile("public/simulator/index.html", "utf8");
await writeFile("public/simulator/index.html", html.replace("<head>", '<head>\n<base href="/simulator/">'));
console.log("Published simulator assets to public/simulator");

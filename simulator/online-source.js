export function decodeFiles(files) {
  const result = {};
  for (const file of files) {
    if (!file.name || file.name.split("/").some((p) => !/^[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(p) || p === "..")) throw new Error("Unsicherer Projektpfad");
    const raw = atob(file.daten);
    result[file.name] = Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }
  return result;
}
export function onlineFiles(bundle, shared) {
  const files = decodeFiles(bundle.dateien);
  if (!files["main.py"]) throw new Error("main.py fehlt im Online-Projekt");
  const drivers = decodeFiles(shared.dateien);
  for (const name of ["ssd1306.py", "bmp280.py"]) {
    if (!files[name] && !files["lib/" + name] && drivers[name]) files[name] = drivers[name];
  }
  return files;
}

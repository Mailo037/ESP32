/* Cross-Origin-Isolation fuer GitHub Pages.
   Die Boards brauchen SharedArrayBuffer + Atomics.wait. Browser erlauben das
   nur mit den Headern COOP/COEP - GitHub Pages sendet sie nicht. Dieser kleine
   Service Worker setzt sie nachtraeglich (gleiche Idee wie "coi-serviceworker"). */
if (typeof window === "undefined") {
  self.addEventListener("install", () => self.skipWaiting());
  self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
  self.addEventListener("fetch", (e) => {
    const r = e.request;
    if (r.cache === "only-if-cached" && r.mode !== "same-origin") return;
    e.respondWith(
      fetch(r).then((res) => {
        if (res.status === 0) return res;
        const h = new Headers(res.headers);
        h.set("Cross-Origin-Embedder-Policy", "require-corp");
        h.set("Cross-Origin-Opener-Policy", "same-origin");
        h.set("Cross-Origin-Resource-Policy", "cross-origin");
        return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
      })
    );
  });
} else {
  (() => {
    if (window.crossOriginIsolated || !window.isSecureContext || !navigator.serviceWorker) return;
    const schonNeu = sessionStorage.getItem("coi-neu") === "1";
    navigator.serviceWorker.register(document.currentScript.src).then((reg) => {
      const neuLaden = () => {
        if (schonNeu) return;              // keine Endlosschleife
        sessionStorage.setItem("coi-neu", "1");
        location.reload();
      };
      if (reg.active && !navigator.serviceWorker.controller) neuLaden();
      reg.addEventListener("updatefound", () => {
        reg.installing && reg.installing.addEventListener("statechange", (ev) => {
          if (ev.target.state === "activated") neuLaden();
        });
      });
      navigator.serviceWorker.ready.then(() => { if (!navigator.serviceWorker.controller) neuLaden(); });
    });
  })();
}

// Service Worker: hält die Programmoberfläche (HTML, Skripte, Stile) für den Start ohne Server bereit.
// Es werden ausdrücklich KEINE API-Antworten und keine Patientendaten zwischengespeichert; das übernimmt die Anwendung selbst
// verschlüsselt (siehe src/offline).
const CACHE = "physioflow-shell-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      const html = await (await fetch("/", { cache: "reload" })).text();
      const assets = [...html.matchAll(/(?:src|href)="(\/[^"]+\.(?:js|css|svg|png|webmanifest))"/g)].map((m) => m[1]);
      await cache.addAll([...new Set(["/", "/manifest.webmanifest", "/favicon.svg", ...assets])]); // addAll lehnt doppelte Adressen ab
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key);
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    // Seiten: zuerst Server (aktuelle Version), ohne Verbindung die gespeicherte Startseite
    event.respondWith(
      fetch(req).catch(async () => (await caches.match("/")) || new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } })),
    );
    return;
  }
  // Programmdateien: gespeicherte Kopie bevorzugen (Dateinamen enthalten eine Prüfsumme), sonst laden und merken
  event.respondWith(
    caches.match(req).then(
      (hit) =>
        hit ||
        fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            void caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        }),
    ),
  );
});

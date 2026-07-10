// Service Worker：缓存核心资源以支持离线启动
const CACHE = "echo-v2";
const ASSETS = ["/", "/index.html", "/css/style.css",
  "/js/api.js", "/js/ws.js", "/js/app.js",
  "/js/dashboard.js", "/js/settings.js", "/js/history.js", "/js/workshop.js",
  "/manifest.json", "/assets/icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  // API/WS 不缓存
  if (req.url.includes("/api/") || req.url.includes("/ws")) return;
  e.respondWith(
    caches.match(req).then((cached) =>
      cached || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => cached)
    )
  );
});

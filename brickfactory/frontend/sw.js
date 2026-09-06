/*
  Minimal service worker. Its main job here is simply to exist — browsers
  require an active service worker before they'll offer the "Install app"
  prompt at all. As a bonus it caches the app shell (HTML/CSS/JS, not API
  data) so the app still opens instantly on a flaky factory-floor signal.

  Bump CACHE_NAME whenever you deploy new frontend files so old clients
  pick up the update instead of serving a stale cached copy.
*/
const CACHE_NAME = "brickfactory-shell-security1";
const SHELL_FILES = [
  "login.html",
  "admin.html",
  "manager.html",
  "css/style.css",
  "js/api-security1.js",
  "js/recovery.js",
  "js/admin-security1.js",
  "js/manager-security1.js",
  "js/dashboard-security1.js",
  "manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Network-first for everything. API calls (/login, /admin/..., etc.) always
// hit the real server — this app deals in live business data, so it must
// never silently serve stale numbers. Only falls back to the cached shell
// file if the network is actually unreachable (e.g. brief signal drop).
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

/*
  Minimal service worker. Its main job here is simply to exist — browsers
  require an active service worker before they'll offer the "Install app"
  prompt at all. As a bonus it caches the app shell (HTML/CSS/JS, not API
  data) so the app still opens instantly on a flaky factory-floor signal.

  Bump CACHE_NAME whenever you deploy new frontend files so old clients
  pick up the update instead of serving a stale cached copy.
*/
const CACHE_NAME = "brickfactory-shell-loginmotion1";
const SHELL_FILES = [
  "login.html",
  "css/login.css?v=motion1",
  "js/login-motion.js?v=motion1",
  "js/customer-accounts.js?v=book2",
  "js/sale-customer-account.js?v=entrydates1",
  "js/production-settings.js?v=entrydates1",
  "js/notifications.js?v=push1",
  "js/date-display.js?v=activity2",
  "admin.html",
  "manager.html",
  "css/style.css",
  "js/api-security1.js?v=mobile1",
  "js/responsive-layout.js?v=mobile1",
  "js/recovery.js?v=transport1",
  "js/admin-security1.js",
  "js/manager-security1.js?v=transport1",
  "js/dashboard-security1.js",
  "manifest.json",
  "js/presence.js?v=presence2",
  "js/historical-entry.js?v=entry5",
  "js/stock-history.js?v=history1",
  "icons/nb-192-v2.png",
  "icons/nb-512-v2.png",
  "icons/nb-180-v2.png",
  "icons/nb-32-v2.png",
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
  if (new URL(event.request.url).pathname.startsWith("/presence/")) return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

self.addEventListener('push', event => {
  if (!event.data) return;
  let data;
  try { data = event.data.json(); } catch (_) { return; }
  event.waitUntil(self.registration.showNotification(data.title || 'NEO BRICKS', {
    body: data.body || '', icon: 'icons/nb-192-v2.png',
    tag: data.tag || 'neo-bricks', data: {url: data.url},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const route = event.notification.data?.url === '/admin.html' ? '/admin.html' : '/manager.html';
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const existing = windows.find(client => new URL(client.url).pathname === route);
    if (existing) return existing.focus();
    return self.clients.openWindow(route);
  })());
});

/* Coin Wire desk service worker — Web Push + offline shell. */

const SHELL_CACHE = "cw-desk-shell-v1";
const SHELL_URLS = [
  "/static/pico.min.css",
  "/static/desk.css",
  "/static/desk.js",
  "/static/icon-192.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "skip") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Never cache HTML/API/media — auth + freshness.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/media/") ||
    url.pathname === "/" ||
    url.pathname === "/today" ||
    url.pathname === "/history" ||
    url.pathname === "/stats" ||
    url.pathname === "/login" ||
    url.pathname === "/sw.js"
  ) {
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const copy = res.clone();
              caches.open(SHELL_CACHE).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});

self.addEventListener("push", (event) => {
  let data = { title: "Coin Wire", body: "Оновлення на desk", url: "/" };
  try {
    if (event.data) {
      data = { ...data, ...event.data.json() };
    }
  } catch (err) {
    try {
      data.body = event.data ? event.data.text() : data.body;
    } catch (e) {
      /* keep defaults */
    }
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Coin Wire", {
      body: data.body || "Є новий контент для перевірки",
      data: { url: data.url || "/" },
      badge: "/static/icon-192.png",
      icon: "/static/icon-192.png",
      tag: data.tag || "cw-desk-push",
      renotify: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(target);
      }
    })
  );
});

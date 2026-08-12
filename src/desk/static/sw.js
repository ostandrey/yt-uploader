/* Coin Wire desk service worker — Web Push + offline shell. */

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
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
      body: data.body || "",
      data: { url: data.url || "/" },
      badge: "/static/icon-192.png",
      icon: "/static/icon-192.png",
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

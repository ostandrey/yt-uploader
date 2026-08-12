(() => {
  const toastEl = document.getElementById("toast");
  const packEl = document.getElementById("pack-json");
  const fallback = document.getElementById("clip-fallback") || document.getElementById("clip-fallback-editorial");
  const dock = document.getElementById("dock");
  const dockBtn = document.getElementById("dock-btn");
  const pwaHint = document.getElementById("pwa-hint");
  const pack = packEl ? JSON.parse(packEl.textContent) : {};
  const ORDER = ["tiktok", "instagram"];
  const SHARE_LABEL = {
    tiktok: "Далі: Share TikTok",
    instagram: "Далі: Share Instagram",
  };
  let blobFile = null;
  let loading = null;

  const standalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  if (!standalone && pwaHint) pwaHint.hidden = false;

  function toast(msg, ok = true) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.toggle("bad", !ok);
    toastEl.classList.add("show");
    window.clearTimeout(toastEl._t);
    toastEl._t = window.setTimeout(() => toastEl.classList.remove("show"), 2400);
    if (navigator.vibrate) navigator.vibrate(ok ? 12 : 30);
  }

  function flashLabel(btn, text) {
    if (!btn) return;
    const original = btn.dataset.label || btn.textContent;
    btn.dataset.label = original;
    btn.textContent = text;
    window.setTimeout(() => {
      btn.textContent = btn.dataset.label;
    }, 1400);
  }

  async function copyText(text) {
    const value = (text || "").trim();
    if (!value) {
      toast("Немає тексту", false);
      return false;
    }
    if (fallback) fallback.value = value;
    try {
      await navigator.clipboard.writeText(value);
      toast("Опис у буфері");
      return true;
    } catch (err) {
      if (fallback) {
        fallback.classList.remove("visually-hidden");
        fallback.focus();
        fallback.select();
        try {
          const ok = document.execCommand("copy");
          fallback.classList.add("visually-hidden");
          if (ok) {
            toast("Опис у буфері");
            return true;
          }
        } catch (copyErr) {
          /* fall through */
        }
      }
      const box = document.querySelector("textarea[data-select]");
      if (box) {
        box.focus();
        box.select();
      }
      toast("Буфер заблокований — текст виділено", false);
      return false;
    }
  }

  function saveDataOn() {
    return Boolean(navigator.connection && navigator.connection.saveData);
  }

  async function videoFile() {
    if (blobFile) return blobFile;
    if (loading) return loading;
    loading = (async () => {
      const res = await fetch("/media/latest.mp4", { credentials: "same-origin" });
      if (!res.ok) throw new Error("video " + res.status);
      const blob = await res.blob();
      blobFile = new File([blob], "coinwire.mp4", { type: "video/mp4" });
      return blobFile;
    })();
    try {
      return await loading;
    } finally {
      loading = null;
    }
  }

  if (packEl && !saveDataOn()) videoFile().catch(() => {});

  function setBusy(on) {
    document.querySelectorAll("[data-share], #dock-btn").forEach((b) => {
      b.disabled = on;
    });
  }

  async function shareVideo(text, btn) {
    if (text) {
      await copyText(text);
    } else {
      toast("Немає опису — після Share встав свій текст", false);
    }
    setBusy(true);
    if (btn) flashLabel(btn, "Завантажую…");
    try {
      const file = await videoFile();
      const data = { title: pack.title || "Coin Wire", text, files: [file] };
      if (!navigator.share) {
        toast("Share немає. Збережи MP4 і встав опис");
        return;
      }
      if (navigator.canShare && !navigator.canShare({ files: [file] })) {
        toast("ОС не бере файл. Збережи MP4 — опис уже в буфері");
        return;
      }
      await navigator.share(data);
      toast("Перевір опис у додатку. Якщо пусто — встав");
    } catch (err) {
      if (err && err.name === "AbortError") return;
      toast("Share не вийшов. Опис у буфері — відкрий додаток", false);
    } finally {
      setBusy(false);
    }
  }

  async function shareText(text) {
    await copyText(text);
    try {
      if (navigator.share) {
        await navigator.share({ text, title: pack.title || "Coin Wire" });
      }
    } catch (err) {
      if (err && err.name === "AbortError") return;
    }
  }

  function captionFor(kind) {
    if (kind === "carousel") return pack.carousel_caption || "";
    return pack.ig_caption || "";
  }

  async function carouselFiles() {
    const names = pack.carousel || [];
    const files = [];
    for (const name of names) {
      const res = await fetch("/media/ig/" + encodeURIComponent(name), {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("slide " + name);
      const blob = await res.blob();
      files.push(new File([blob], name, { type: "image/jpeg" }));
    }
    return files;
  }

  async function shareCarousel(btn) {
    const caption = pack.carousel_caption || "";
    await copyText(caption);
    if (btn) {
      btn.disabled = true;
      flashLabel(btn, "Завантажую…");
    }
    try {
      const files = await carouselFiles();
      if (!files.length) {
        toast("Немає слайдів", false);
        return;
      }
      if (!navigator.share) {
        toast("Затисни кожен слайд → Зберегти зображення");
        return;
      }
      const payload = { files, title: pack.title || "Coin Wire", text: caption };
      if (navigator.canShare && !navigator.canShare({ files })) {
        toast("Затисни кожен слайд → Зберегти зображення");
        return;
      }
      await navigator.share(payload);
      toast("У Instagram: новий пост → кілька фото з галереї");
    } catch (err) {
      if (err && err.name === "AbortError") return;
      toast("Затисни кожен слайд → Зберегти зображення", false);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function nextPlatform() {
    return ORDER.find((name) => {
      const box = document.querySelector(`[data-mark="${name}"]`);
      return box && !box.checked;
    });
  }

  function syncDock() {
    if (!dock || !dockBtn) return;
    const next = nextPlatform();
    if (!next) {
      dock.hidden = true;
      return;
    }
    dock.hidden = false;
    dockBtn.textContent = SHARE_LABEL[next];
    dockBtn.dataset.kind = next;
  }

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const key = btn.getAttribute("data-copy");
      const ok = await copyText(pack[key] || "");
      if (ok) flashLabel(btn, "Скопійовано");
    });
  });
  document.querySelectorAll("[data-copy-text]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const index = btn.getAttribute("data-copy-text");
      const box = document.querySelector(`[data-editorial="${CSS.escape(index)}"]`);
      const ok = await copyText(box ? box.value : "");
      if (ok) flashLabel(btn, "Скопійовано");
    });
  });
  document.querySelectorAll("[data-editorial-done]").forEach((box) => {
    box.addEventListener("change", async () => {
      const id = box.getAttribute("data-editorial-done");
      const card = box.closest(".editorial-item");
      try {
        const res = await fetch("/api/editorial/done", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, done: box.checked }),
        });
        if (!res.ok) throw new Error("editorial mark");
        const data = await res.json();
        if (card) {
          card.classList.toggle("is-done", Boolean(data.done));
          card.classList.toggle("is-new", Boolean(data.is_new));
          const badge = card.querySelector(".editorial-badge");
          if (badge) {
            badge.className = `editorial-badge badge-${data.badge_kind || "old"}`;
            const age = data.age ? ` · ${data.age}` : "";
            badge.textContent = `${data.badge || ""}${age}`;
          }
        }
        toast(box.checked ? "Позначено як запощено" : "Повернуто в чергу");
      } catch (err) {
        box.checked = !box.checked;
        toast("Не вдалось зберегти позначку", false);
      }
    });
  });
  document.querySelectorAll("[data-share-carousel]").forEach((btn) => {
    btn.addEventListener("click", () => shareCarousel(btn));
  });
  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.getAttribute("data-share");
      shareVideo(captionFor(kind), btn);
    });
  });
  if (dockBtn) {
    dockBtn.addEventListener("click", () => {
      const kind = dockBtn.dataset.kind;
      if (!kind) return;
      shareVideo(captionFor(kind), dockBtn);
    });
  }
  document.querySelectorAll("textarea[data-select]").forEach((box) => {
    box.addEventListener("focus", () => box.select());
    box.addEventListener("click", () => box.select());
  });
  document.querySelectorAll("[data-mark]").forEach((box) => {
    box.addEventListener("change", async () => {
      const platform = box.getAttribute("data-mark");
      const id = pack.id;
      if (!id) return;
      try {
        const res = await fetch("/api/mark", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ id, platform, posted: box.checked }),
        });
        if (!res.ok) throw new Error("mark");
        const heading = box.closest(".platform")?.querySelector("h2");
        if (heading) {
          let tick = heading.querySelector(".done");
          if (box.checked && !tick) {
            tick = document.createElement("span");
            tick.className = "done";
            tick.textContent = "✓";
            heading.appendChild(tick);
          } else if (!box.checked && tick) {
            tick.remove();
          }
        }
        toast(box.checked ? "Позначено як запощено" : "Знято позначку");
        syncDock();
      } catch (err) {
        box.checked = !box.checked;
        toast("Не збереглось", false);
      }
    });
  });
  syncDock();

  function setupTabs() {
    const tabs = Array.from(document.querySelectorAll("[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-panel]"));
    if (!tabs.length || !panels.length) return;

    function show(tabId) {
      const allMode = tabId === "all";
      tabs.forEach((tab) => {
        tab.classList.toggle("is-active", tab.getAttribute("data-tab") === tabId);
      });
      panels.forEach((panel) => {
        const id = panel.getAttribute("data-panel");
        const visible = allMode
          ? id === "short" || id === "threads" || id === "telegram" || id === "tiktok" || id === "instagram"
          : id === tabId;
        panel.hidden = !visible;
      });
      try {
        localStorage.setItem("cw-desk-tab", tabId);
      } catch (err) {
        /* ignore */
      }
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => show(tab.getAttribute("data-tab")));
    });

    let initial = "all";
    try {
      initial = localStorage.getItem("cw-desk-tab") || "all";
    } catch (err) {
      initial = "all";
    }
    if (!tabs.some((tab) => tab.getAttribute("data-tab") === initial)) {
      initial = "all";
    }
    // Prefer first tab with a badge if landing on all and there are new items
    const hot = tabs.find((tab) => {
      const id = tab.getAttribute("data-tab");
      return id !== "all" && tab.querySelector(".desk-tab-badge");
    });
    if (initial === "all" && hot) {
      initial = hot.getAttribute("data-tab");
    }
    show(initial);
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const output = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
    return output;
  }

  function isIos() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  async function setupPush() {
    const btn = document.getElementById("push-btn");
    const hint = document.getElementById("push-hint");
    if (!btn) return;

    const supportsPush =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;

    if (!supportsPush) {
      btn.hidden = false;
      btn.textContent = "Push недоступний";
      btn.disabled = true;
      if (hint) {
        hint.hidden = false;
        hint.textContent = isIos()
          ? "На iOS потрібен iOS 16.4+ і ярлик з Safari → Share → На екран «Додому»."
          : "Цей браузер не підтримує Web Push.";
      }
      return;
    }

    btn.hidden = false;
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;

    if (isIos() && !isStandalone && hint) {
      hint.hidden = false;
      hint.textContent =
        "iPhone: відкрий desk з іконки на Home Screen, тоді натисни «Увімкнути сповіщення». З Safari-вкладки push не працює.";
    }

    async function refreshLabel() {
      try {
        const reg = await navigator.serviceWorker.ready;
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          btn.textContent = "Тест сповіщення";
          btn.dataset.mode = "test";
        } else if (isStandalone) {
          btn.textContent = "Увімкнути сповіщення";
          btn.dataset.mode = "subscribe";
        } else {
          btn.textContent = isIos() ? "Сповіщення (з Home)" : "Увімкнути сповіщення";
          btn.dataset.mode = "subscribe";
        }
      } catch (err) {
        btn.textContent = "Сповіщення";
        btn.dataset.mode = "subscribe";
      }
    }

    await refreshLabel();

    btn.addEventListener("click", async () => {
      try {
        if (isIos() && !isStandalone) {
          toast("Спочатку відкрий desk з Home Screen", false);
          return;
        }
        const perm = await Notification.requestPermission();
        if (perm !== "granted") {
          toast("Дозвіл на сповіщення відхилено", false);
          return;
        }
        const keyRes = await fetch("/api/push/public-key", { credentials: "same-origin" });
        if (!keyRes.ok) throw new Error("key");
        const { publicKey } = await keyRes.json();
        const reg = await navigator.serviceWorker.ready;
        // Always resubscribe with current VAPID — old keys die after redeploy without volume
        const old = await reg.pushManager.getSubscription();
        if (old) {
          try {
            await old.unsubscribe();
          } catch (err) {
            /* continue */
          }
        }
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
        const res = await fetch("/api/push/subscribe", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sub.toJSON()),
        });
        if (!res.ok) throw new Error("subscribe");
        const testRes = await fetch("/api/push/test", {
          method: "POST",
          credentials: "same-origin",
        });
        const testBody = testRes.ok ? await testRes.json() : {};
        await refreshLabel();
        if (testRes.ok && (testBody.sent || 0) > 0) {
          toast("Тест-пуш надіслано");
        } else {
          toast(
            "Підписка є, але сервер не зміг надіслати (перевір volume / pywebpush)",
            false
          );
        }
      } catch (err) {
        console.error(err);
        toast("Не вдалось увімкнути сповіщення", false);
      }
    });
  }

  setupTabs();
  setupPush();
})();


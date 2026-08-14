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

  const refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "…";
      const url = new URL(window.location.href);
      url.searchParams.set("r", String(Date.now()));
      window.location.replace(url.toString());
    });
  }

  const pageStamp = {
    editorial: document.querySelectorAll("[data-editorial-id]").length,
    newest: "",
  };
  function reloadDesk() {
    const url = new URL(window.location.href);
    url.searchParams.set("r", String(Date.now()));
    window.location.replace(url.toString());
  }
  async function checkStamp() {
    try {
      const res = await fetch("/api/desk/stamp", { credentials: "same-origin" });
      if (!res.ok) return;
      const stamp = await res.json();
      const more = Number(stamp.editorial || 0) > pageStamp.editorial;
      if (more) reloadDesk();
      pageStamp.newest = stamp.newest || pageStamp.newest;
    } catch (err) {
      /* ignore */
    }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkStamp();
  });
  window.setInterval(checkStamp, 20000);

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
      toast("Скопійовано");
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
            toast("Скопійовано");
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
    if (kind === "tiktok") return pack.tiktok_caption || pack.ig_caption || "";
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
          const list = card.parentElement;
          if (list && data.done) {
            list.appendChild(card);
          } else if (list && !data.done) {
            const firstDone = list.querySelector(".editorial-item.is-done");
            if (firstDone && firstDone !== card) list.insertBefore(card, firstDone);
          }
        }
        toast(box.checked ? "Позначено як запощено" : "Повернуто в чергу");
      } catch (err) {
        box.checked = !box.checked;
        toast("Не вдалось зберегти позначку", false);
      }
    });
  });
  async function saveAllSlides(btn) {
    if (btn) {
      btn.disabled = true;
      flashLabel(btn, "Зберігаю…");
    }
    try {
      const files = await carouselFiles();
      if (!files.length) {
        toast("Немає слайдів", false);
        return;
      }
      if (navigator.share && (!navigator.canShare || navigator.canShare({ files }))) {
        await navigator.share({ files, title: pack.title || "Coin Wire" });
        toast(`${files.length} слайди збережено`);
        return;
      }
      files.forEach((file) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(file);
        a.download = file.name;
        a.click();
        window.setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      });
      toast(`${files.length} слайди збережено`);
    } catch (err) {
      if (err && err.name === "AbortError") return;
      window.location.href = "/media/ig.zip";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  document.querySelectorAll("[data-save-carousel]").forEach((btn) => {
    btn.addEventListener("click", () => saveAllSlides(btn));
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

    function panelVisible(tabId, panel) {
      return panel.getAttribute("data-panel") === tabId;
    }

    function show(tabId) {
      tabs.forEach((tab) => {
        tab.classList.toggle("is-active", tab.getAttribute("data-tab") === tabId);
      });
      panels.forEach((panel) => {
        panel.hidden = !panelVisible(tabId, panel);
      });
      try {
        localStorage.setItem("cw-desk-tab", tabId);
      } catch (err) {
        /* ignore */
      }
      try {
        const url = new URL(window.location.href);
        url.searchParams.set("tab", tabId);
        window.history.replaceState({}, "", url);
      } catch (err) {
        /* ignore */
      }
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => show(tab.getAttribute("data-tab")));
    });

    const params = new URLSearchParams(window.location.search);
    let initial = params.get("tab") || "";
    if (!initial) {
      try {
        initial = localStorage.getItem("cw-desk-tab") || "threads";
      } catch (err) {
        initial = "threads";
      }
    }
    const hot = tabs.find((tab) => tab.querySelector(".desk-tab-badge"));
    if (!params.get("tab") && hot) {
      initial = hot.getAttribute("data-tab");
    } else if (!tabs.some((tab) => tab.getAttribute("data-tab") === initial)) {
      initial = tabs[0].getAttribute("data-tab");
    }
    show(initial);

    const itemId = params.get("item");
    if (itemId) {
      const card = document.querySelector(`[data-editorial-id="${CSS.escape(itemId)}"]`);
      if (card) {
        card.classList.add("is-focus");
        window.setTimeout(() => card.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
      }
    }
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
    const statusText = document.getElementById("push-status-text");
    const card = document.getElementById("push-card");
    if (!btn) return;

    const serverReady = !btn.disabled;
    const supportsPush =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;

    if (!serverReady) {
      if (statusText) {
        statusText.textContent =
          "Сервер ще не вміє слати push (немає VAPID / pywebpush). Після deploy кнопка стане активною.";
      }
      return;
    }

    if (!supportsPush) {
      btn.disabled = true;
      btn.textContent = "Push недоступний тут";
      if (statusText) {
        statusText.textContent = isIos()
          ? "На iOS потрібен 16.4+ і ярлик з Safari → Поділитися → На екран «Додому»."
          : "Цей браузер не підтримує Web Push. Спробуй Chrome / Edge.";
      }
      return;
    }

    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;

    if (isIos() && !isStandalone && hint) {
      hint.hidden = false;
      hint.textContent =
        "iPhone: відкрий desk з іконки Home Screen. З вкладки Safari система push не дає.";
    }

    async function ensureRegistration() {
      if (!("serviceWorker" in navigator)) throw new Error("no sw");
      let reg = await navigator.serviceWorker.getRegistration("/");
      if (!reg) {
        reg = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
          updateViaCache: "none",
        });
      }
      if (reg.waiting) await reg.waiting.postMessage({ type: "skip" });
      return reg;
    }

    async function syncSubscription() {
      if (isIos() && !isStandalone) return null;
      if (!window.Notification || Notification.permission !== "granted") return null;
      const keyRes = await fetch("/api/push/public-key", { credentials: "same-origin" });
      if (!keyRes.ok) throw new Error("key");
      const { publicKey } = await keyRes.json();
      const reg = await ensureRegistration();
      let sub = await reg.pushManager.getSubscription();
      const known = localStorage.getItem("cw-vapid-public") || "";
      if (!sub || known !== publicKey) {
        if (sub) {
          try {
            await sub.unsubscribe();
          } catch (err) {
            /* continue */
          }
        }
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
        localStorage.setItem("cw-vapid-public", publicKey);
      }
      const res = await fetch("/api/push/subscribe", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sub.toJSON()),
      });
      if (!res.ok) throw new Error("subscribe");
      return sub;
    }

    async function refreshLabel() {
      try {
        const reg = await ensureRegistration();
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          btn.textContent = "Надіслати тест";
          btn.dataset.mode = "test";
          if (card) card.classList.add("is-on");
          const dot = document.getElementById("push-dot");
          if (dot) {
            dot.hidden = false;
            dot.classList.add("is-on");
            dot.title = "Push: активний";
          }
          if (statusText) {
            statusText.textContent =
              `Увімкнено (standalone=${isStandalone}). Тест: спочатку local, потім server.`;
          }
        } else {
          btn.textContent = "Увімкнути сповіщення";
          btn.dataset.mode = "subscribe";
          if (card) card.classList.remove("is-on");
          const dot = document.getElementById("push-dot");
          if (dot) {
            dot.hidden = false;
            dot.classList.remove("is-on");
            dot.title = "Push: вимкнений";
          }
          if (statusText) {
            statusText.textContent =
              `Allow → підписка. standalone=${isStandalone}, permission=${Notification.permission}`;
          }
        }
      } catch (err) {
        btn.textContent = "Увімкнути сповіщення";
        btn.dataset.mode = "subscribe";
      }
    }

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const prev = btn.textContent;
      btn.textContent = "…";
      try {
        if (isIos() && !isStandalone) {
          toast("Спочатку відкрий desk з Home Screen", false);
          return;
        }
        if (!window.Notification) {
          toast("Цей браузер не вміє сповіщення", false);
          return;
        }
        toast("Запитую дозвіл у браузера…");
        const perm = await Notification.requestPermission();
        if (perm !== "granted") {
          toast("Дозвіл відхилено. Chrome → значок замка біля адреси → Notifications → Allow", false);
          if (statusText) {
            statusText.textContent =
              "Браузер заблокував сповіщення. Замок біля URL → Notifications → Allow, тоді знову Увімкнути.";
          }
          return;
        }
        try {
          new Notification("Coin Wire", {
            body: "Локальний тест браузера",
            icon: "/static/icon-192.png",
            tag: "coin-wire-local-test",
          });
        } catch (pageErr) {
          console.warn(pageErr);
        }
        toast("Локальний тест пішов. Підписую сервер…");
        const subWait = new Promise((_, reject) => {
          window.setTimeout(() => reject(new Error("підписка зависла >12с")), 12000);
        });
        await Promise.race([syncSubscription(), subWait]);
        const testRes = await fetch("/api/push/test", {
          method: "POST",
          credentials: "same-origin",
        });
        const testBody = testRes.ok ? await testRes.json() : {};
        await refreshLabel();
        const tg = testBody.telegram || {};
        const webOk = testRes.ok && (testBody.sent || 0) > 0;
        if (tg.sent) toast("Telegram ping надіслано");
        if (webOk) toast("Серверний push OK — має бути ще одне сповіщення");
        if (!webOk && !tg.sent) {
          const why = testBody.reason || tg.reason || "unknown";
          toast(`Серверний push ні (${why}). Локальний тест уже був.`, false);
        }
        if (statusText) {
          const webLine = webOk
            ? "Web Push: ок"
            : `Web Push: ні (${testBody.reason || "fail"})`;
          const tgLine = tg.sent ? "Telegram: ок" : `Telegram: ні (${tg.reason || "—"})`;
          statusText.textContent = `${webLine}. ${tgLine}. Підписок: ${(testBody.status && testBody.status.subs) || testBody.subs || 0}.`;
        }
      } catch (err) {
        console.error(err);
        toast("Не вдалось увімкнути сповіщення", false);
        if (statusText) statusText.textContent = String(err && err.message ? err.message : err);
      } finally {
        btn.disabled = false;
        if (btn.dataset.mode !== "test") btn.textContent = prev || "Увімкнути";
      }
    });

    refreshLabel()
      .then(async () => {
        if (Notification.permission === "granted" && !(isIos() && !isStandalone)) {
          try {
            await syncSubscription();
            await refreshLabel();
          } catch (syncErr) {
            console.warn(syncErr);
          }
        }
      })
      .catch((err) => console.warn(err));
  }

  setupTabs();
  setupPush();
})();


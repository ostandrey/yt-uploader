(() => {
  const toastEl = document.getElementById("toast");
  const packEl = document.getElementById("pack-json");
  const fallback =
    document.getElementById("clip-fallback") ||
    document.getElementById("clip-fallback-editorial");
  const dock = document.getElementById("dock");
  const dockBtn = document.getElementById("dock-btn");
  const pwaHint = document.getElementById("pwa-hint");
  const root = document.getElementById("desk-root");
  const pack = packEl ? JSON.parse(packEl.textContent) : {};
  const ORDER = ["tiktok", "instagram"];
  const SHARE_LABEL = {
    tiktok: "Далі: Поділитись TikTok",
    instagram: "Далі: Поділитись Instagram",
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
      hardReload();
    });
  }

  const pageStamp = {
    editorial: Number(root?.dataset.stampEditorial || document.querySelectorAll("[data-editorial-id]").length || 0),
    newest: root?.dataset.stampNewest || "",
    open: Number(root?.dataset.stampOpen || 0),
    pack: root?.dataset.stampPack || "",
  };

  function hardReload() {
    const url = new URL(window.location.href);
    url.searchParams.set("r", String(Date.now()));
    window.location.replace(url.toString());
  }

  function showUpdateBar(msg) {
    const bar = document.getElementById("desk-update-bar");
    const text = document.getElementById("desk-update-text");
    const btn = document.getElementById("desk-update-btn");
    if (!bar) {
      hardReload();
      return;
    }
    if (text) text.textContent = msg || "Є оновлення на desk";
    bar.hidden = false;
    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = "1";
      btn.addEventListener("click", hardReload);
    }
  }

  function applyStampUi(stamp) {
    pageStamp.editorial = Number(stamp.editorial || 0);
    pageStamp.newest = stamp.newest || pageStamp.newest;
    pageStamp.open = Number(stamp.open || 0);
    pageStamp.pack = stamp.pack_updated_at || pageStamp.pack;
    if (root) {
      root.dataset.stampEditorial = String(pageStamp.editorial);
      root.dataset.stampNewest = pageStamp.newest;
      root.dataset.stampOpen = String(pageStamp.open);
      root.dataset.stampPack = pageStamp.pack;
    }
    const openEl = document.getElementById("ops-open");
    if (openEl) openEl.textContent = String(pageStamp.open);
    if (stamp.next_check) {
      const next = document.getElementById("ops-next");
      const hint = document.getElementById("desk-hint");
      if (next) next.textContent = stamp.next_check;
      if (hint) hint.textContent = stamp.next_check;
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderEditorialCard(item) {
    const status = item.status || (item.done ? "desk_posted" : "desk_queued");
    const classes = ["editorial-item"];
    if (item.is_new) classes.push("is-new");
    if (item.done) classes.push("is-done");
    if (status === "desk_skipped") classes.push("is-skipped");
    const age = item.age ? ` · ${escapeHtml(item.age)}` : "";
    const skipBtn =
      status === "desk_skipped"
        ? ""
        : `<button type="button" class="btn-ghost btn-compact" data-editorial-skip="${escapeHtml(item.id)}">Пропустити</button>`;
    const reason = item.skip_reason
      ? `<p class="editorial-skip-reason">Пропуск: ${escapeHtml(item.skip_reason)}</p>`
      : "";
    const snip = item.snip
      ? `<p class="editorial-snip">${escapeHtml(item.snip)}</p>`
      : "";
    return `<article class="${classes.join(" ")}" data-editorial-id="${escapeHtml(item.id)}" data-status="${escapeHtml(status)}" id="item-${escapeHtml(item.id)}">
  <div class="editorial-meta">
    <p class="editorial-label">${escapeHtml(item.label)}</p>
    <span class="editorial-badge badge-${escapeHtml(item.badge_kind || "old")}">${escapeHtml(item.badge || "")}${age}</span>
  </div>
  ${snip}
  <textarea readonly data-select data-editorial="${escapeHtml(item.id)}">${escapeHtml(item.text)}</textarea>
  <div class="editorial-actions">
    <button type="button" class="btn-secondary" data-copy-text="${escapeHtml(item.id)}">Копіювати</button>
    ${skipBtn}
    <label class="mark editorial-mark">
      <input type="checkbox" data-editorial-done="${escapeHtml(item.id)}" ${item.done ? "checked" : ""}>
      <span>Вже запостив</span>
    </label>
  </div>
  ${reason}
</article>`;
  }

  function paintEditorialLists(items) {
    const byTab = { threads: [], telegram: [] };
    (items || []).forEach((item) => {
      const tab = item.tab === "telegram" ? "telegram" : "threads";
      byTab[tab].push(item);
    });
    ["threads", "telegram"].forEach((tab) => {
      const host = document.querySelector(`[data-editorial-list="${tab}"]`);
      const panel = document.querySelector(`[data-panel="${tab}"]`);
      if (!host) return;
      const list = byTab[tab];
      if (!list.length) {
        host.innerHTML = `<div class="empty-panel"><p class="empty-title">Немає постів для ${tab === "threads" ? "Threads" : "Telegram"}</p><p class="empty-body">Оновиться автоматично після job.</p></div>`;
        if (panel) panel.setAttribute("data-has-content", "0");
        return;
      }
      const step =
        tab === "threads"
          ? `<p class="step">Threads · Копіювати → встав · познач «Вже запостив»</p>`
          : `<p class="step">Telegram · Копіювати → встав у канал</p>`;
      host.innerHTML = step + list.map(renderEditorialCard).join("");
      if (panel) panel.setAttribute("data-has-content", "1");
    });
    refreshTabBadgesFromDom();
  }

  function refreshTabBadgesFromDom() {
    ["threads", "telegram"].forEach((tab) => {
      const n = document.querySelectorAll(
        `[data-panel="${tab}"] .editorial-item[data-status="desk_queued"]`
      ).length;
      const tabBtn = document.querySelector(`[data-tab="${tab}"]`);
      if (!tabBtn) return;
      let badge = tabBtn.querySelector(".desk-tab-badge");
      if (n > 0) {
        if (!badge) {
          badge = document.createElement("span");
          badge.className = "desk-tab-badge";
          tabBtn.appendChild(badge);
        }
        badge.textContent = String(n);
        tabBtn.setAttribute("data-count", String(n));
      } else if (badge) {
        badge.remove();
        tabBtn.removeAttribute("data-count");
      }
    });
  }

  async function softLoadEditorial() {
    const res = await fetch("/api/desk/editorial?scope=today", {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("editorial");
    const data = await res.json();
    paintEditorialLists(data.items || []);
    if (data.stamp) applyStampUi(data.stamp);
    toast("Desk оновлено");
  }

  async function checkStamp() {
    try {
      const res = await fetch("/api/desk/stamp", { credentials: "same-origin" });
      if (!res.ok) return;
      const stamp = await res.json();
      const packChanged =
        Boolean(stamp.pack_updated_at) &&
        stamp.pack_updated_at !== pageStamp.pack;
      const editorialChanged =
        stamp.newest !== pageStamp.newest ||
        Number(stamp.editorial || 0) !== pageStamp.editorial ||
        Number(stamp.open || 0) !== pageStamp.open;
      if (packChanged) {
        // Empty → first pack, or new short after previous one.
        if (!pageStamp.pack) {
          showUpdateBar("Short готовий — онови сторінку");
        } else {
          showUpdateBar("Новий Short готовий — онови сторінку");
        }
        return;
      }
      if (editorialChanged) {
        try {
          await softLoadEditorial();
        } catch (err) {
          showUpdateBar("Є нові тексти на desk");
        }
      } else {
        applyStampUi(stamp);
      }
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

  function applyCardStatus(card, data) {
    if (!card || !data) return;
    const status = data.status || (data.done ? "desk_posted" : "desk_queued");
    card.dataset.status = status;
    card.classList.toggle("is-done", Boolean(data.done));
    card.classList.toggle("is-new", Boolean(data.is_new));
    card.classList.toggle("is-skipped", status === "desk_skipped");
    const box = card.querySelector("[data-editorial-done]");
    if (box) box.checked = Boolean(data.done);
    const badge = card.querySelector(".editorial-badge");
    if (badge) {
      badge.className = `editorial-badge badge-${data.badge_kind || "old"}`;
      const age = data.age ? ` · ${data.age}` : "";
      badge.textContent = `${data.badge || ""}${age}`;
    }
    if (data.stamp) applyStampUi(data.stamp);
    refreshTabBadgesFromDom();
  }

  // Event delegation — works after soft editorial refresh.
  document.addEventListener("click", async (event) => {
    const copyBtn = event.target.closest("[data-copy]");
    if (copyBtn) {
      const key = copyBtn.getAttribute("data-copy");
      const ok = await copyText(pack[key] || "");
      if (ok) flashLabel(copyBtn, "Скопійовано");
      return;
    }
    const copyTextBtn = event.target.closest("[data-copy-text]");
    if (copyTextBtn) {
      const index = copyTextBtn.getAttribute("data-copy-text");
      const box = document.querySelector(`[data-editorial="${CSS.escape(index)}"]`);
      const ok = await copyText(box ? box.value : "");
      if (ok) flashLabel(copyTextBtn, "Скопійовано");
      return;
    }
    const skipBtn = event.target.closest("[data-editorial-skip]");
    if (skipBtn) {
      const id = skipBtn.getAttribute("data-editorial-skip");
      const card = skipBtn.closest(".editorial-item");
      try {
        const res = await fetch("/api/editorial/skip", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, reason: "operator" }),
        });
        if (!res.ok) throw new Error("skip");
        const data = await res.json();
        applyCardStatus(card, data);
        const list = card && card.parentElement;
        if (list && card) list.appendChild(card);
        skipBtn.remove();
        toast("Пропущено");
      } catch (err) {
        toast("Не вдалось пропустити", false);
      }
      return;
    }
    if (event.target.closest("[data-save-carousel]")) {
      saveAllSlides(event.target.closest("[data-save-carousel]"));
      return;
    }
    if (event.target.closest("[data-share-carousel]")) {
      shareCarousel(event.target.closest("[data-share-carousel]"));
      return;
    }
    const shareBtn = event.target.closest("[data-share]");
    if (shareBtn) {
      shareVideo(captionFor(shareBtn.getAttribute("data-share")), shareBtn);
    }
  });

  document.addEventListener("change", async (event) => {
    const box = event.target.closest("[data-editorial-done]");
    if (!box) return;
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
      applyCardStatus(card, data);
      const list = card && card.parentElement;
      if (list && data.done) {
        list.appendChild(card);
      } else if (list && !data.done) {
        const firstDone = list.querySelector(".editorial-item.is-done, .editorial-item.is-skipped");
        if (firstDone && firstDone !== card) list.insertBefore(card, firstDone);
      }
      toast(box.checked ? "Позначено як запощено" : "Повернуто в чергу");
    } catch (err) {
      box.checked = !box.checked;
      toast("Не вдалось зберегти позначку", false);
    }
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

  if (dockBtn) {
    dockBtn.addEventListener("click", () => {
      const kind = dockBtn.dataset.kind;
      if (!kind) return;
      shareVideo(captionFor(kind), dockBtn);
    });
  }
  document.addEventListener("focusin", (event) => {
    const box = event.target.closest("textarea[data-select]");
    if (box) box.select();
  });
  document.addEventListener("click", (event) => {
    const box = event.target.closest("textarea[data-select]");
    if (box) box.select();
  });
  function adjustTabBadge(tabId, delta) {
    const tab = document.querySelector(`[data-tab="${tabId}"]`);
    if (!tab || !delta) return;
    let badge = tab.querySelector(".desk-tab-badge");
    let n = badge ? parseInt(badge.textContent || "0", 10) || 0 : 0;
    n = Math.max(0, n + delta);
    if (n > 0) {
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "desk-tab-badge";
        tab.appendChild(badge);
      }
      badge.textContent = String(n);
      tab.setAttribute("data-count", String(n));
    } else if (badge) {
      badge.remove();
      tab.removeAttribute("data-count");
    }
  }

  document.querySelectorAll("[data-mark]").forEach((box) => {
    box.addEventListener("change", async () => {
      const platform = box.getAttribute("data-mark");
      const id = pack.id;
      if (!id) return;
      const wasChecked = !box.checked;
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
        const ytBadge = document.getElementById("yt-mark-badge");
        if (platform === "youtube" && ytBadge) {
          ytBadge.hidden = !box.checked;
        }
        if (pack.is_today) {
          const delta = box.checked ? -1 : 1;
          if (platform === "tiktok" || platform === "instagram") {
            adjustTabBadge(platform, delta);
            adjustTabBadge("short", delta);
          } else if (platform === "youtube") {
            adjustTabBadge("short", delta);
          }
        }
        if (pack.marks) pack.marks[platform] = box.checked;
        toast(box.checked ? "Позначено як запощено" : "Знято позначку");
        syncDock();
      } catch (err) {
        box.checked = wasChecked;
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
        const on = tab.getAttribute("data-tab") === tabId;
        tab.classList.toggle("is-active", on);
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
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

    const tablist = document.getElementById("desk-tabs");
    if (tablist) {
      tablist.addEventListener("keydown", (event) => {
        const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        const ids = tabs.map((t) => t.getAttribute("data-tab"));
        const current = tabs.findIndex((t) => t.classList.contains("is-active"));
        let next = current;
        if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
        if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = tabs.length - 1;
        show(ids[next]);
        tabs[next].focus();
      });
    }

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
    return (
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
    );
  }

  function collapsePushCard(on) {
    const card = document.getElementById("push-card");
    if (!card) return;
    card.classList.toggle("is-collapsed", on);
    card.hidden = on;
  }

  async function setupPush() {
    const btn = document.getElementById("push-btn");
    const hint = document.getElementById("push-hint");
    const statusText = document.getElementById("push-status-text");
    const card = document.getElementById("push-card");
    const dot = document.getElementById("push-dot");
    if (!btn) return;

    if (dot) {
      dot.addEventListener("click", () => {
        if (card) {
          card.hidden = false;
          card.classList.remove("is-collapsed");
          card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      });
    }

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
          if (dot) {
            dot.hidden = false;
            dot.classList.add("is-on");
            dot.title = "Push: активний (тап = показати картку)";
          }
          collapsePushCard(true);
          if (statusText) {
            statusText.textContent =
              `Увімкнено (standalone=${isStandalone}). Тест: спочатку local, потім server.`;
          }
        } else {
          collapsePushCard(false);
          btn.textContent = "Увімкнути сповіщення";
          btn.dataset.mode = "subscribe";
          if (card) card.classList.remove("is-on");
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

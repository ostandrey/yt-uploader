(() => {
  const toastEl = document.getElementById("toast");
  const packEl = document.getElementById("pack-json");
  const fallback = document.getElementById("clip-fallback");
  const dock = document.getElementById("dock");
  const dockBtn = document.getElementById("dock-btn");
  const pwaHint = document.getElementById("pwa-hint");
  if (!packEl) return;
  const pack = JSON.parse(packEl.textContent);
  const ORDER = ["tiktok", "instagram", "threads"];
  const SHARE_LABEL = {
    tiktok: "Далі: Share TikTok",
    instagram: "Далі: Share Instagram",
    threads: "Далі: Share Threads",
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

  if (!saveDataOn()) videoFile().catch(() => {});

  function setBusy(on) {
    document.querySelectorAll("[data-share], #dock-btn").forEach((b) => {
      b.disabled = on;
    });
  }

  async function shareVideo(text, btn) {
    await copyText(text);
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
    if (kind === "threads") return pack.threads_text || pack.title || "";
    return pack.ig_caption || pack.title || "";
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
    const caption = pack.carousel_caption || pack.title || "";
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
  document.querySelectorAll("[data-share-carousel]").forEach((btn) => {
    btn.addEventListener("click", () => shareCarousel(btn));
  });
  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.getAttribute("data-share");
      if (kind === "threads") shareText(captionFor(kind));
      else shareVideo(captionFor(kind), btn);
    });
  });
  if (dockBtn) {
    dockBtn.addEventListener("click", () => {
      const kind = dockBtn.dataset.kind;
      if (!kind) return;
      if (kind === "threads") shareText(captionFor(kind));
      else shareVideo(captionFor(kind), dockBtn);
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
})();

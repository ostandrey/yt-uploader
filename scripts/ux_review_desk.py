#!/usr/bin/env python3
"""Playwright UX review pass for Coin Wire desk vs EXPERIENCE Implementation delta."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "_bmad-output" / "planning-artifacts" / "ux-designs" / "ux-yt-uploader-2026-08-24" / ".working" / "playwright-review"
TMP = ROOT / "data" / "storage" / "_desk_ux_review_data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ["COIN_WIRE_DATA"] = str(TMP)
    os.environ["DESK_PASSWORD"] = "preview"
    os.environ["DESK_SECRET"] = "preview-secret-desk-ui"
    os.environ["DESK_HOST"] = "127.0.0.1"
    os.environ["DESK_PORT"] = "8766"

    for name in list(sys.modules):
        if name.startswith("src.desk") or name.startswith("src.paths"):
            del sys.modules[name]

    from src.desk.catalog import write_editorial_items

    now = datetime.now(timezone.utc).isoformat()
    write_editorial_items(
        [
            {
                "id": "ux-news",
                "kind": "новина",
                "label": "Threads — новина",
                "text": "XRP on track for biggest weekly gain since April as traders rotate into large caps.",
                "created_at": now,
                "done": False,
            },
            {
                "id": "ux-opinion",
                "kind": "opinion",
                "label": "Threads — opinion hook",
                "text": (
                    "Fidelity's plan to stake 100% of its Ethereum ETF signals "
                    "a shift in how traditional finance views crypto investments."
                ),
                "created_at": now,
                "done": False,
            },
            {
                "id": "ux-numbers",
                "kind": "зріз ринку",
                "label": "Threads — зріз ринку",
                "text": "Market snapshot, Aug 24: BTC +1.2%, ETH +2.4%, SOL flat.",
                "created_at": now,
                "done": True,
            },
        ]
    )

    import uvicorn
    from src.desk.app import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        time.sleep(0.1)
        if server.started:
            break

    from playwright.sync_api import sync_playwright

    findings: list[dict] = []
    shots: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto("http://127.0.0.1:8766/login", wait_until="networkidle")
        page.fill('input[name="password"]', "preview")
        page.click('button[type="submit"]')
        page.wait_for_url("**/")
        page.wait_for_timeout(600)

        path = OUT / "01_today_mobile.png"
        page.screenshot(path=str(path), full_page=True)
        shots.append(str(path))

        metrics = page.evaluate(
            """() => {
              const kind = document.querySelector('.editorial-item:not(.is-done) .editorial-kind');
              const kindStyle = kind ? getComputedStyle(kind) : null;
              const label = document.querySelector('.editorial-item:not(.is-done) .editorial-label');
              const labelStyle = label ? getComputedStyle(label) : null;
              const tabs = document.querySelector('.desk-tabs');
              const tabsStyle = tabs ? getComputedStyle(tabs) : null;
              const dock = document.getElementById('dock');
              const push = document.getElementById('push-card');
              const tip = Array.from(document.querySelectorAll('.desk-hint, .panel-hint, .step, [data-hint]'))
                .filter(el => el.offsetParent !== null)
                .map(el => (el.textContent || '').trim())
                .filter(Boolean);
              const wrap = document.querySelector('.page-wrap') || document.body;
              const wrapPad = getComputedStyle(wrap).paddingBottom;
              const cssDock = getComputedStyle(document.documentElement).getPropertyValue('--dock-clearance').trim();
              const headerBtns = Array.from(document.querySelectorAll('.header-actions button, .header-actions a'));
              const dot = document.getElementById('push-dot');
              const headerActions = document.querySelector('.header-actions');
              const headerWrap = headerActions ? getComputedStyle(headerActions).flexWrap : null;
              return {
                kindText: kind ? kind.textContent.trim() : null,
                kindFontWeight: kindStyle && kindStyle.fontWeight,
                kindFontSize: kindStyle && kindStyle.fontSize,
                kindColor: kindStyle && kindStyle.color,
                labelFontWeight: labelStyle && labelStyle.fontWeight,
                labelFontSize: labelStyle && labelStyle.fontSize,
                tabsOverflowX: tabsStyle && tabsStyle.overflowX,
                tabsFlexWrap: tabsStyle && tabsStyle.flexWrap,
                dockPresent: !!dock,
                dockHidden: dock ? !!dock.hidden : null,
                pushPresent: !!push,
                pushHidden: push ? !!push.hidden : null,
                pushCollapsed: push ? push.classList.contains('is-collapsed') || push.classList.contains('is-on') : null,
                pushClass: push ? push.className : null,
                tipTexts: tip.slice(0, 8),
                tipCount: tip.length,
                pageWrapPaddingBottom: wrapPad,
                cssDockClearance: cssDock,
                headerBtnCount: headerBtns.length,
                headerFlexWrap: headerWrap,
                openCards: document.querySelectorAll('.editorial-item:not(.is-done)').length,
                doneCards: document.querySelectorAll('.editorial-item.is-done').length,
                greenDotHidden: dot ? !!dot.hidden : null,
                greenDotOn: dot ? dot.classList.contains('is-on') : null,
              };
            }"""
        )

        # Probe empty Short tab
        if page.locator('[data-tab="short"]').count():
            page.click('[data-tab="short"]')
            page.wait_for_timeout(300)
            path2 = OUT / "02_short_empty_mobile.png"
            page.screenshot(path=str(path2), full_page=True)
            shots.append(str(path2))
            empty = page.evaluate(
                """() => {
                  const panel = document.getElementById('panel-short');
                  const text = (panel && panel.innerText) || '';
                  return { hasWhy: /немає|ще не|готовий|перевірк|Short/i.test(text), snippet: text.slice(0, 280) };
                }"""
            )
        else:
            empty = {"hasWhy": False, "snippet": "no short tab"}

        # Desktop viewport
        page.set_viewport_size({"width": 1100, "height": 900})
        if page.locator('[data-tab="threads"]').count():
            page.click('[data-tab="threads"]')
        page.wait_for_timeout(300)
        path3 = OUT / "03_today_desktop.png"
        page.screenshot(path=str(path3), full_page=True)
        shots.append(str(path3))

        browser.close()

    # Score against Implementation delta
    def add(req: str, status: str, note: str) -> None:
        findings.append({"requirement": req, "status": status, "note": note})

    weight = str(metrics.get("kindFontWeight") or "")
    if weight in {"700", "800", "900", "bold"}:
        add("Kind-chip scan hierarchy", "pass", f"weight={weight}, size={metrics.get('kindFontSize')}, text={metrics.get('kindText')}")
    elif weight in {"600", "500"}:
        add("Kind-chip scan hierarchy", "partial", f"weight={weight} (DESIGN target 700); size={metrics.get('kindFontSize')}; text={metrics.get('kindText')}")
    else:
        add("Kind-chip scan hierarchy", "fail", f"weight={weight}, color={metrics.get('kindColor')}")

    pad_raw = str(metrics.get("pageWrapPaddingBottom") or "0px").replace("px", "")
    try:
        pad_n = float(pad_raw)
    except ValueError:
        pad_n = 0.0
    css_dock = str(metrics.get("cssDockClearance") or "")
    add(
        "Dock clearance",
        "pass" if pad_n >= 64 or "72" in css_dock else "fail",
        f"pageWrapPaddingBottom={metrics.get('pageWrapPaddingBottom')} --dock-clearance={css_dock} dockPresent={metrics.get('dockPresent')} dockHidden={metrics.get('dockHidden')}",
    )

    add(
        "Push card collapse",
        "observe",
        f"pushHidden={metrics.get('pushHidden')} pushCollapsed={metrics.get('pushCollapsed')} greenDotHidden={metrics.get('greenDotHidden')} (needs subscribed session to fully verify)",
    )

    tip_n = int(metrics.get("tipCount") or 0)
    add(
        "Header tip dedupe",
        "pass" if tip_n <= 1 else ("partial" if tip_n == 2 else "fail"),
        f"desk-hint count={tip_n}; samples={metrics.get('tipTexts')}; headerBtns={metrics.get('headerBtnCount')}",
    )

    add(
        "Empty-state clarity",
        "pass" if empty.get("hasWhy") else "partial",
        f"short panel: {empty.get('snippet')!r}",
    )

    wrap = (metrics.get("tabsFlexWrap") or "").lower()
    ox = (metrics.get("tabsOverflowX") or "").lower()
    add(
        "Narrow tab scroll",
        "pass" if wrap == "nowrap" and ox in {"auto", "scroll", "overlay"} else "partial",
        f"flexWrap={metrics.get('tabsFlexWrap')} overflowX={metrics.get('tabsOverflowX')}",
    )

    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "viewport_primary": "390x844",
        "metrics": metrics,
        "empty_short": empty,
        "findings": findings,
        "shots": shots,
    }
    (OUT / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    server.should_exit = True
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

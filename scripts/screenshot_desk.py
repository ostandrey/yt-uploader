#!/usr/bin/env python3
"""Render desk with sample data and screenshot via Playwright."""

from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "storage" / "coin_wire" / "desk_preview"
TMP = ROOT / "data" / "storage" / "_desk_preview_data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ["COIN_WIRE_DATA"] = str(TMP)
    os.environ["DESK_PASSWORD"] = "preview"
    os.environ["DESK_SECRET"] = "preview-secret-desk-ui"
    os.environ["DESK_HOST"] = "127.0.0.1"
    os.environ["DESK_PORT"] = "8765"

    # Fresh modules with overridden data root
    for name in list(sys.modules):
        if name.startswith("src.desk") or name.startswith("src.paths"):
            del sys.modules[name]

    from src.desk import catalog
    from src.desk.catalog import write_editorial_items

    now = datetime.now(timezone.utc).isoformat()
    write_editorial_items(
        [
            {
                "id": "preview-opinion",
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
                "id": "preview-context",
                "kind": "context",
                "label": "Telegram — контекст",
                "text": (
                    "Context: Fidelity filed with the SEC to add staking to its "
                    "Ethereum ETF. The fund would keep most rewards and pay cash "
                    "distributions quarterly."
                ),
                "created_at": now,
                "done": False,
            },
        ]
    )

    import uvicorn
    from src.desk.app import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(40):
        time.sleep(0.1)
        if server.started:
            break

    from playwright.sync_api import sync_playwright

    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, name in ((390, "mobile"), (1100, "desktop")):
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.goto("http://127.0.0.1:8765/login", wait_until="networkidle")
            page.fill('input[name="password"]', "preview")
            page.click('button[type="submit"]')
            page.wait_for_url("**/")
            page.wait_for_timeout(500)
            path = OUT / f"desk_{name}.png"
            page.screenshot(path=str(path), full_page=True)
            shots.append(path)
            # Also capture All tab
            page.click('[data-tab="all"]')
            page.wait_for_timeout(300)
            path_all = OUT / f"desk_{name}_all.png"
            page.screenshot(path=str(path_all), full_page=True)
            shots.append(path_all)
        browser.close()

    server.should_exit = True
    print("Wrote:")
    for path in shots:
        print(f"  {path}")


if __name__ == "__main__":
    main()

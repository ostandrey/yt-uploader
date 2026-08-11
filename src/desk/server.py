"""Start the FastAPI desk in a daemon thread (same process as the worker)."""

from __future__ import annotations

import logging
import os
import threading

from src.desk import auth

log = logging.getLogger("coin_wire_desk")


def start_desk_thread() -> None:
    import uvicorn

    from src.desk.app import app

    # Always bind PORT so Railway healthchecks work even when the UI is off.
    port = int(os.getenv("DESK_PORT") or os.getenv("PORT") or "8080")
    host = os.getenv("DESK_HOST", "0.0.0.0")
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, name="coin-wire-desk", daemon=True)
    thread.start()
    if auth.enabled():
        log.info(
            "Desk UI on %s:%s session=%sh",
            host,
            port,
            os.getenv("DESK_SESSION_HOURS", "12"),
        )
    else:
        log.info("Desk /health on %s:%s (set DESK_PASSWORD to enable the PWA)", host, port)

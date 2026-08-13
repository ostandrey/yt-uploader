"""Coin Wire phone desk — FastAPI."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from src.content.copy_guard import display_title, safe_caption
from src.desk import auth, catalog, db, push

DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(DIR / "templates"))

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; media-src 'self'; script-src 'self'; "
        "style-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'"
    ),
}


class EditorialDoneBody(BaseModel):
    id: str
    done: bool = True


class MarkBody(BaseModel):
    id: int
    platform: str
    posted: bool = True


class PushSubBody(BaseModel):
    endpoint: str
    keys: dict = Field(default_factory=dict)
    expirationTime: int | float | None = None


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith("/static/desk.js") or request.url.path.startswith("/sw.js"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif request.url.path.startswith("/media/"):
            response.headers["Cache-Control"] = "private, no-store"
        else:
            response.headers.setdefault("Cache-Control", "no-store")
        return response


app = FastAPI(title="Coin Wire desk", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SecurityHeaders)
app.mount("/static", StaticFiles(directory=str(DIR / "static")), name="static")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _authed(request: Request) -> bool:
    token = request.cookies.get(auth.COOKIE_NAME, "")
    return bool(token and auth.verify_session(token))


def _cookie_args(request: Request, *, clear: bool = False) -> dict:
    secure = (request.headers.get("x-forwarded-proto") or "").lower() == "https"
    if os.getenv("DESK_SECURE", "").strip() in {"1", "true", "yes"}:
        secure = True
    if os.getenv("DESK_SECURE", "").strip() in {"0", "false", "no"}:
        secure = False
    if clear:
        return {
            "key": auth.COOKIE_NAME,
            "value": "",
            "max_age": 0,
            "httponly": True,
            "samesite": "lax",
            "path": "/",
            "secure": secure,
        }
    return {
        "key": auth.COOKIE_NAME,
        "value": auth.issue_session(),
        "max_age": auth.session_ttl_sec(),
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": secure,
    }


def _public_pack(pack: dict | None) -> dict | None:
    if not pack:
        return None
    marks = pack.get("marks") or {name: False for name in db.PLATFORMS}
    ig = safe_caption(str(pack.get("ig_caption") or ""))
    carousel = safe_caption(catalog.carousel_caption_text())
    return {
        "id": pack.get("id"),
        "title": display_title(str(pack.get("title") or "")),
        "ig_caption": ig,
        "youtube_url": pack.get("youtube_url") or "",
        "qa_score": pack.get("qa_score"),
        "bytes": pack.get("bytes") or 0,
        "updated_at": pack.get("updated_at") or "",
        "marks": {name: bool(marks.get(name)) for name in db.PLATFORMS},
        "carousel_caption": carousel,
        "carousel": [p.name for p in catalog.list_carousel_slides()],
        "caption_ready": bool(ig),
        "fallback": bool(pack.get("fallback")),
    }


@app.get("/sw.js")
def service_worker():
    path = DIR / "static" / "sw.js"
    return FileResponse(
        path,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/health")
def health():
    from src.paths import storage_status

    status = storage_status()
    return {
        "ok": True,
        "desk": auth.enabled(),
        "storage": status,
        "push": push.push_status(),
        "owner_telegram": bool(os.getenv("TELEGRAM_CHAT_ID", "").strip()),
    }


@app.get("/login")
def login_get(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "desk disabled")
    if _authed(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "logged_in": False, "error": "", "nav": "login"},
    )


@app.post("/login")
def login_post(request: Request, password: str = Form("")):
    if not auth.enabled():
        raise HTTPException(404, "desk disabled")
    ip = _client_ip(request)
    if not auth.login_allowed(ip):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "logged_in": False,
                "error": "Забагато спроб. Зачекай ~15 хв.",
                "nav": "login",
            },
            status_code=429,
        )
    if auth.check_password(password):
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(**_cookie_args(request))
        return response
    auth.record_fail(ip)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "logged_in": False,
            "error": "Невірний пароль.",
            "nav": "login",
        },
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    response = RedirectResponse("/login", status_code=303)
    response.set_cookie(**_cookie_args(request, clear=True))
    return response


@app.get("/")
@app.get("/today")
def today(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "desk disabled")
    if not _authed(request):
        return RedirectResponse("/login", status_code=303)
    pack = catalog.load_latest()
    public = _public_pack(pack)
    editorial = catalog.load_editorial_items(scope="today")
    from src.paths import storage_status

    storage = storage_status()
    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "request": request,
            "logged_in": True,
            "nav": "today",
            "pack": public,
            "has_thumb": bool(pack and catalog.resolve_thumb(pack)),
            "editorial": editorial,
            "tabs": catalog.desk_tabs(public, editorial),
            "push_enabled": push.push_configured(),
            "history_count": catalog.editorial_history_count(),
            "storage_warn": bool(storage.get("warn_no_volume")),
            "next_check": catalog.next_check_label(),
        },
    )


@app.get("/history")
def history(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "desk disabled")
    if not _authed(request):
        return RedirectResponse("/login", status_code=303)
    page = catalog.history_page()
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "request": request,
            "logged_in": True,
            "nav": "history",
            "groups": page["groups"],
            "count": page["count"],
            "storage_warn": page["storage_warn"],
        },
    )


@app.get("/stats")
def stats(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "desk disabled")
    if not _authed(request):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "request": request,
            "logged_in": True,
            "nav": "stats",
            "snap": catalog.stats_snapshot(),
        },
    )


@app.get("/media/latest.mp4")
def media_video(request: Request, dl: int = 0):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    pack = catalog.load_latest()
    if not pack:
        raise HTTPException(404, "no video")
    path = catalog.resolve_video_file(pack)
    if not path:
        raise HTTPException(404, "no video")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename="coinwire.mp4",
        content_disposition_type="attachment" if dl else "inline",
    )


@app.get("/media/ig/{name}")
def media_ig_slide(request: Request, name: str, dl: int = 0):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    path = catalog.resolve_carousel_slide(name)
    if not path:
        raise HTTPException(404, "no slide")
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=path.name,
        content_disposition_type="attachment" if dl else "inline",
    )


@app.get("/media/ig.zip")
def media_ig_zip(request: Request):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    slides = catalog.list_carousel_slides()
    if not slides:
        raise HTTPException(404, "no carousel")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for slide in slides:
            zf.write(slide, slide.name)
        caption = catalog.carousel_dir() / "caption.txt"
        if caption.is_file():
            zf.write(caption, "caption.txt")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=coinwire-ig.zip"},
    )


@app.get("/media/thumb.jpg")
def media_thumb(request: Request):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    pack = catalog.load_latest()
    if not pack:
        raise HTTPException(404, "no thumb")
    path = catalog.resolve_thumb(pack)
    if not path:
        raise HTTPException(404, "no thumb")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/desk/stamp")
def api_desk_stamp(request: Request):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    return JSONResponse(catalog.desk_stamp())


@app.get("/api/push/public-key")
def api_push_public_key(request: Request):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    key = push.public_key()
    if not key:
        raise HTTPException(503, "push unavailable")
    return JSONResponse({"publicKey": key})


@app.post("/api/push/subscribe")
def api_push_subscribe(request: Request, body: PushSubBody):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    if not push.push_configured():
        raise HTTPException(503, "push unavailable")
    payload = {
        "endpoint": body.endpoint,
        "keys": body.keys,
        "expirationTime": body.expirationTime,
    }
    try:
        push.save_subscription(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse({"ok": True, "sub": push.subscription_debug_info(payload)})


@app.post("/api/push/test")
def api_push_test(request: Request):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    if not push.push_configured():
        raise HTTPException(503, "push unavailable")
    result = push.notify_desk_push(
        "Coin Wire server test",
        "Web Push reached the device",
        url="/",
        tag="coin-wire-server-test",
    )
    telegram = {"sent": False, "reason": "skipped"}
    try:
        from src.publishers.telegram_publisher import TelegramPublisher

        tg = TelegramPublisher()
        if not tg.notify_chat_id:
            telegram["reason"] = "TELEGRAM_CHAT_ID missing on Railway"
        elif not tg.bot_token:
            telegram["reason"] = "TELEGRAM_BOT_TOKEN missing"
        else:
            tg.notify_owner("Desk test · Telegram ping живий")
            telegram = {"sent": True, "reason": "ok"}
    except Exception as exc:
        telegram = {"sent": False, "reason": str(exc)[:180]}
    result["telegram"] = telegram
    result["status"] = push.push_status()
    return JSONResponse(result)

@app.post("/api/editorial/done")
def api_editorial_done(request: Request, body: EditorialDoneBody):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    item = catalog.set_editorial_done(body.id, body.done)
    if not item:
        raise HTTPException(404, "unknown editorial item")
    return JSONResponse(
        {
            "ok": True,
            "id": item.get("id"),
            "done": bool(item.get("done")),
            "badge": item.get("badge"),
            "badge_kind": item.get("badge_kind"),
            "is_new": bool(item.get("is_new")),
            "age": item.get("age") or "",
        }
    )


@app.post("/api/mark")
def api_mark(request: Request, body: MarkBody):
    if not _authed(request):
        raise HTTPException(401, "auth required")
    try:
        pack = db.set_mark(body.id, body.platform, body.posted)
    except ValueError:
        raise HTTPException(400, "bad platform") from None
    if not pack:
        raise HTTPException(404, "unknown short")
    return JSONResponse({"ok": True, "marks": pack.get("marks")})

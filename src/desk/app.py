"""Coin Wire phone desk — FastAPI."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from src.desk import auth, catalog, db

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


class MarkBody(BaseModel):
    id: int
    platform: str
    posted: bool = True


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith("/static/"):
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
    return {
        "id": pack.get("id"),
        "title": pack.get("title") or "",
        "ig_caption": pack.get("ig_caption") or pack.get("title") or "",
        "threads_text": pack.get("threads_text") or pack.get("title") or "",
        "youtube_url": pack.get("youtube_url") or "",
        "qa_score": pack.get("qa_score"),
        "bytes": pack.get("bytes") or 0,
        "updated_at": pack.get("updated_at") or "",
        "marks": {name: bool(marks.get(name)) for name in db.PLATFORMS},
    }


@app.get("/health")
def health():
    return {"ok": True, "desk": auth.enabled()}


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
    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "request": request,
            "logged_in": True,
            "nav": "today",
            "pack": _public_pack(pack),
            "has_thumb": bool(pack and catalog.resolve_thumb(pack)),
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

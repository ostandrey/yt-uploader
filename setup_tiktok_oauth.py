#!/usr/bin/env python3
"""
One-time TikTok OAuth for Coin Wire (Login Kit → tokens).

Use Sandbox client key/secret from TikTok Dev Portal while recording the review demo.
Use Production keys after the app is approved.

1. Portal → Login Kit → Redirect URI:
   https://ostandrey.github.io/yt-uploader/oauth-callback.html
2. Put TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET in .env
3. Sandbox: add your TikTok account as a target user
4. Run:  python setup_tiktok_oauth.py
5. Browser → Authorize → copy code from callback page → paste here
6. Tokens saved to tokens/tiktok_token.json

Demo upload (after OAuth):
  python setup_tiktok_oauth.py --upload path/to/short.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

REDIRECT_URI = "https://ostandrey.github.io/yt-uploader/oauth-callback.html"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = "user.info.basic,video.upload"
TOKEN_FILE = ROOT / "tokens" / "tiktok_token.json"


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def build_auth_url(client_key: str) -> str:
    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": "coin_wire",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(client_key: str, client_secret: str, code: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    data = response.json()
    # TikTok sometimes nests under "data"
    if "access_token" not in data and isinstance(data.get("data"), dict):
        data = {**data, **data["data"]}
    if not data.get("access_token"):
        raise RuntimeError(f"Token exchange failed: {data}")
    return data


def save_tokens(access_token: str, refresh_token: str = "") -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token or _env("TIKTOK_REFRESH_TOKEN"),
    }
    TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_oauth() -> None:
    load_dotenv(ROOT / ".env")
    client_key = _env("TIKTOK_CLIENT_KEY")
    client_secret = _env("TIKTOK_CLIENT_SECRET")
    if not client_key or not client_secret:
        raise SystemExit(
            "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env "
            "(Sandbox keys for demo, Production after approval)."
        )

    url = build_auth_url(client_key)
    print("=" * 60)
    print("Coin Wire — TikTok OAuth (Login Kit)")
    print("=" * 60)
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes:       {SCOPES}")
    print("\nOpening browser… Log in with the Coin Wire TikTok account.")
    print("After Allow, copy the authorization code from the callback page.\n")
    print(url)
    webbrowser.open(url)

    code = input("\nPaste authorization code here: ").strip()
    if not code:
        raise SystemExit("No code pasted.")

    data = exchange_code(client_key, client_secret, code)
    access = data["access_token"]
    refresh = data.get("refresh_token", "")
    save_tokens(access, refresh)

    # Keep .env in sync for Railway / local pipelines that read env first
    print(f"\nSaved: {TOKEN_FILE}")
    print("Optional — also put in .env:")
    print(f"  TIKTOK_ACCESS_TOKEN={access[:20]}...")
    if refresh:
        print(f"  TIKTOK_REFRESH_TOKEN={refresh[:20]}...")
    print("\nNext demo upload:")
    print("  python setup_tiktok_oauth.py --upload data/storage/coin_wire/videos/<file>.mp4")


def run_upload(video_path: Path) -> None:
    load_dotenv(ROOT / ".env")
    from src.publishers.tiktok_publisher import TikTokPublisher

    # Unaudited / Sandbox often requires SELF_ONLY
    publisher = TikTokPublisher(privacy_level="SELF_ONLY")
    if not publisher.configured():
        raise SystemExit("No token. Run: python setup_tiktok_oauth.py")
    if not video_path.exists():
        raise SystemExit(f"File not found: {video_path}")

    print(f"Uploading (SELF_ONLY): {video_path}")
    result = publisher.upload_video(
        video_path,
        caption="Coin Wire sandbox demo #crypto #news",
    )
    print("Result:", json.dumps(result, indent=2)[:800])
    print("Check TikTok app → Activity / Inbox / Private posts (Sandbox).")


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok OAuth + demo upload")
    parser.add_argument(
        "--upload",
        type=Path,
        help="Upload an existing MP4 after OAuth (Sandbox demo)",
    )
    args = parser.parse_args()
    if args.upload:
        run_upload(args.upload)
    else:
        run_oauth()


if __name__ == "__main__":
    main()

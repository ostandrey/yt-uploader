# Coin Wire Uploader

Automated English crypto news channel: Telegram posts + YouTube Shorts.

## Quick start (local)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp env_example.txt .env   # fill in API keys
python setup_youtube_oauth.py
python coin_wire_worker.py
```

## Entry points

| Script | Purpose |
|--------|---------|
| `coin_wire_worker.py` | Production scheduler (Railway / always-on server) |
| `run_coin_wire_pipeline.py` | One Short: RSS → render → YouTube unlisted |
| `post_crypto_news.py` | One Telegram news post |
| `upload_coin_wire_short.py --publish ID` | Approve unlisted Short |
| `create_test_short.py` | Dev render smoke test |

## Config

`config/coin_wire.yaml` — schedule, news filters, voice, visual mode.

Default schedule (America/New_York):

| Job | Times |
|-----|-------|
| Telegram `@coinwirenews` | 08:00, 12:00, 17:00 |
| YouTube Shorts (unlisted) | 09:00, 18:00 |

## Railway deployment

### 1. Push repo

Connect this repo to Railway (GitHub → New Project → Deploy from repo).

### 2. Service settings

- **Builder:** Dockerfile (`railway.toml` already set)
- **Start command:** `python coin_wire_worker.py`
- **RAM:** 2 GB+ recommended (FFmpeg render)
- **No public HTTP** needed — this is a background worker

### 3. Environment variables

Copy from your local `.env` into Railway → Variables:

```
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
TELEGRAM_CHAT_ID
YOUTUBE_CRYPTO_CLIENT_ID
YOUTUBE_CRYPTO_CLIENT_SECRET
YOUTUBE_CRYPTO_TOKEN_JSON    # full JSON from tokens/coin_wire_token.json
PEXELS_API_KEY
PIXABAY_API_KEY
```

`YOUTUBE_CRYPTO_TOKEN_JSON` — paste the entire contents of `tokens/coin_wire_token.json` as one line. On first start the worker writes it to `/app/tokens/coin_wire_token.json` (refreshed tokens persist if volume is mounted).

### 4. Volumes (recommended)

| Mount path | Purpose |
|------------|---------|
| `/app/data` | Dedup state, renders, videos |
| `/app/tokens` | OAuth token after refresh |

Without volumes, dedup resets on redeploy and OAuth refresh may be lost.

### 5. Deploy

Railway builds the Docker image and starts `coin_wire_worker.py`. Check logs:

```
Coin Wire Worker — starting
Timezone: America/New_York
Telegram: 08:00, 12:00, 17:00
Shorts:   09:00, 18:00
Worker ready at ...
```

### 6. Manual test on Railway

Railway shell (or one-off run):

```bash
python post_crypto_news.py --count 1
python run_coin_wire_pipeline.py
```

You get a Telegram notification with the unlisted Short link. Publish from local:

```bash
python upload_coin_wire_short.py --publish VIDEO_ID
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `Missing env vars` | Add all required Railway variables |
| `YouTube token missing` | Set `YOUTUBE_CRYPTO_TOKEN_JSON` or mount `/app/tokens` |
| Render OOM | Increase Railway memory to 2–4 GB |
| OAuth expired | Re-run `setup_youtube_oauth.py` locally, update `YOUTUBE_CRYPTO_TOKEN_JSON` |

# Coin Wire Uploader

Automated English crypto news channel: Telegram posts + YouTube Shorts.

## Quick start

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

## Railway

- `Dockerfile` + `Procfile` included
- Mount volumes: `/app/data`, `/app/tokens`
- Set env vars from `env_example.txt`

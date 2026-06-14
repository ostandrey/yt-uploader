# Coin Wire — Strategy & Development Roadmap

> Crypto & market news in English. No trading signals. Fully automated pipeline.

Last updated: 2026-06-07

---

## 1. What We Are Building

| Product | Format | Language | Goal |
|---------|--------|----------|------|
| **Telegram** `@CoinWire` (TBD) | Text posts, 3–5/day | English | Fast audience, affiliate links, sponsors |
| **YouTube Shorts** | 1 video/day, 25–40 sec | English | Reach, brand, larger sponsors |
| **TikTok / Instagram** | Same 9:16 video | English | Free traffic (manual cross-post at first) |

**Not in scope:** trading signals, buy/sell advice. Personal project **Csurge** stays private forever.

---

## 2. Niche

**Crypto & Market News** — what happened, why the market moved, new projects, regulation, Fed/macro context.

Examples:
- "SEC approves new Bitcoin ETF — market reacts"
- "Fed holds rates at 5.25% — Bitcoin pumps 3%"
- "Solana DeFi protocol raises $50M"

### What is "Macro"?

Macro = economy-wide events that move all markets (including crypto):

| Event | Why it matters for crypto |
|-------|---------------------------|
| Fed interest rate decisions | BTC often moves same day |
| CPI / inflation data | Shapes rate expectations |
| Jobs report (NFP) | Risk-on / risk-off sentiment |
| SEC / EU regulation | Direct crypto impact |
| Geopolitics | Capital flows in/out of risk assets |

---

## 3. What Changes in the Codebase

### Remove / Deprecate

| Old | Problem | Replacement |
|-----|---------|-------------|
| MoviePy text clips (color rectangles) | No readable subtitles | FFmpeg + ASS subtitles |
| gTTS voiceover | Robotic, low retention | **edge-tts** (free, neural voices) |
| Images only (Pexels v1) | Static slideshow feel | **Pexels Video API** + images for numbers |
| Abacus.AI (primary) | Paid, overkill for news | OpenRouter free tier or RSS + template |
| Tech-only RSS feeds | Wrong niche | Crypto + macro RSS feeds |
| 3 channels (tech, crypto, memes) | Unfocused | **One channel: Coin Wire** |

### Add

| Component | File (planned) | Purpose |
|-----------|----------------|---------|
| FFmpeg Short renderer | `src/media/ffmpeg_short_renderer.py` | Professional 9:16 output |
| Stock video fetcher | `src/media/stock_video_fetcher.py` | Pexels/Pixabay video API |
| Edge TTS audio | `src/media/edge_tts_audio.py` | Voice + word-level subtitles |
| Crypto RSS feeds | `src/content/crypto_feeds.py` | CoinDesk, CoinTelegraph, The Block |
| Telegram publisher | `src/publishers/telegram_bot.py` | Auto-post news to TG |
| Channel config | `config/coin_wire.yaml` | Single source of truth |
| Test script | `create_test_short.py` | One-command demo Short |

---

## 4. Target Video Quality

Reference style: faceless news Shorts (New Money, Coin Bureau clips, market news channels).

| Element | Spec |
|---------|------|
| Resolution | 1080×1920 (9:16) |
| Duration | 25–40 seconds |
| Voice | `en-US-GuyNeural` or `en-US-ChristopherNeural` |
| Subtitles | Large, bottom-center, white + black outline (readable muted) |
| Visuals | 70% stock video, 30% text/numbers overlay |
| Motion | Ken Burns on images; native motion on stock video |
| Hook | First 2 sec: headline on screen |
| Music | Optional quiet background (YouTube Audio Library) |

---

## 5. News Sources

### Crypto RSS (free)

| Source | RSS |
|--------|-----|
| CoinDesk | `https://www.coindesk.com/arc/outboundfeeds/rss/` |
| CoinTelegraph | `https://cointelegraph.com/rss` |
| The Block | `https://www.theblock.co/rss.xml` |
| Decrypt | `https://decrypt.co/feed` |

### Macro / Finance

| Source | Notes |
|--------|-------|
| Federal Reserve | Official rate announcements |
| Reuters Markets | General finance |
| Investing.com calendar | CPI, NFP dates |

### Price Data (on-screen numbers)

| API | Cost |
|-----|------|
| CoinGecko | Free |
| CoinMarketCap | Limited free tier |

### Pipeline

```
RSS feeds → filter (crypto + macro) → LLM script (40 sec EN)
    ├→ Telegram post (text + link)
    └→ edge-tts → stock video → FFmpeg → YouTube Short
```

---

## 6. Tools & Budget

### Stack ($0/month to start)

| Tool | Cost | Role |
|------|------|------|
| edge-tts | $0 | Neural voiceover |
| FFmpeg (via imageio-ffmpeg) | $0 | Video assembly, subtitles |
| Pexels Video API | $0 | Stock footage |
| Pillow | $0 | Title cards, number overlays |
| OpenRouter free tier | $0 | Script generation |
| CoinGecko API | $0 | Live prices |

### Optional ($20 max)

| Tool | Cost | When |
|------|------|------|
| VPS (Hetzner) | ~$4/mo | When running 24/7 automation |
| OpenRouter credits | ~$5 | If free tier is not enough |
| ElevenLabs Starter | $5/mo | Only if edge-tts is not enough |

**Recommendation:** stay at $0 for the first 2–3 months.

---

## 7. Channel Branding

### Name candidates (pick one)

1. **Coin Wire** — news agency feel (recommended)
2. **Chain Brief** — short, memorable
3. **Crypto Pulse Daily** — good for YouTube search

### Bio template

```
Daily crypto & market news. No financial advice.
Bitcoin · Ethereum · DeFi · Fed · Regulation
```

Use the **same name** on Telegram, YouTube, TikTok, Instagram.

---

## 8. Monetization Path

| Stage | Timeline | Revenue |
|-------|----------|---------|
| Affiliate links (Binance, Bybit, TradingView) | 1–3 months | $20–100/mo |
| Telegram sponsor post | 3–6 months (500–2K subs) | $30–100/post |
| YouTube sponsor integration | 4–8 months | $200–1000/video |
| YouTube AdSense | 6+ months (1000 subs + 10M Shorts views) | Side income |

---

## 9. Telegram Growth

1. **YouTube Shorts → Telegram** — CTA at end of every video
2. **Consistent posting** — 3–5 posts/day, same times (UTC 8:00, 14:00, 20:00)
3. **Shareable format** — short posts with numbers ("BTC -4.2% after Fed decision")
4. **Reddit** — genuine comments on r/CryptoCurrency, r/Bitcoin (no spam)
5. **X/Twitter** — reply to crypto news, link in bio
6. **Telegram directories** — tgstat.com, combot.org
7. **Do not** buy followers or mix with Csurge signals

---

## 10. Development Phases

### Phase 1 — Proof of Quality (now)

- [x] Strategy document (this file)
- [ ] Test Short with FFmpeg + edge-tts + subtitles + stock video
- [ ] Verify output looks acceptable before automating further

### Phase 2 — Content Pipeline

- [ ] Crypto RSS integration
- [ ] Script generator (English, 40 sec, news tone)
- [ ] Pexels Video API in `stock_video_fetcher.py`
- [ ] Replace MoviePy renderer with FFmpeg renderer in main pipeline

### Phase 3 — Publishing

- [ ] Telegram bot auto-poster
- [ ] YouTube auto-upload (reuse existing OAuth)
- [ ] `config/coin_wire.yaml` as single channel config

### Phase 4 — Scale

- [ ] Daily scheduler (1 Short + 3 TG posts)
- [ ] TikTok / Instagram (manual → API when ready)
- [ ] Analytics dashboard (views, TG growth)
- [ ] Affiliate link rotation in descriptions

---

## 11. Additional Development Recommendations

### Architecture

1. **One renderer, one config** — delete duplicate templates (`simple_fallback`, `improved_video_templates` in scripts/ and src/) after FFmpeg renderer is stable.
2. **Separate `src/publishers/`** — YouTube, Telegram, TikTok as independent modules behind a common interface.
3. **Temp workspace** — render into `data/storage/coin_wire/renders/{timestamp}/` (audio, clips, subs, final.mp4) for debugging.
4. **Quality gate** — before upload, check: duration 20–45s, audio peak level, subtitle line count > 0, file size > 500KB.

### Content

5. **Deduplication** — hash RSS titles so the same news is not posted twice on TG and YouTube.
6. **Fact-first scripts** — prompt must forbid "buy/sell" language; include disclaimer in description.
7. **CoinGecko overlay** — show live % change for the main asset mentioned in the script.

### Ops

8. **FFmpeg via `imageio-ffmpeg`** — works on Windows without system FFmpeg install.
9. **Fail-safe uploads** — `auto_upload: false` until 10 videos pass manual review.
10. **Telegram first** — ship TG bot before perfecting video; text posts validate the niche faster.

### Legal / Trust

11. **Disclaimer** on every post: "Not financial advice."
12. **Never link Csurge** — separate products, separate audiences.
13. **Source attribution** — link to CoinDesk / original article in TG and YouTube description.

---

## 12. How to Run the Test Short

```bash
pip install edge-tts imageio-ffmpeg pillow python-dotenv requests
python create_test_short.py
```

Output: `data/storage/coin_wire/videos/test_short.mp4`

Optional: set `PEXELS_API_KEY` in `.env` for real stock footage. Without it, the script uses bundled fallback visuals.

---

## 13. Success Criteria

| Metric | Target (3 months) |
|--------|-------------------|
| TG subscribers | 500–2000 |
| YouTube Shorts | 60+ published |
| Avg views/Short | 1000+ |
| First affiliate signup | 1+ |
| Video production | Fully automated, < 5 min human review/day |

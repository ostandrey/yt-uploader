# Coin Wire — tech map, next actions, phone upload, AI review

**Updated:** 2026-08-11  
**Staff synthesis:** `_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md`  
**Quality plan:** `docs/shorts_quality_improvement_plan.md`

North star: people **watch to the end, like, and share**. Platforms are amplifiers. Unofficial cookie/browser posting is out of scope.

---

## 1. What we have today

| Layer | Stack | Notes |
|-------|--------|--------|
| News | RSS: CoinDesk, Cointelegraph, The Block, Decrypt + `news_filter` scores | Spine. Soft “analysis eyes…” still slips through. |
| Script | `short_script_generator` + optional `COPY_LLM_*` | Sprint 1: shorter CTA. 2A: dangling-clause truncate. |
| Voice | Edge TTS (`en-US-ChristopherNeural`, `+15%`) | Free, often flat. Facade for ElevenLabs later. |
| Montage | `ffmpeg_short_renderer` — hook, karaoke ASS, ticker, xfade, outro, SFX | Sprint 1 pacing landed; 2B cut density still soft (~2.0–2.5s clips). |
| B-roll | Live Pexels/Pixabay; optional local library + R2 sync | YOLO/CLIP offline on fill/index. AI-at-render parked. |
| YouTube | Official OAuth upload unlisted → auto-publish | Breaks without `/app/tokens` volume + valid `YOUTUBE_CRYPTO_TOKEN_JSON`. |
| Telegram | Channel posts + owner notify | Now also sends MP4 to owner chat for phone re-upload. |
| TikTok | Login Kit in code | **Production rejected: crypto / virtual currency.** |
| IG / Threads | Meta Graph | Threads failing `OAuthException 190` (dead token). IG needs public R2. |
| X | Not wired | Official API is paid/app review; no unofficial bot. |

Railway ops: mount **`/app/data`** and **`/app/tokens`**. Overlay disk wipes renders and OAuth on redeploy.

---

## 2. Improve vs rewrite vs pay

### Voice

| Action | What |
|--------|------|
| Keep | Edge as always-on fallback |
| Rewrite | Thin `generate_voiceover` facade (Edge now, API later) |
| Free try | Edge A/B (`Guy` / `Davis`); listen on HF Spaces (Kokoro, Chatterbox, Qwen3-TTS, IndexTTS) |
| Pay | ElevenLabs / Cartesia / OpenAI TTS after listen gate fails twice |
| Do not | Clone stacks, RVC, ZeroGPU Spaces inside Railway worker |

### News

| Action | What |
|--------|------|
| Keep | Current RSS + score |
| Rewrite | 2A hygiene + Sprint 4 angle weights (ETF/Fed/SEC/$ over filler) |
| Ideas only | worldmonitor-style macro/infra angles — not a drop-in fetcher |
| Pay | Optional `COPY_LLM` for sharper copy (cheap JSON) |

### Montage

| Action | What |
|--------|------|
| Keep / tune | Current ffmpeg (2B: 1.5–2.0s cuts, ASS, SFX) |
| AI review | `src/media/shorts_qa.py` — rules + optional vision LLM on keyframes |
| Do not rewrite | Remotion, Shotcut/Kdenlive CLI, fal.ai on every Short |
| Pay later | Generative B-roll / upscale — wrong cost for 2×/day news |

---

## 3. MCP Market — servers vs skills

[mcpmarket.com](https://mcpmarket.com/) is a **directory**. Listings are either official-API wrappers, paid SaaS, ffmpeg toys, or cookie bots.

### Skills (video editor search) — steal ideas, don’t swap the engine

| Skill-style listing | Use for Coin Wire |
|---------------------|-------------------|
| Automated Video Editor (ffmpeg + Remotion) | Timing/caption ideas only. We already ffmpeg. No Remotion rewrite. |
| Video Editor (ffmpeg) | Trim/merge — already in renderer. |
| AI Video Editor (fal.ai) | Optional later polish of a *winner* Short — not every render. Paid GPU. |
| VideoDB / semantic search | Future B-roll pick-time scoring (same job as CLIP). |
| Shot List Builder | Editorial packaging; Sophia/Reel already own script→beats. |
| Shotcut / Kdenlive CLI | Server NLE — heavier than ffmpeg for 25s news. Skip. |
| LazyReel / Maxmotion | Faceless-template makers — usually gameplay/quotes, lower bar. |

### Servers (user links)

| Listing | Verdict |
|---------|---------|
| elevenlabs-1 | Official TTS API wrapper. Pay for keys if Sprint 3. |
| world-monitor | News-angle inspiration. |
| threads-growth / meta-platform | Official Graph. We already call Threads/IG; fix **tokens**, not MCP. |
| video / video-editor / clip / pipeline / media-editor | Ideas. Keep our renderer. |
| tiktok / publisher | Official or SaaS. Our app is crypto-blocked. |
| tiktok-4 “no API keys” | Cookie/session bots. **Out of scope.** |

**Partner schedulers** (Plann/Buffer-class): legitimate *if* their audited app can post to *your* creator account. Not the same as scraping TikTok yourself.

---

## 4. Cross-post without sitting at a laptop

We will **not** store TikTok/IG/X passwords or session cookies for headless upload.

**Phone path (shipped):** after each render, the bot sends the **MP4 + copy-paste captions** to `TELEGRAM_CHAT_ID`.

**Desk PWA (FastAPI + SQLite, optional UI):** worker always binds `PORT` (`/health` for Railway). Set `DESK_PASSWORD` (+ `DESK_SECRET`, `DESK_PUBLIC_URL`) to unlock `/` — latest Short, Copy + Web Share into TikTok/IG/Threads, Save MP4, posted checkboxes, `/stats`. HMAC session cookie (Lax, HttpOnly). SQLite on the volume remembers marks. Not an auto-poster. Local: `python scripts/run_desk.py`. No Django, no Postgres.

From the phone:

1. Open Telegram (bot chat).  
2. Save video to Camera Roll / Files.  
3. Open TikTok / Instagram / Threads / X → upload from gallery.  
4. Paste the caption from the same Telegram message.

Limits: Telegram Bot API **~50 MB** per video. If larger, message still has filename; pull from Railway volume when at a computer.

Optional later: TG channel teaser with YouTube link when the Short is PUBLIC (owned loop, no extra apps).

---

## 5. AI Shorts feedback

`python scripts/review_short.py --video PATH` (also runs after pipeline render).

1. **Rules (always):** duration, sentence count, hook-stat present, B-roll mix, outro length, dangling script lines, chart-fallback share.  
2. **Vision (if `COPY_LLM_API_KEY` set):** 4 keyframes → news-desk rubric (first 2s hook, mid-cut energy, ending, subtitle collision).  
3. Report goes to console + owner Telegram.

This is **feedback**, not auto-rewrite of the MP4 in v1.

---

## 6. Ordered next actions

```text
[now]  Phone MP4 via Telegram + Shorts QA reviewer
[now]  Sprint 2A dangling-clause truncate
       Fix YouTube token + Railway volumes /app/tokens + /app/data
       Listen one Short; if VO still dead → ElevenLabs facade
Sprint 2B  cut density 1.5–2.0s + ASS/SFX
       Automate TG channel teaser on PUBLIC
Sprint 4   news angle scoring
       Refresh Threads token (official API)
TikTok     SocialPublisher via audited partner API (see docs/social_publisher_architecture.md); phone until vendor proven
(later)    B-roll AI-at-render (CLIP at pick), orchestrator epic
```

### Keys to refresh after tests

- `YOUTUBE_CRYPTO_TOKEN_JSON` + volume `/app/tokens`  
- `COPY_LLM_API_KEY` for vision QA + better copy  
- Later: `ELEVENLABS_API_KEY` (or Cartesia/OpenAI TTS)  
- Threads/IG: do not revive Graph; partner API after a paid/trial vendor works  
- R2 public URL only if the chosen vendor rejects multipart upload  

---

## 7. Anti-patterns

- Cookie/Playwright “I clicked it” upload to TikTok/IG/X.  
- Fighting TikTok Production review for a crypto app.  
- Buying ads before % viewed is healthy.  
- Dumping Remotion/fal.ai into the daily worker.  
- Treating MCP Market as a plug-in store for the Railway image.

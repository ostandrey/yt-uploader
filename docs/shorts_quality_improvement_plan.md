# Coin Wire — Shorts quality improvement plan

**Updated:** 2026-07-22  
**Goal:** Shorts that people **watch to the end, like, and share** — via tighter pacing, livelier voice, sharper montage, better stories, **and a clear distribution plan**. Product craft without a promo loop still dies at 1 sub.

Related: [`roadmap_broll_and_platforms.md`](roadmap_broll_and_platforms.md).  
**Canonical staff decisions:** [`../_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md`](../_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md) (Showrunner + 4 specialists, 2026-07-22).  
**Tech map / MCP skills / phone upload / AI QA:** [`tech_and_next_actions.md`](tech_and_next_actions.md) (2026-08-11).

---

## 0. Product reality (as of 2026-07-22)

| Signal | Note |
|--------|------|
| YouTube chain | Working after OAuth fix; auto-publish ON |
| Analytics | ~462 views / 28d; spike after mid-July (channel still tiny, 1 sub) |
| Main retention killers (user) | Long pauses, long ending, flat Edge voice, soft montage |
| Growth killers (user) | No deliberate promo loop — quality alone ≠ views/likes/shares |
| Ops debt | Mount Railway volumes `/app/data` + `/app/tokens` or redeploys wipe state |

**North star (engagement):** viewer finishes the Short more often than they swipe by ~3s → like / share / follow.  
**Craft bar for each Short:** 18–28s spoken, punchy CTA ≤1 line, brand outro ≤1.2s, cuts every ~1.5–2s, one clear hook-stat in first 2s.  
**Distribution bar:** every public Short has a **push path** (Telegram + ≥1 discovery surface), not only Studio upload.

---

## 1. Done — Sprint 1 (pacing / ending)

Landed in tree (local dry-run verified script shape):

| Change | Where |
|--------|--------|
| Sentence pause `0.4s` → `0.15s` | `src/media/edge_tts_audio.py` |
| Outro `3.0s` → `1.2s`, hook `2.5s` → `1.8s` | `src/media/ffmpeg_short_renderer.py` |
| Outro card no longer restates news (`sentences[-2]`) | `src/media/script_parser.py` → `Follow @coinwirenews` |
| Script cap ~5 lines; shorter CTA | `src/content/short_script_generator.py`, `copy_writer.py` |
| Voice rate `+15%`, target duration `20-30` | `config/coin_wire.yaml` |

**Next check:** local `--skip-upload` listen test → commit → Railway deploy.

Known leftover: summary lines can still truncate mid-phrase (`...inflows to.`) — fix in Sprint 2A.

---

## 2. Priority backlog

### Sprint 2A — Script hygiene (cheap, high leverage)

1. Fix truncated / dangling summary sentences (`_summary_sentences`).
2. Hard cap spoken length (~26s) — drop weakest body line before TTS.
3. Prefer money/flow/regulator facts over vague “markets watching…”.
4. A/B two Edge Neural voices (`Christopher` vs `Guy` / `Davis`) without new deps.

**Accept:** dry-run scripts never end mid-preposition; spoken ≤ ~28s.

### Sprint 2B — Montage / overlays (stay on ffmpeg)

Keep current stack (`ffmpeg_short_renderer`, karaoke ASS, ticker, hook-stat). Steal *ideas*, not frameworks.

| Idea | Implementation note |
|------|---------------------|
| Snappier cuts | Slightly shorter segment max; more cuts per Short |
| Stronger transitions | Keep short `xfade` (~0.15–0.2s); optional cut SFX already in `sfx_mixer` — tune levels |
| Hook | Stat chip + title in first 1.5–2s (already partially there) |
| Subs | Bigger karaoke, fewer words/line, safer lower-third (avoid UI collision with ticker) |
| End | Visual CTA only (done); optional 0.3s sting, no spoken essay |

**Do not** replace renderer with Remotion / MoviePy toy repos unless we deliberately rebuild.

### Sprint 3 — Voice upgrade (pick ONE path)

Constraint: Railway CPU worker, batch Shorts 2×/day — **not** a real-time voice agent.

| Path | Effort | Quality | Fit |
|------|--------|---------|-----|
| **A. Edge voice A/B** | Low | Medium | Ship this week |
| **B. Hosted API** (ElevenLabs / Cartesia / OpenAI TTS) | Medium | High | Best ROI for “alive” news VO |
| **C. HF open TTS on GPU box / Endpoint** | High | High | Only if we want brand voice + control cost |
| **D. Self-host clone in worker** | Very high | Variable | **Reject for now** |

Recommended sequence: **A → listen → B if still flat**. Evaluate **C** only after B cost/quality known.

### Sprint 4 — Story selection / “ideas for news”

| Source of ideas | Use |
|-----------------|-----|
| Current RSS (CoinDesk, CT, The Block, Decrypt) | Keep as spine |
| [worldmonitor](https://github.com/koala73/worldmonitor) | Inspiration for *angles* (macro, infra, geopolitics) — not a drop-in fetcher |
| Score weights | Boost ETF flows, SEC, Fed, billion-dollar moves; demote soft “analysis eyes…” filler |
| Dedup | Prefer freshest *distinct* story vs same BTC narrative twice/day |

Separate from B-roll AI-at-render debate (parked 1–2 weeks): when revisited, target **CLIP/YOLO on candidates at pick time**, not R2-as-goal.

### Sprint 5 — Platforms (lower priority)

TikTok token, Meta/Threads OAuth refresh, IG needs public R2 media host. Does not block Shorts quality.

---

## 3. Research triage — voice

### Skip / do not wire into Railway worker

| Project | Why |
|---------|-----|
| [CorentinJ/Real-Time-Voice-Cloning](https://github.com/CorentinJ/Real-Time-Voice-Cloning) | Author flags it as outdated; SaaS/newer OSS better |
| [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | TTS code removed from public repo after misuse concerns; ASR/realtime ≠ our VO path |
| [jamiepine/voicebox](https://github.com/jamiepine/voicebox) | Strong studio/clone UX; heavy local stack, not a batch Shorts plug-in |
| Most [voice-ai-agents](https://github.com/topics/voice-ai-agents) / [conversational-ai](https://github.com/topics/conversational-ai) | Telephony / chat agents — wrong product shape |

### Worth watching (HF + OSS)

| Asset | Role for Coin Wire |
|-------|--------------------|
| [Hugging Face Hub](https://huggingface.co/) + [org](https://github.com/huggingface) | Model catalog, Inference Providers, Spaces demos — **evaluation surface**, not “install transformers in worker” |
| [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) ([kokoro](https://github.com/hexgrad/kokoro)) | Small Apache TTS; good **local/GPU-box** candidate; lighter than clone stacks |
| [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox) (+ turbo) | Strong open TTS / cloning; MIT; needs GPU for comfort — candidate for dedicated voice job, not default Railway CPU |
| HF Transformers TTS docs ([SpeechT5, etc.](https://huggingface.co/docs/transformers/en/tasks/text-to-speech)) | Fine-tune / research path — overkill for v1 news VO |
| CosyVoice / Qwen3-TTS (community benchmarks) | Pre-produced narration quality — evaluate via Spaces/samples before any port |

**Hugging Face takeaway for us:**

1. Use HF to **listen and compare** (Spaces / samples), not to dump `transformers`+GPU into the current Docker worker.
2. If open TTS: run **Kokoro or Chatterbox** on a GPU machine or [HF Inference Endpoint / Provider](https://huggingface.co/), write WAV → existing ffmpeg mux.
3. Keep Edge (or paid API) as fallback so Shorts never block on model download.

### HF Spaces catalogs (listen / compare — 2026-07-22)

Use these as **demo shopping**, not as deploy targets. Staff rule: evaluate in browser → if a voice wins the listen gate twice over Edge, then Endpoint/API — never bake ZeroGPU Spaces into Railway.

| Category | Link | Coin Wire use |
|----------|------|----------------|
| **Speech Synthesis** | [spaces?category=speech-synthesis](https://huggingface.co/spaces?category=speech-synthesis) | **Primary listen board.** Priority demos: [Kokoro TTS](https://huggingface.co/spaces/hexgrad/Kokoro-TTS), [Chatterbox TTS](https://huggingface.co/spaces/ResembleAI/Chatterbox), [Qwen3-TTS](https://huggingface.co/spaces/Qwen/Qwen3-TTS-Demo), [IndexTTS 2](https://huggingface.co/spaces/IndexTeam/IndexTTS), [Supertonic 3](https://huggingface.co/spaces/Supertone/Supertonic), Edge TTS Space (baseline vs our Edge). |
| **Voice Cloning** | [spaces?category=voice-cloning](https://huggingface.co/spaces?category=voice-cloning) | **Optional brand voice later.** Prefer zero-shot TTS Spaces that output clean narration (NeuTTS, MegaTTS clones) over **RVC / singing / Genshin** conversion. Skip XTTS-era demos if unstable. Clone only after we have a legal reference VO and Sprint 3 API path. |
| **Video Generation** | [spaces?category=video-generation](https://huggingface.co/spaces?category=video-generation) | **Not Shorts B-roll V1.** Wan2.2 / LTX I2V are GPU-heavy generative clips — wrong latency/cost for 2×/day news. Maybe later: one branded hook bumper. Keep stock + library for body. |
| **Visual QA** | [spaces?category=visual-qa](https://huggingface.co/spaces?category=visual-qa) | **Ideas for B-roll AI-at-render revisit** (ask “is this a chart/screen/crowd?”). Complements YOLO/CLIP; do not replace Sprint 2 pacing. |
| **Data Visualization** | [spaces?category=data-visualization](https://huggingface.co/spaces?category=data-visualization) | **Almost none for render.** Leaderboards / VoiceEQ benchmarks are for *choosing* models ([Real World VoiceEQ](https://huggingface.co/spaces?category=data-visualization)), not for on-screen charts in Shorts — we already have ticker + chart_fallback. |

**Listen protocol (Sprint 3 prep):** take one Coin Wire script (4 lines + CTA) → paste into Kokoro, Chatterbox, Qwen3-TTS, IndexTTS → score news-desk energy 1–5 → only then open paid API or Endpoint discussion.

---

## 4. Research triage — montage / Shorts generators

| Project | Steal | Don’t |
|---------|-------|-------|
| [gyoridavid/short-video-maker](https://github.com/gyoridavid/short-video-maker) | Remotion timing/captions ideas, MCP packaging | Full Remotion rewrite |
| [Binary-Bytes/Auto-YouTube-Shorts-Maker](https://github.com/Binary-Bytes/Auto-YouTube-Shorts-Maker) | — | gTTS + gameplay = lower bar than current |
| [sw-aka/Short-Video-Creator](https://github.com/sw-aka/Short-Video-Creator) | Local caption styling ideas | Different input model (edit existing clips) |
| [Saganaki22/ContentMachine](https://github.com/Saganaki22/ContentMachine) | Workflow packaging ideas | Evaluate only if still maintained / fits news |
| [hkuds/vimax](https://github.com/hkuds/vimax) | Research if multimodal editing helps later | Not Sprint 2 |
| [topics/ai-video-editor](https://github.com/topics/ai-video-editor) | Scan for ffmpeg/EDL agents (e.g. transcript→cut) | Skip CapCut cracker / unlocker noise |
| [topics/video-generator](https://github.com/topics/video-generator) | Faceless Shorts patterns | Avoid gameplay-quote clones |

**Principle:** Coin Wire already has news → script → Edge → ffmpeg → YouTube. Improve **gates and timing** inside that spine.

---

## 5. Growth & promotion (views / likes / shares)

Quality raises **retention**; distribution raises **reach**. At ~1 sub both are required. Paid ads are optional **after** a Short reliably holds the first 3–10s.

### 5.1 Owned channels (do first — $0)

| Channel | How | Cadence |
|---------|-----|---------|
| **Telegram `@coinwirenews`** | After Short goes PUBLIC: post short teaser + YouTube Shorts link (or native TG video later). Same story as the Short, one hook line + link. | Every Short (2×/day when YT ships) |
| **YouTube itself** | Consistent title pattern (`$ / % / named actor` first); 3–5 tags; end screen/CTA to channel; reply to early comments in first hour. | Every upload |
| **Pin / community** | Pin best-performing Short; Community post “today’s move” with link when YouTube allows. | 2–3×/week |

**Product hook (code later):** pipeline already notifies owner on upload — add optional **channel teaser** when auto-publish fires (`publish_pending_shorts` → TG channel), so promo is not manual.

### 5.2 Free discovery (organic)

| Surface | Tactic | Fit now |
|---------|--------|---------|
| **YouTube Search / browse** | Titles with concrete facts (“ETF inflows $…”, “SEC …”); avoid vague “analysis eyes…”. | High — free, compounds with Sprint 4 angles |
| **Shorts feed** | Retention + posting at schedule (09:00 / 18:00 ET already). Don’t spam >2–3/day. | High |
| **Reddit** (r/CryptoCurrency, r/Bitcoin, niche) | Only if rules allow self-promo; prefer value comment + link, not dump. Risk of bans. | Medium / careful |
| **X / Threads** | One-liner + Short link when Meta/X tokens work; until then manual or skip. | Medium when OAuth alive |
| **TikTok / Reels** | Same MP4, different caption. **TikTok Login Kit Production: rejected** for crypto (“Virtual currency/Cryptocurrency related will not be approved”) — **no API autopilot**. Manual upload to a personal/creator TikTok account is still possible outside the rejected app. IG Reels only after Meta + R2. | TikTok API = **blocked**; manual optional; IG later |
| **Crypto Discords / newsletters** | Guest one-liners, “tool of the week” — human outreach, not automation. | Low volume, high trust |

### 5.3 Paid (only after retention proof)

| Channel | When | Notes |
|---------|------|-------|
| **YouTube Ads (Promote / Video campaigns)** | Avg view duration / % viewed looks healthy on last ~10 Shorts | Start tiny ($5–15/day), target crypto/finance interests or similar videos; kill creatives with &lt;30% viewed |
| **Boost best organic Short** | One clear winner (views + likes) | Don’t boost every upload |
| **Telegram ads / crypto Twitter ads** | After TG channel has steady readers | Easy to waste — measure CTR to YT |

**Rule:** never buy traffic into soft pacing. Fix Sprint 1–2B first, then spend.

### 5.4 What to measure (small-channel dashboard)

| Metric | Why |
|--------|-----|
| **Average percentage viewed** / avg view duration | Primary — likes follow this |
| Likes / views, shares / views | Engagement quality |
| Traffic source (Shorts feed vs Search vs External / TG) | Are promos working? |
| Subs gained per Short | Secondary at this size |
| TG clicks / forwards on teaser posts | Owned loop health |

Ignore vanity: raw view spikes from dead traffic with 5% viewed.

### 5.5 Promo backlog (ordered)

1. Manual ritual: every PUBLIC Short → TG teaser same day (start this week).  
2. Title/description template for search + shareability (align with Sprint 4 angles).  
3. Automate TG teaser on auto-publish (small code story).  
4. ~~TikTok API crosspost~~ — **Production denied (crypto policy).** Optional: manual TikTok upload of winners; IG Reels when Meta + R2 ready.  
5. Tiny YouTube Promote test on **one** high-retention Short.  
6. Optional: Showrunner cast for “Growth epic” if paid + multi-platform budget decisions conflict.

### 5.7 MCP Market note (2026-08-11)

[mcpmarket.com](https://mcpmarket.com/) is a **directory of agent tools**, not a new video engine. Most listings wrap either (a) official APIs we already have, (b) paid SaaS, or (c) cookie/browser bots.

**Do not** wire unofficial “post without API keys” MCP servers into Railway. Same class as TiktokAutoUploader: session cookies = full account access; ToS/ban risk; TikTok already rejected our crypto Production app.

Legitimate alternatives if we want TikTok later: official Login Kit (blocked for crypto), or a **partner scheduler** (Plann/Buffer-class) where *their* audited app posts. Threads Growth MCP uses the **official Threads API** — we already have that path; it is failing on expired token (`OAuthException 190`), not missing MCP.

---

### 5.6 Anti-patterns

- Posting Shorts with no TG push (“upload and pray”).  
- Buying ads before hooks hold 3s.  
- Spamming Reddit/Discords → brand burn.  
- Chasing Meta Graph while YT+TG loop is empty.  
- Fighting TikTok Production review for a **crypto** app (policy reject — don’t burn cycles on appeal unless TikTok policy changes).  
- Promoting every weak Short equally.

---

## 6. Decision log (avoid repeating the R2 mistake)

| User intent | Wrong translation | Right translation |
|-------------|-------------------|-------------------|
| “AI picks fitting B-roll” | Sync 4GB library to R2 | Score candidates (CLIP/YOLO) at pick / fill time |
| “Livelier voice” | Clone every OSS voice repo into Docker | A/B Edge → paid TTS or one HF model on GPU/API |
| “Better montage” | New video framework | Tune cuts, SFX, hook, ASS, outro length |
| “More views / likes / shares” | Only buy ads or more platforms | Retention craft + **TG→YT loop** + titles; ads after proof |

---

## 7. Suggested order of work

```text
[done] Sprint 1 pacing/outro/CTA
   ↓
[now]  User local --skip-upload listen
   ↓
Sprint 2A script hygiene + Edge A/B
   ↓
Sprint 2B montage/subs polish (ffmpeg)
   ↓
Promo loop: TG teaser each public Short (manual → then automate)
   ↓
Sprint 3 voice: decide Edge OK vs ElevenLabs vs Kokoro/Chatterbox endpoint
   ↓
Sprint 4 news angles / scoring (+ searchable titles)
   ↓
Platforms amplify: **manual TikTok only** (API blocked for crypto); IG Reels later; optional tiny YT Promote on winners
   ↓
(later) B-roll AI-at-render revisit
```

---

## 8. Acceptance checklist (per Short)

**Craft**
- [ ] Spoken length ~18–28s  
- [ ] No dead air between lines  
- [ ] Ending ≤ ~1.5s visual, no second news essay  
- [ ] Hook-stat readable in first 2s  
- [ ] Karaoke readable; no collision with ticker  
- [ ] VO feels news-desk, not bedtime story  
- [ ] Title/script match one clear story (no truncated garbage lines)

**Distribution**
- [ ] Title leads with fact ($ / % / named actor)  
- [ ] PUBLIC Short pushed to Telegram (teaser + link) same day  
- [ ] After ~24–48h: check % viewed — if weak, don’t boost; fix craft

When Sprint 1 is confirmed on a local MP4, commit + deploy; then start 2A.

# Coin Wire — roadmap: B-roll library + platforms

Goal: **first understand** the brownfield system (BMAD analyst + architect + video-editor lens), define a **quality gate** (YOLO for video, separate scorer for text posts), then improve Shorts by auto-filling and scoring `data/assets/broll_library/`.

See also: [`docs/bmad_analysis_brief.md`](bmad_analysis_brief.md) — session order and skill names.

---

## Current state

| Piece | Status |
|-------|--------|
| Telegram + YouTube Shorts | Working |
| Local B-roll folders | Exist (`bitcoin/`, `ethereum/`, `macro/`, …) but mostly empty |
| Pexels / Pixabay | Used **at render time** (slow, random, API-rate limited) |
| Meta (Threads / IG / FB) | Unreliable API — deprioritize |
| TikTok | Needs OAuth tokens |
| YOLO / CLIP tagging | Not implemented |
| **BMAD** | **Installed** — `_bmad/` + BMM + CIS; 56 skills in `.agents/skills/` |

**Problem:** every Short may hit Pexels live. We want the opposite: **batch-download once → library grows → quality-scored local clips dominate**.

---

## Phase 0 — BMAD multi-lens analysis (orchestrated — one chat)

**Do not** open separate chats per BMAD agent. Use the **Showrunner**:

| Invoke | Effect |
|--------|--------|
| `coin-wire-orchestrator` | Parent agent spawns Mary / Winston / Sophia / Reel as Task subagents, then writes one synthesis |
| `bmad-party-mode` | Same cast as party `coin-wire-staff` (default in `_bmad/custom/bmad-party-mode.toml`) |

Config / skill:

- `_bmad/custom/bmad-party-mode.toml`
- `.agents/skills/coin-wire-orchestrator/SKILL.md`
- Brief: [`docs/bmad_analysis_brief.md`](bmad_analysis_brief.md)

| Lens | Who | Job |
|------|-----|-----|
| Analyst | Mary | Product priority, Meta debt, cadence |
| Architect | Winston | Where fill / YOLO / post-scorer plug in |
| Storyteller | Sophia | Narrative / anti-AI copy |
| Video editor | Reel | Hook + visual QA rubric |

Host output (mandatory): `_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md`

### Quality evaluation design (from synthesis)

| What | Tool | Note |
|------|------|------|
| Video / B-roll / Short MP4 | YOLO + ffprobe + motion | Objects, clutter, reject junk |
| Topic match | CLIP | Category fit |
| Text posts | Rules / humanize / editorial | **Not YOLO** |
| Combined report | Optional QA job | Video score + post score |

Platform posture:

1. Telegram + YouTube = core autopilot  
2. Meta → semi-auto until API is reliable  
3. TikTok OAuth when ready; IG after R2  

---

## Phase 1 — Auto-fill B-roll library

**Idea:** a scheduled (or one-shot) job that searches stock APIs and **writes MP4s into category folders**, so YOLO/CLIP later only *sort and label* — they do not invent footage from scratch.

### 1.1 Script: `scripts/fill_broll_library.py` ✅

```
for each category:
  search Pexels (+ Pixabay)
  download under quota
  ffprobe gate + YOLO tag (if ultralytics installed)
  reject → category/_rejected/ + *.meta.json
  keep → category/{source}_{id}.mp4 + meta (flags: has_screen, …)
```

Also: `pip install ultralytics opencv-python-headless` for YOLO marks.

### 1.2 Query packs (examples)

| Category | Example queries |
|----------|-----------------|
| bitcoin | bitcoin trading, crypto chart, candlestick screen, bitcoin office |
| ethereum | ethereum, blockchain network, cryptocurrency laptop |
| macro | stock market ticker, wall street, federal reserve, inflation news |
| regulation | courthouse, government building, legal documents, compliance |
| security | cyber security, hacking code, lock digital |
| defi | digital finance, tokenization, smart contract abstract |
| default | city night finance, money abstract, trading floor |

### 1.3 Guardrails

- Daily / weekly **quota** (e.g. max 20 new clips/day) — respect Pexels rate limits.
- Prefer **portrait** or crop-friendly landscape with enough height.
- Store metadata JSON next to clip: `{source, id, query, url, duration, orientation, downloaded_at}`.
- Never overwrite existing IDs; never delete without a `--prune` flag.
- License: stick to Pexels/Pixabay free terms; keep source id for attribution if needed.

### 1.4 Config

Add under `config/coin_wire.yaml`:

```yaml
broll_library:
  auto_fill: true
  max_clips_per_category: 40
  max_downloads_per_run: 20
  min_duration_sec: 5
  max_duration_sec: 30
  prefer_portrait: true
```

### 1.5 Ops

- Run manually: `python scripts/fill_broll_library.py`
- Optional Railway cron once a week (off-peak), or local only if disk on Railway is limited.
- Volume: library lives on a **persistent volume** (or sync from local → deploy).

**Success:** each category has ≥15 usable clips; Short pipeline `source_stats.local` dominates over `pexels`.

---

## Phase 2 — Tag / score clips (YOLO + lighter tools)

YOLO does **not** download videos. It **analyzes** what is already on disk (or what Phase 1 just saved) and decides keep / reject / re-folder.

### 2.1 Offline indexer: `scripts/index_broll_library.py`

Pipeline per clip:

1. **Probe** — duration, resolution, fps, bitrate (ffprobe).
2. **Scene / motion** — skip near-static or too-dark clips (OpenCV or ffmpeg `scdet`).
3. **Object tags (YOLOv8n)** — optional GPU/local: `person`, `laptop`, `cellphone`, `tv`, `car`, …  
   → useful signals: “has screen/chart-like object”, “crowded street”, etc.
4. **CLIP text match** (recommended even without YOLO) — embed clip keyframes vs category prompts  
   e.g. `"bitcoin candlestick chart on monitor"` → score for `bitcoin/`.
5. Write `data/assets/broll_library/index.json` (or sidecar `.meta.json` per file).

### 2.2 Auto-sort rules

- Low CLIP score for current folder + high score for another → **suggest move** (or `--apply` move).
- Too many faces / logo-like clutter → mark `avoid_as_hook` or reject.
- High motion + dark + charts → prefer for **hook** (first 2s).

### 2.3 Reality check

| Approach | Role |
|----------|------|
| Auto-download (Phase 1) | Fills folders |
| CLIP | Best ROI for “does this match crypto/macro?” |
| YOLO | Nice extras: object presence, reject bad frames |
| Training custom YOLO | **Skip** — not worth it for stock B-roll |

**Success:** renderer can prefer clips tagged `good_for_hook`, `has_screen`, matching category score ≥ threshold.

---

## Phase 3 — Wire into existing renderer

Today: `StockVideoFetcher` tries local library, then live Pexels.

Improve:

1. Prefer **indexed** local clips (score + unused this week).
2. Rotate so the same 3 clips do not appear every Short.
3. Track `used_clip_ids` in state (like used article hashes).
4. Live Pexels only if category library &lt; N clips or all recently used.
5. Log `% local vs api` in Telegram `/status` or pipeline summary.

---

## Phase 4 — Project Skills (after BMAD analysis hardens the vocabulary)

BMAD is **already installed** (see Phase 0). Project-specific skills still help agents not re-learn Coin Wire ops:

Store under `.cursor/skills/` *or* `.agents/skills/` (BMAD Cursor target is `.agents/skills`).

| Skill | When agent should use it | Contents |
|-------|--------------------------|----------|
| `coin-wire-broll` | Filling / indexing / picking B-roll | Paths, fill script, quotas, CLIP/YOLO index |
| `coin-wire-video` | Short pipeline | ffmpeg, karaoke, hook, quality checks |
| `coin-wire-publish` | Cross-post / Railway | TG+YT first, Meta draft, TikTok, R2 |
| `coin-wire-qa` | Quality gates | YOLO video rubric + text post score |

**BMAD usage (locked in):**

1. Phase 0 analysis (document → three lenses → party).  
2. `bmad-prd` / `bmad-architecture` / epics for B-roll + QA epic.  
3. `coin-wire-*` skills = domain truth; BMAD = process.

---

## Phase 5 — Content / platform improvements (parallel)

Small wins while B-roll + QA mature:

1. **Telegram draft for Threads/IG** — copy-paste fallback.  
2. **TikTok OAuth**.  
3. **R2** — only if Instagram Reels remains a goal.

---

## Suggested order of work

| Step | Deliverable | Effort |
|------|-------------|--------|
| **0** | **Showrunner run** (`coin-wire-orchestrator`): 4 subagents → one synthesis file | 1 session |
| **0b** | PRD + architecture for B-roll fill + YOLO/CLIP video QA + text post QA | 0.5–1 day |
| 0c | Optional `coin-wire-*` skills from agreed vocabulary | 0.5 day |
| 1 | `fill_broll_library.py` + yaml queries + metadata | 0.5–1 day |
| 2 | Fill locally ≥15 clips/category; smoke-render | 0.5 day |
| 3 | `index_broll_library.py` — ffprobe + CLIP + **YOLO** quality flags | 1–1.5 day |
| 4 | Renderer: scored local pick + rotation | 0.5 day |
| 5 | Text **post score** job (pairs with video score for reports) | 0.5 day |
| 6 | Platform fallbacks (TG draft / TikTok) | as needed |

---

## What we are *not* doing

- Treating YOLO as a text/post authoring tool (it only sees frames).  
- Scraping competitors’ Shorts and recreating them.  
- Training custom YOLO on crypto charts from scratch (start with YOLOv8n COCO).  
- More Meta Graph digging until analysis + video quality path are clear.  
- Dumping thousands of clips onto Railway without a volume strategy.

---

## One-line summary

**BMAD (analyst + architect + editor) agrees the plan; YOLO scores video quality; a separate scorer rates posts; then we auto-fill and use a scored B-roll library.**

**BMAD is installed + Showrunner skill.** Next: say **«запусти оркестратор»** in this chat (no new tabs).

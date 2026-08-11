# Coin Wire — Instagram carousels (Minimal Glassdark)

Locked visual system for static IG. Reels stay the daily Shorts pipeline. Do not mix formats.

**CTA destinations (real, not coinwire.news):**
YouTube `https://www.youtube.com/@CryptoFinanceDigest` · Telegram `t.me/coinwirenews` · IG `@coinwire.news`

## Verdict

| Take | Skip |
|------|------|
| Carousel 4:5 (1080×1350), 6–8 slides | Stories as a planned product (repost slide 1 only if spare time) |
| Quote-card / breaking still ≤1× week | Video carousels |
| 3 carousels / week, Reels first | 10+ slide infographics, single photo as the growth format |

Never publish a Reel and a carousel on the **same story** the same day.

## Weekly grid

| Day | Rubric | Notes |
|-----|--------|--------|
| Mon | **B Week Desk** | Digest of last week. Target ~10:00 UTC. Pipeline may still render a Short that day — pick a *different* topic or skip the carousel. |
| Wed | **A What Moved** or **D Top List** | Hottest story, or skip if that day's Reel already covers it. Every other Wed may be a quote-card (real quote + named source, no generated face). |
| Fri | **C Explain** or **E How to Read** | Evergreen. Reel the same day is fine. |

Three carousels is a ceiling for one operator posting by hand. If a week is on fire, drop Friday, never drop Reels.

## Visual tokens

Same as desk: `#08090E` bg · `#111318` panel · `#F0B429` accent · `#E5E7EB` text · `#6B7280` meta · `#1E2028` line.

- Left accent: 3px gold bar, x≈80px, headline starts ~x=110.
- Type: Inter / system-ui. Title 700 ~72–80px on 1080. Body 400–500 ~44–52px. Meta ~32px `#6B7280`.
- Max 12–16 words on a title slide (digest slide may hit ~30 at smaller size).
- Canvas 1080×1350. Safe 80px all sides. **No copy in the bottom 250px.**
- Wordmark `COIN WIRE` top-left, ~28px, `#6B7280`. Rubric tag top-right, same size (`WHAT MOVED` / `WEEK DESK` / `EXPLAIN` / `TOP LIST` / `HOW TO READ`).
- No neon `#00e676`, Orbitron, fake TradingView, fake faces, unfiltered stock, emoji piles.

**Stock** (Pexels/Pixabay): only when a real place matters (Fed building, floor, servers). Overlay 50–70% `#08090E` + bottom gradient. No watermarks, no recognizable faces in front.

**Gen** (Flux/SD/MJ): covers, diagrams, wire-nodes, paper texture. Never photoreal people, never other brands' logos, never charts with numbers.

One texture language per carousel (don't mix isometric cover with paper on slide 3).

## Templates

**A — What Moved (6)**  
1 Hook (stock + overlay) · 2 one number, no photo · 3 context · 4 what to watch (dates, not a trade) · 5 source · 6 CTA YouTube/TG.

**B — Week Desk (7)**  
1 cover (gold wire nodes) + date range · 2–6 one story each (big gold index) · 7 “That's the week” + CTA.

**C — Explain (7)**  
1 question + “Plain language. No trading advice.” · 2–5 term (gold) + definition + why it matters · 6 dated real case + source · 7 “Bookmark this.”

**D — Top List (7, not 6)**  
1 title (“5 things that moved BTC this week”) · **2–6 one item each** (01–05) · 7 CTA. (The draft had 2–5 = four items for a five-list. Fixed.)

**E — How to Read (6)**  
1 “You read the headline wrong.” · 2 headline vs 3 what happened vs 4 what media flattened · 5 “Next time check [source]” · 6 CTA.

## Caption

1. One-sentence fact.  
2. Two sentences of context. Blank line.  
3. One CTA: `Full breakdown on YouTube.` / `Swipe for context.` — never “FOLLOW FOR ALPHA”.  
4. Blank line. **3–5** tags from: `#bitcoin #crypto #cryptonews #btc #ethereum #sec #etf #federalreserve #cryptoregulation`.  
Voice: short active verbs. No `game changer` / `NFA DYOR` / emoji rows.

## Gen negative (append always)

`no readable text, no fake chart data, no logos of real companies, no photoreal human faces, no watermark, no neon green accents, no rainbow gradients, no bitcoin moon rocket meme, no TradingView screenshot style, no busy cluttered composition`

Cover prompts live in chat history / the art pass. Palette locked to the hex tokens above.

## Automation (What Moved)

Daily Short pipeline renders **template A** as six 1080×1350 JPEGs on the desk (`/media/ig/…` + ZIP). Slide 1 uses Pexels/Pixabay if keys exist, otherwise a solid desk background. Slides 2–6 are type-only. Telegram is only the Short MP4 + copy packs — carousel is on the site.

Templates B–E (Week Desk, Explain, Top List, How to Read) are still editorial — not in the daily job.

# Coin Wire — BMAD analysis brief

**Status:** Orchestrator done; **fill + YOLO-on-ingest implemented** (`scripts/fill_broll_library.py`).  
**Goal next:** run fill locally (install ultralytics for YOLO marks), then CLIP index / renderer preference.

Communication / docs language for BMAD config: **uk**.

---

## How you work (important)

**Do not** open 4 tabs and talk to analyst / architect / editor separately.

| Approach | What to say |
|----------|-------------|
| **Preferred** | `coin-wire-orchestrator` or «запусти showrunner / оркестратор» |
| BMAD party (same idea) | `bmad-party-mode` — party `coin-wire-staff` (default) |

The **Showrunner** (parent agent in this chat):

1. Spawns Mary / Winston / Sophia / Reel as **subagents** (Task tool)
2. Collects their findings
3. Writes **one** synthesis → `_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md`
4. Proposes the next implementation step

You only reply in this thread and pick from the backlog.

Party config: `_bmad/custom/bmad-party-mode.toml`  
Skill: `.agents/skills/coin-wire-orchestrator/SKILL.md`

---

## Cast

| Role | Who | Focus |
|------|-----|--------|
| Analyst | Mary | Product, Meta debt, metrics |
| Architect | Winston | fill_broll, YOLO index, Railway |
| Storyteller | Sophia | Voice / copy not feeling AI |
| Video editor | Reel (custom) | Hook, B-roll, YOLO visual QA |
| **Host** | Showrunner | Assigns work, synthesizes, one file |

---

## YOLO vs posts

| Asset | Tool |
|-------|------|
| Video / B-roll / Short | YOLO + CLIP + ffprobe |
| Text posts | Separate scorer (not YOLO) |

---

## Session order (orchestrated)

1. User invokes **`coin-wire-orchestrator`** (or party `coin-wire-staff`).
2. Parallel subagent briefings.
3. Optional clash round.
4. Synthesis file written.
5. User picks backlog item → implement in **same** chat.

Artifacts:

- `_bmad-output/planning-artifacts/coin-wire-staff-synthesis.md`
- later PRD / architecture under `_bmad-output/planning-artifacts/`
- long-lived knowledge: `docs/`

---

## Draft rubrics (refine in orchestrated run)

### Video

- 5–30s; portrait or crop-safe  
- Not near-black / washed-out  
- Prefer screen/chart / finance scenes; reject lifestyle clutter  
- CLIP topic score ≥ threshold  
- Hook: relevant object / energy in first ~2s  

### Posts

- No em-dash AI fingerprint; no boilerplate Threads takeaways  
- Fact overlap with source  
- Platform length caps; sparse tags; questions ≤ ~25%  

---

## Start line

In this chat: **«запусти оркестратор»** / invoke `coin-wire-orchestrator`.

# TANGLE Canvas — Design Principles

> Per's directive 2026-06-29: clean, opinionated, scalable.

## TL;DR

The TANGLE canvas is **mostly empty by default**. One entity + a great file drop.
Nodes build up as the user does things. Color is **monochrome** (black/white
+ gray ramp only). Stats and pipelines are **toggleable layers**, not always-on.

---

## Core principles

### 1. Empty is the default state

When a user opens TANGLE, they should see:
- A single entity placeholder (centered, zoomed in)
- A beautiful file drop zone (the primary CTA)
- Nothing else

No MAESTRO orchestrator. No pipeline. No counters. No verbose logs.
**Just: "drop a file to start" or "type an entity name to begin."**

Implementation: `App.tsx` initial state has zero/one entity node. Panels
(Logs, Index, CLI) are hidden behind header buttons, not auto-shown.

### 2. Nodes build up incrementally

As the user does things, nodes appear:
- **Drop file** → `SourceNode` appears at drop position
- **Run mission** → `PipelineNode`s appear for Planner/Scout/Librarian/Critic/Synthesizer
- **Mission completes** → `EntityNode` shows the report preview
- **Wiki expands** → `MemoryNode`s / `WikiNode`s radiate from entity

Build-up should feel **deliberate and physical**, not spammy. Each node
has an entry animation (fade + scale from 0.85 → 1.0, ~200ms ease-out).

### 3. Monochrome palette (B/W)

Until further notice:
- **No purple, cyan, or accent colors anywhere in the canvas**
- Background: pure black `#000` to deep gray `#0a0a0a`
- Text: pure white `#fff` and off-white `#e5e5e5`
- Borders: gray ramp — `#1a1a1a`, `#333`, `#555`, `#888`
- Active/selected states: **white** (not cyan or purple)
- Glow effects: white at low opacity (max ~15%) for hover/active

**Status colors are STATE, not decoration** — keep red/amber/green ONLY
for actual status indicators (`running`, `failed`, `complete`).

### 4. Stats are toggleable

The default canvas shows zero stats. Toggle layers in `App.tsx`:

| Toggle | Default | Keyboard | What it shows |
|---|---|---|---|
| Pipeline | OFF | `1` | Planner/Scout/Librarian/Critic/Synthesizer nodes + WebSocket status |
| Counters | OFF | `2` | Active/Events/Agents counters on each orchestrator node |
| Verbose logs | OFF | `3` | Agent-by-agent telemetry panel (AgentVerbosePanel) |
| Sources | ON | `4` | SourceNode visibility — files dropped |
| Wiki | ON | `5` | MemoryNode visibility — wiki chunks radiating |

Toggles live in a small bottom-right toolbar (NOT top-right header —
keep header for the 3 essential actions: INDEX / CLI / LOGS).
On mobile / small viewport, toolbar collapses to a "Layers" menu.

### 5. File drop is a feature, not a button

Drop zone should be:
- **Centered in the canvas when empty**, sized ~400px × 240px
- Visible-by-default with a subtle pulse animation every 4-5s
- On hover with files: brightens + shows accepted formats
- Multi-file support (multiple SourceNodes appear staggered)
- Also accepts URLs (paste, auto-fetch)
- Also accepts text from clipboard

When canvas already has nodes: drop zone collapses into a small "+" button
in the corner (only appears when drag-over).

### 6. The entity node should disappear

The current EntityNode shows: name + status icon + 8 fields (filepath,
report preview, critic score, tags, etc.).
Default state should show: **just the name + a single status dot**.
Expanded view (on click) reveals the full content.

Open question: should entity be shown as a single card that expands, or
as a radiating graph (entity in center, chunks around it)?
TBD — document iteration, see "Open questions" below.

---

## Visual hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│ TANGLE                              [INDEX] [CLI] [LOGS]      │   ← header (always)
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                                                              │
│                    ┌──────────────────────┐                  │
│                    │                      │                  │
│                    │   DROP A FILE OR     │                  │
│                    │   TYPE AN ENTITY     │  ← entity/drop  │   ← center
│                    │                      │                  │
│                    └──────────────────────┘                  │
│                                                              │
│                                                              │
│                                          [Layers ▾] [⚙]    │   ← bottom-right
└─────────────────────────────────────────────────────────────┘
```

After a mission runs:
```
┌─────────────────────────────────────────────────────────────┐
│ TANGLE                              [INDEX] [CLI] [LOGS]      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│         ┌─────────┐                                           │
│         │ PLANNER │ ─→ ┌──────┐                               │
│         └─────────┘    │SCOUT │ ─→ ┌────────┐                 │
│                        └──────┘    │ LIB    │ ─→ ...          │
│                                      └────────┘                │
│                                                              │
│         ┌─────────────────┐                                   │
│         │ Acme Corp   ✓   │  ← entity (click to expand)     │
│         └─────────────────┘                                   │
│                                                              │
│                                          [Layers ▾] [⚙]    │
└─────────────────────────────────────────────────────────────┘
```

---

## Color token spec

```css
:root {
  /* Background ramp */
  --bg:        #000;        /* canvas / page */
  --bg-1:      #0a0a0a;     /* node body */
  --bg-2:      #141414;     /* hover / nested surface */
  --bg-3:      #1f1f1f;     /* header / footer */

  /* Borders */
  --border:    #1a1a1a;     /* inactive */
  --border-1:  #333;        /* hovered */
  --border-2:  #555;        /* active */

  /* Text */
  --text:      #ffffff;     /* primary */
  --text-1:    #e5e5e5;     /* body */
  --text-2:    #888;        /* labels */
  --text-3:    #555;        /* disabled */

  /* Status only (not decoration) */
  --status-running: #c084fc;  /* mauve */
  --status-done:    #ffffff;  /* pure white */
  --status-failed:  #c084fc;  /* mauve same as running (low-budget mode) */
  --status-idle:    #555;     /* mid gray */

  /* NOT USED for now (delete from :root) */
  /* --cyan, --purple, --pink, --orange, --green */
}
```

**Decision rule:** any `--cyan` / `--purple` reference that exists today
is either a leftover or a "decoration color" — both should be removed.
Status colors get specifically named (not generic).

---

## What's actionable tonight vs. tomorrow

### Tonight (Phase 0.1 polish)
- [x] Capture this doc as the source of truth
- [ ] Identify all `--cyan` / `--purple` references in CSS + tsx
- [ ] Define new monochrome token set in `:root`
- [ ] Empty-canvas default (no auto-shown Pipeline/Counters)
- [ ] B/W palette applied to App.tsx + EntityNode + edges

### Tomorrow (Phase 0.1 finish)
- [ ] Toggle layer controls in bottom-right toolbar
- [ ] File drop as canvas-center CTA when empty
- [ ] Per-node entry animations
- [ ] Updated screenshot to confirm aesthetic

### Out of scope (Phase 1+)
- [ ] Mobile responsive
- [ ] Keyboard shortcuts panel
- [ ] Theme variants (B/W current, accent for v2)

---

## Open questions for Per

1. **Entity representation:** single card vs radiating graph?
2. **Pipeline visual:** always animate flow direction, or just static on hover?
3. **Source node deduplication:** drop same file twice → one node or two?
4. **Empty-state copy:** "Drop a file or type an entity name to begin" — too long? More concise?
5. **Onboarding:** for first-time users, show a 5-second demo animation of a mission running, or let them discover?

---

## References (already in repo)

- `frontend/src/index.css` — current CSS variables + markdown report styling
- `frontend/src/App.tsx` — top-level layout, state, header buttons
- `frontend/src/nodes/EntityNode.tsx` — main entity display (current: too busy)
- `frontend/src/nodes/PipelineNode.tsx` — Planner/Scout/etc. nodes
- `frontend/src/components/FileDropZone.tsx` — current drag-drop (per source code review)
- `frontend/src/store/agentStore.ts` — pipeline state, events, telemetry
- `docs/screenshots/canvas-2026-06-29.png` — current state (purple/cyan + busy)

---

*Last updated 2026-06-29 by Mavis during TANGLE session.*

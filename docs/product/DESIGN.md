# Presentation Skill — Design System

> **Living document.** Every claim about behavior is annotated:
> - `[current]` — implemented today.
> - `[planned: <spec-slug>]` — spec exists or will be created; not yet
>   implemented. Slugs are forward-reference identifiers, not links.
>   When the corresponding PR lands, update the annotation to `[current]`.
>
> Drift is a bug. See [Maintenance Rule](#maintenance-rule).
> Design Evidence footnotes are at the bottom of this file.

---

## Subsystem Index

| # | Subsystem | What it does | Primary script(s) |
|---|-----------|-------------|-------------------|
| 1 | [Invocation](#invocation) | How to start the skill; example prompts | `/ppt-agent` slash command |
| 2 | [Planning](#planning) | Interview → outline → planning.json → proof | `assemble_planning.py`, `planning_validator.py`, `proof_worksheet.py` |
| 3 | [Rendering](#rendering) | planning.json → per-slide HTML files | SKILL.md pipeline + `prompt_harness.py` |
| 4 | [Preview HTML](#preview-html) | Single-file browser presenter | `html_packager.py` |
| 5 | [Exports](#exports) | Slides → PNG, PDF, PPTX | `html2png.py`, `build_pdf.py`, `png2pptx.py`, `svg2pptx.py` |
| 6 | [Assimilation](#assimilation) | External deck → repo assets | `assimilate-slides` skill |
| 7 | [Mermaid Render](#mermaid-render) | Diagram source → SVG/PNG/HTML | `scripts/mermaid_render/` |

---

## Invocation

### Entry Points

The skill is activated by the `/ppt-agent` slash command or by describing a
deck brief in natural language. Two primary modes: **deck generation** (the
full pipeline) and **review-only** (narrative feedback without generating
slides).

**Common activation patterns:**

| Intent | Example prompt |
|--------|---------------|
| New deck from topic | `/ppt-agent` → "Quarterly business review for the infra team, 12 slides, formal style" |
| New deck from source material | `/ppt-agent` → "Build a deck summarising this research report: [paste or attach]" |
| New deck from an existing outline | "Start at Step 4 planning with this outline: [attach outline.json or paste]" |
| Narrative arc review → feedback | "Review the narrative arc of this deck and give me structured feedback on story flow, message clarity, and call-to-action" |
| Narrative review → HTML/PDF report | "Review this presentation and produce a feedback report I can share as HTML or PDF" |
| Quick facilitation read | "What story does this deck tell, where does it lose the audience, what's the strongest slide? [attach or paste]" |

### Step 1 — Needs-gathering interview `[current]` [¹⁵]

After a topic is given, the skill does a quick background search, then sends
the user **3–7 structured questions** covering:

- Scene and context (what event, what room)
- Audience (who, what they know, what they fear)
- Action (what the deck must move people to do)
- Narrative arc (problem/insight/resolution or other frame)
- Emphasis (the one thing that must land)
- Persuasion approach (data-led, story-led, visual)
- Logistics (page count, format constraints)

The skill **hard-stops** waiting for the user's reply before proceeding —
this step cannot be skipped. The interview output becomes the brief that
drives all downstream planning and rendering decisions.

### Narrative Arc Review Use Case [¹⁶]

The skill can be used in **review-only mode** without generating any slides.
The user provides an existing deck (as a paste, an HTML file, a PPTX, or a
structured outline) and asks for a narrative review. The skill produces
structured written feedback — not slides — that the user can turn into an
HTML or PDF report.

This is a first-class use case. Common patterns:

- "Review this deck for narrative coherence and message clarity"
- "Give me facilitation feedback — what story does it tell, where does it lose
  the audience, what's the call-to-action gap"
- "Produce a narrative arc review of [deck] formatted as a shareable feedback
  report"
- "Score each slide: does it advance the argument, is the headline opinionated,
  is the evidence sufficient"
- "Compare the stated objective from my brief against the deck that was built —
  where is the drift"

Output is structured Markdown or HTML that the user renders as a PDF via
browser print or the Exports pipeline.

---

## Planning

### Design Intent [⁷]

The planning step validates and assembles each slide's structured data
(`planning.json`) before rendering begins. It is a **schema gate**, not a
design tool — it catches structural errors (wrong layout names, budget
violations, missing required fields) at the cheapest possible point in the
pipeline.

### Key Contracts `[current]`

- **`assemble_planning.py`** — consumes a minimal per-page payload from the
  planning subagent and produces a fully schema-valid `planning.json`.
- **`planning_validator.py`** — the single authoritative oracle for all enums,
  budget constants, and structural rules. `assemble_planning.py` imports
  directly from it. [⁸]
- Outputs: one `planning<N>.json` per page (or a wrapped deck payload).
- Cross-page checks (duplicate slide numbers, 3-consecutive-high density,
  dashboard neighbours) are intentionally **out of scope** for per-page tools
  — they belong to the orchestrator.

### Step 4.5 — Proof Worksheet `[current]`

Before rendering begins, `proof_worksheet.py` generates a deterministic,
**zero-LLM** HTML worksheet (`runtime/proof/<deck-slug>-intent.html`) from all
`planning/planningN.json` files plus `outline.json`. It shows each slide as a
schematic blueprint: layout label, headline, body intent, data/chart type. The
user can catch structural and content problems cheaply before a full LLM
render.

The user chooses one of two paths:
- **A — Review/iterate:** revise planning JSON, re-run proof.
- **B — Render-direct:** proceed to Step 5 slide generation.

`proof_gate.py` enforces this as a hard precondition: Step 5c cannot proceed
without a recorded decision in `runtime/proof/gate.json`.

**Speaker notes in the proof worksheet** `[current]` [¹⁷]

The proof worksheet displays per-slide speaker notes in a "Facilitation" block
after the card table and before the art-direction section. Notes are loaded from
`<deck-slug>-notes.json` (generated by `proof_worksheet.build()` at Step 4.5)
so the presenter can review and refine facilitation intent before rendering.

### Planning-time Speaker Notes `[current]` [¹⁷]

Speaker notes are generated as part of the planning step, not as an
empty stub after rendering. During Step 4.5 (proof worksheet), the system
derives initial notes from each slide's `page_goal`, `narrative_role`,
`audience_takeaway`, and anchor card `headline` in the planning JSON
— capturing the facilitation intent while the content reasoning is live.

These notes populate `<deck-slug>-notes.json` at planning time. The presenter
can then refine them in the proof worksheet (Step 4.5) and again after
receiving the preview HTML. This replaces the current empty-stub pattern where
notes are generated post-render with no initial content.

---

## Rendering

### Design Intent [⁹]

Rendering converts `planning.json` into per-slide HTML files. The pipeline is
**SKILL.md-driven** (instructions layer) with Python scripts as the execution
layer. Rendered HTML must not use CSS features that break downstream converters.

### Architecture Constraints `[current]`

- Output path: `ppt-output/<deck-slug>/slides/*.html`
- CSS must comply with `references/pipeline-compat.md` prohibition list — no
  `<text>` SVG elements, no `mask-image`, no `conic-gradient`, no
  `background-image: url()` — to remain safely convertible by Playwright and
  `svg2pptx.py`.
- `resource_loader.py` routes design tokens and brand assets into render prompts
  without hard-coding paths.

---

## Preview HTML

### Design Intent [¹]

The preview HTML is a **single, self-contained browser file** that a human can:

1. Open offline — no server, no CDN, no network. `[current]`
2. Share by attaching to an email, a Slack message, or a file-transfer link. `[current]`
3. Present directly from a browser — no PowerPoint, no Keynote, no plugins. `[current]`

These three properties drive every constraint below. The file must be fully
self-contained (all images inlined, all CSS inline) and must work in any
modern Chromium-based browser without extensions.

### Architecture Constraints

#### Slide isolation — iframe sandbox `[current]` [²]

Each slide HTML file is embedded as an `<iframe srcdoc="..." sandbox="">` with
no `allow-same-origin` flag. This gives each slide an **opaque null origin** —
its CSS, JS, and DOM cannot affect or be read by sibling slides or the outer
wrapper. This is non-negotiable: slides are independently authored and may use
conflicting class names, reset stylesheets, or global variable declarations.

Consequence: all presenter-layer features live in the **outer wrapper document**
and operate via `iframe.style` and `data-*` attributes injected by the packager
— never via postMessage or cross-frame DOM access.

#### Base64 image inlining `[current]` [³]

All local image references (`src="..."`, `url(...)`) in slide HTML are replaced
with `data:` URIs at pack time. JPEG, PNG, GIF, SVG, and WebP are supported.

### Navigation Bar

#### Position: bottom-aligned `[current]` [⁴]

Controls are a **static bar below the slide stage** — not fixed/overlaid, so they
never obscure slide content, and they follow normal document flow.

Confirmed by independent research: every major browser-based presentation tool
uses bottom navigation in presentation mode (reveal.js, Slidev, Slides.com,
PowerPoint for the Web, Keynote, Pitch). No major tool defaults to top-aligned
during present/play mode.

### Controls Layout `[current]`

```
[stage: width:min(1280px,90vw), margin-top:12px]
[controls bar: static, below stage]
  Left group:  ← Prev | → Next | Slides
  Center:      ████████░░░░░░░░  (progress bar, full width, animated)
  Right group: N / total | Notes [current] | Print [current]
```

Controls bar is `display: grid; grid-template-columns: auto 1fr auto`.

### Keyboard Shortcuts `[current]`

| Key | Action |
|-----|--------|
| `←` / `↑` / `PageUp` | Previous slide |
| `→` / `↓` / `Space` / `PageDown` | Next slide |
| `Home` | First slide |
| `End` | Last slide |
| `G` | Open slide jump modal |
| `N` | Toggle speaker notes panel `[current]` |
| `B` | Blank screen (nav or B again to restore) |
| `Escape` | Close slide jump modal |

### Slide Jump Modal `[current]`

A fixed overlay dialog (`position: fixed; inset: 10% 15%`) with a dark scrim
backdrop. Contains a 3-column grid of all slides; each cell shows the slide
number and title (derived from `<title>` or `<h1>` via `_slide_title()`).

- Opened by `G` or "Slides" button; focus moves to first grid item on open.
- Closed by `Escape`, clicking a slide, or clicking the scrim.
- `data-slide-category` badges — `[planned: backlog]`
- Tab-key focus cycling — `[planned: backlog]`

### Speaker Notes `[current]` [⁵]

Speaker notes travel as a **separate deliverable** alongside the preview HTML.
The packager generates a stub `<deck-slug>-notes.json` automatically; the
presenter fills it in and passes it back via `--notes`.

The stub is pre-populated with derived facilitation content by `proof_worksheet.build()`
at Step 4.5; the presenter refines the text and passes it back via `--notes`.

```json
{
  "schema_version": "1",
  "_comment": "Fill in facilitation notes here; pass --notes to html_packager.py to embed them.",
  "slides": [
    { "slide_number": 1, "title": "Cover", "notes": "Plain-text facilitation notes." }
  ]
}
```

Notes are matched by `slide_number` (1-indexed). Empty strings are absent — the
panel stays hidden. The notes panel is `position: absolute` inside the stage,
bottom-right corner; toggled by `N` key or "Notes" button.

### Print / PDF `[current]` [⁶]

A `@media print` block reveals all slides and hides presenter chrome:

```css
@media print {
  @page { size: 13.333in 7.5in; margin: 0; }
  .slide-frame { display: block !important; page-break-after: always; break-after: page; }
  .controls, .slide-jump, .scrim, .notes-panel { display: none !important; }
}
```

A "Print" button calls `window.print()`.

> Browser-native print quality is lower than Playwright PNG export for complex
> layouts. Use Playwright export for final deliverables; Print is for quick
> PDF sharing.

---

## Exports

### Design Intent [¹⁰]

Exports produce the final deliverables a client receives: PNG screenshots for
review, PDF for sharing, PPTX for further editing. **Two PPTX routes exist by
design** — they trade CSS fidelity against text editability.

### Routes `[current]`

| Route | Script | Tradeoff |
|-------|--------|----------|
| PNG export | `html2png.py` → `mermaid_render/png.py` | Playwright screenshot; pixel-1:1 CSS fidelity; text rasterized |
| PDF | `build_pdf.py` | Playwright screenshots → Pillow PDF pages; guaranteed fidelity |
| PNG-embed PPTX | `png2pptx.py` | Full-screen PNG images in PPTX; maximum compatibility |
| SVG-to-OOXML PPTX | `svg2pptx.py` | SVG elements → native OOXML shapes; text remains editable [¹¹] |

Playwright renders at 1280×720 viewport for both PNG and PDF — the same
resolution as the slide stage in preview HTML, ensuring consistency.

---

## Assimilation

### Design Intent [¹²]

The `assimilate-slides` skill absorbs external decks (HTML/CSS, `.pptx`,
`.pdf`, or loose images/SVGs) and produces first-class repo assets: a validated
style JSON, styling spec, block recipes, and SVG icon library entries.

### Architecture Constraints `[current]`

- **Scrub-first policy:** all personally-identifying and confidential material
  must be removed before anything is written to the repo. A scrub checklist
  runs against the full diff before commit.
- **Idea-level icon redraw:** icons are redrawn from concept, never traced from
  originals. Delivered as inline `<svg>`, never `url()` or `<img>`.
- All CSS/SVG must bind to deck theme variables and pass the
  `pipeline-compat.md` prohibition rules.
- No ad-hoc library installs; PDF output is pixel-1:1 via
  puppeteer-screenshot + Pillow.

---

## Mermaid Render

### Design Intent [¹³]

The mermaid render subsystem generates diagrams from Mermaid source text,
producing HTML, SVG, or PNG. It uses a **pure-Python layout engine** — not
the upstream Mermaid.js browser renderer — enabling headless, deterministic
output in CI.

### Architecture `[current]`

Internal pipeline: `_parser.py` → `layout/` (type-specific modules) →
`_renderer.py` (SVG serialization) → optionally `png.py` (Playwright).

Subcommands via `python3 -m mermaid_render`:

| Command | Output |
|---------|--------|
| `render` | HTML |
| `svg` | SVG |
| `png` | PNG (Playwright) |

### Key Constraints `[current]`

- **ELK adapter** (`layout/elk_adapter.py`) — used for graph-type layouts
  (flowchart, ER, class) where cycle detection, crossing minimization, and
  layering are non-trivial. [¹⁴]
- **"Lift seam"** (ADR 002) — rendering contract is separated from layout
  internals; diagram-type layout strategies can be swapped independently.
- P2 native SVG shipped; deferred: mindmap tidy-tree, arch/C4 bidirectional
  edges, C4 shapes, state semantics `[planned: mermaid-p3]`

---

## Maintenance Rule

**Any PR that changes a visual or interaction aspect of a subsystem must update
this file in the same commit. Drift is a bug.**

- When a `[planned: <slug>]` section is implemented, change it to `[current]`
  in that same PR.
- When a new planned feature is introduced, add a `[planned: <slug>]` section
  here before or alongside its spec.
- Never delete a section because it describes future state — use `[planned]`.

Specific enforcement for preview HTML: AGENTS.md requires any PR touching
`scripts/html_packager.py` to update this file in the same commit.

---

## Design Evidence

Brief principle per section. Not exhaustive — full rationale is in the linked
specs and ADRs.

[¹] **Preview HTML — self-contained file:** Zero-dependency portability is the
top constraint. A file that requires a server, CDN, or internet connection
cannot be shared via email attachment or used in a locked-down meeting room.
Every other constraint (iframe sandbox, base64 inlining, inline CSS) is a
consequence of this single axiom.

[²] **iframe sandbox isolation:** Defense-in-depth between independently
authored slides. Any shared global namespace (CSS class names, JS globals,
`window.onload`) creates unpredictable inter-slide interference. Opaque origin
(`sandbox=""`) is the only browser primitive that provides hard isolation
without postMessage overhead.

[³] **Base64 inlining:** A portable file cannot contain external references.
Any `src="./image.png"` becomes a broken link the moment the HTML file moves.
Inlining at pack time makes the file unconditionally self-contained.

[⁴] **Bottom-aligned navigation:** Three converging principles — (a)
media-player convention (stage above / controls below) adopted universally by
video players and browser presentation tools; (b) Fitts's Law (screen-edge
acts as an infinite-width target; cursor decelerates at the floor); (c)
cognitive hierarchy (top chrome competes visually with slide titles; bottom
chrome is spatially separated from the content canvas).

[⁵] **Separate notes.json artifact:** Facilitation notes are a presenter
artifact, not a deck artifact. Keeping them in a separate file lets the deck
travel independently (send the HTML, withhold the notes), allows notes to be
updated post-delivery without rebuilding the deck, and gives the presenter
a clean fill-in-the-blanks template with no risk of corrupting slide content.

[⁶] **`@media print` over JS print-reveal:** CSS `@media print` is a
declarative state change the browser's print engine understands natively —
no JS event listener, no race condition between `window.print()` and DOM
manipulation. The browser handles multi-page layout and margin zeroing
internally once the CSS is declared.

[⁷] **Planning as a schema gate:** Errors caught at planning time (wrong
layout, missing required fields, budget overrun) cost near zero to fix — the
planner can retry with corrected fields. The same error caught at render time
requires a full LLM re-render; caught at export time it requires re-render
plus a client resend. Front-loading validation is the cheapest error strategy.

[⁸] **Assembler imports from validator (single source of truth):** Two
independent definitions of the same enum always drift. Importing directly
from `planning_validator.py` makes it structurally impossible for
`assemble_planning.py` to accept a value the validator would reject — drift
requires changing the wrong file's import, which is immediately obvious.

[⁹] **`pipeline-compat.md` CSS prohibition list:** Downstream converters
(Playwright, `svg2pptx.py`) have known feature gaps — certain CSS/SVG
constructs render correctly in Chrome but fail silently in Playwright or
produce malformed OOXML. Prohibiting at authoring time converts silent
export failures into loud authoring-time errors.

[¹⁰] **Two PPTX routes:** CSS fidelity and text editability are mutually
exclusive properties in the current OOXML toolchain. PNG-embed preserves
every pixel of the CSS render but produces rasterized, non-editable text.
SVG-to-OOXML preserves text as real text objects but requires faithful
CSS → OOXML shape translation. Both are needed; the caller chooses based on
downstream use.

[¹¹] **`svg2pptx.py` hardened XML parser:** PPTX files are consumed by
document editors (PowerPoint, LibreOffice) in corporate environments. An XML
parser that resolves entities, follows DTDs, or makes network requests creates
XXE attack surface. The hardened parser disables all three.

[¹²] **Scrub-first assimilation:** The repository is a shared, potentially
public artifact. Client names, project names, personal emails, and internal
URLs embedded in committed assets create legal, confidentiality, and
reputational risk that cannot be undone after a push. Scrubbing is a
precondition, not a post-processing step.

[¹³] **Pure-Python Mermaid layout:** Removing the browser dependency from
diagram generation eliminates a class of flaky CI failures (browser not
available, Mermaid.js version pinning, headless Chrome startup races) and
makes output deterministic across environments. Headless diagram generation
is a reproducible-build property.

[¹⁴] **ELK adapter for graph layouts:** Optimal graph layout (minimizing
edge crossings, distributing nodes evenly, respecting port constraints) is
NP-hard. Eclipse Layout Kernel is an industrial-grade implementation with
two decades of production use in IDE diagram editors. Delegating to ELK
avoids reinventing cycle detection, Sugiyama layering, and crossing
minimization — while keeping the Python layout engine as the thin adapter
layer above it.

[¹⁵] **Needs-gathering interview before planning:** The quality gap between
a well-briefed deck and an under-briefed deck is large and irreversible once
rendering starts. The interview is a forcing function: it surfaces assumptions
(audience expertise, desired action, existing objections) that the user holds
implicitly but the system cannot infer from a topic string alone. A hard-stop
interview costs ~2 minutes; a full re-render costs 20–40 minutes.

[¹⁶] **Narrative arc review as a first-class use case:** Deck critique is
valuable independent of deck generation. The same reasoning capability that
plans a deck can critique one — evaluating narrative coherence, evidence
sufficiency, CTA sharpness, and message drift from brief. Producing a
structured feedback document (not slides) serves a real workflow where the
user needs a second opinion, a stakeholder-ready review artifact, or a
quality gate before client delivery.

[¹⁷] **Planning-time speaker notes:** Speaker notes have the highest value
when they capture the facilitation intent at the moment the content reasoning
is live — "why this slide, what question does it answer, what should the
presenter say to bridge from the previous slide." Generating an empty stub
post-render discards that context. Generating notes during planning, then
surfacing them in the proof worksheet, gives the presenter a review and
refinement loop before any LLM render cost is incurred.

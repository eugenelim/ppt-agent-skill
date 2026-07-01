# Spec: persistent_chrome deck flag

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none <!-- the interface surface is the outline deck-global field + the planning-JSON field, both documented in the pipeline playbooks; no contracts/<type>/ artifact -->
- **Shape:** integration <!-- wires an author flag across the outline → planning → page-html stages -->

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A deck author producing a **reference deck** — a runbook, SOP, or playbook the
audience keeps open and scans, rather than watches once — needs every content
page to carry the same orientation chrome so a reader dropping in mid-deck knows
what document they are in and where they are. `persistent_chrome` is a
deck-global flag, set once in the outline, that turns this on: when it is set,
every `content` page renders a **masthead** strip at the top (deck brand /
subtitle / revision) and a **runbook footer** at the bottom, both drawn from the
paste-ready page-chrome recipes in `references/blocks/worksheet.md` group C and
bound to the deck's CSS variables so they re-theme with any style. The flag
defaults **off**, and off it changes nothing — existing decks render exactly as
they do today. The success condition for the author is purely visual and
mechanical: flip the flag on for a runbook, and every content page comes out
with consistent masthead + footer that themes with the chosen style and survives
the headless-render pipeline; leave it off, and the deck is what it was.

This flag is the engine-level realization of the reference-runbook chrome
deferred by the sibling spec (`docs/backlog.md`
§schematic-blueprint-runbook-restyle, 3rd item), which extracted the group-C
recipes but left the flag that renders them per-deck to this spec.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Keep the flag **off by default** — absence of the outline field, or an
  explicit `off`, means no chrome and no change to the page skeleton.
- Reuse the existing `masthead` and `footer` recipes from
  `references/blocks/worksheet.md` group C verbatim in structure; bind them to
  deck CSS variables (`--text-primary`, `--accent-1`, `--card-bg-from`,
  `--font-mono`, `--font-primary`) so they re-theme with any style.
- Propagate the flag along the established stage path: outline deck-global header
  → planning stage records it into planning JSON → page-html stage reads planning
  JSON and emits the chrome. The page-html stage does **not** read the outline.
- When the flag is on, also record the **deck chrome copy** the recipes need
  (`deck_chrome.title` + `deck_chrome.subtitle`, derived from deck metadata the
  planning stage already reads: deck topic/title + outline 核心论点) into every
  page's planning JSON, so the page-html stage fills the masthead/footer text
  slots from deck metadata. Recipe text slots with no deck source (e.g. a
  revision string) are omitted, not invented.
- Restrict the chrome to `content` pages; `cover` / `section` / `toc` / `end`
  keep their existing free-form or skeleton treatment.

### Ask first

- Extending the chrome to page types other than `content` (e.g. `toc`).
- Introducing a *new* chrome recipe, or altering the worksheet group-C recipes'
  structure, rather than reusing them.
- Sourcing masthead/footer copy from anywhere other than deck metadata already
  available to the page-html stage (deck title, outline core thesis).

### Never do

- Never render the chrome with `::before` / `::after` content decorations,
  `mask-image`, `conic-gradient`, `background-clip:text`, SVG `<text>`, or any
  other technique `pipeline-compat.md` forbids — the chrome must be real
  `<div>`/`<span>`/`<footer>` nodes so `html2svg.py` round-trips it.
- Never hardcode a color or font in the emitted chrome — only deck CSS variables
  (the worksheet status-block semantic-signal carve-out does not apply here;
  masthead/footer use theme variables only).
- Never leak the group-C recipes' *sample* copy (e.g. `SCHEMATIC · DELIVERY
  RUNBOOK`, `Engineering Delivery Handbook`, `REV 2.4`, `Delivery Runbook`,
  `Pre-flight · Cadence · Gates`) into a rendered deck — every text slot is
  filled from deck metadata or omitted.
- Never mint a new planning-validator `card_type`, a new `page_type` enum value,
  or a new top-level dependency; the flag is a boolean carried on existing JSON
  and consumed by existing prompt stages.
- Never change the rendered output of a deck that does not set the flag.

## Testing Strategy

- **Flag propagation (outline → planning → page-html wiring):** goal-based
  check. A `grep` across the edited stage docs confirms the field is named and
  carried at each hop with a consistent spelling. This is the *appropriate*
  altitude because the wiring is documentation/prompt content, not runtime logic.
- **Default-off = no change:** goal-based check **plus** recorded manual
  read-through. `grep` proves every masthead/footer emission instruction is
  lexically *inside* a "when `persistent_chrome` is set" conditional (no
  unconditional emission), but `grep` alone **cannot** prove flag-off output is
  byte-identical to today — there is no automated flag-off render diff in the
  gates (a render needs a live subagent run). So the default-off guarantee rests
  on: (a) the grep showing no unconditional emission, and (b) a manual
  read-through, recorded in `plan.md`, confirming the flag-off path adds nothing
  to the rendering instructions.
- **Chrome is pipeline-safe and theme-bound when emitted:** goal-based check.
  The *actual* guarantee is **verbatim reuse** of the group-C recipes, which
  already pass `lint_diagram_recipes.py` (forbidden-technique + hardcoded-color
  scan). `smoke_test.py`'s `::before`/`::after` check is **warning-level, not a
  hard gate** (`smoke_test.py:296-298`) — it is advisory confirmation, not the
  safety net; a future *non-verbatim* edit would not be caught by it.
- **Nav-skeleton exception is coherent:** goal-based check. `design-specs.md` §A
  documents the flag-gated exception with concrete band geometry so a page-html
  agent reading the injected global resources produces the masthead+footer frame
  instead of contradicting the plain-skeleton contract; verified by reading that
  the exception is present, gives positions/heights, and is internally consistent
  (no page is told to render both the plain skeleton and the chrome).

## Acceptance Criteria

- [x] Every masthead/footer emission instruction in the edited stage docs is
  lexically conditioned on `persistent_chrome` being set — `grep` finds no
  unconditional chrome emission — and a manual read-through recorded in `plan.md`
  confirms the flag-off / flag-absent path adds nothing to the rendering
  instructions, so a deck that does not set the flag renders the standard
  `header.slide-header` + `footer.slide-footer` skeleton (`design-specs.md` §A)
  exactly as today. (Grep alone cannot prove byte-identity; the read-through is
  the second half of this criterion.)
- [x] `references/playbooks/outline-phase1-playbook.md` documents
  `持久化页框 (persistent_chrome)` as a deck-global field in the outline header
  format, enumerated `{on / off}`, absent = off, with a pointer that it suits
  参考型 (reference-archetype) decks.
- [x] `references/prompts/step4/tpl-page-planning.md` instructs the planning
  stage to read the outline's `persistent_chrome` value and, when set, record
  both the boolean flag **and** the deck chrome copy (`deck_chrome.title` +
  `deck_chrome.subtitle`, from deck topic/title + outline 核心论点) into every
  page's planning JSON so both reach the page-html stage.
- [x] `references/playbooks/step4/page-html-playbook.md` and
  `references/prompts/step4/tpl-page-html.md` instruct the page-html stage: when
  planning `persistent_chrome` is set **and** `page_type` is `content`, emit the
  `masthead` (top) and `footer` (bottom) recipes from
  `references/blocks/worksheet.md` group C, bound to deck CSS variables, filling
  every text slot from `deck_chrome` + per-page fields (never the recipes' sample
  literals; unsourced slots omitted).
- [x] `references/design-runtime/design-specs.md` §A documents the flag-gated
  exception to the unified nav-skeleton contract with **concrete band geometry**:
  with `persistent_chrome` set, a `content` page pins the masthead as an
  absolute top band, drops `header.slide-header` below it, and pins the runbook
  footer as an absolute bottom band in place of `.slide-footer` — each band with
  a stated position and height, and the content area's usable height reduced
  accordingly (with `density_contract` computed against the reduced height). The
  exception states the invariant that a page renders the plain skeleton **or**
  the chrome frame, never both. With the flag off the contract is unchanged.
- [x] The emitted chrome is pipeline-safe (no `::before`/`::after` content,
  `mask-image`, `conic-gradient`, SVG `<text>`, or hardcoded colors/fonts) and
  carries no group-C sample literals — guaranteed by reusing the worksheet
  group-C recipes verbatim in structure and filling copy from `deck_chrome`.
- [x] Gates pass: `smoke_test.py`, `lint_diagram_recipes.py`, `check_skill.py`.

## Assumptions

- Technical: deck-global outline fields live in the Phase-1 outline header block
  (核心论点/叙事结构/密度倾向/…), so a new deck-global flag lands there (source:
  `references/playbooks/outline-phase1-playbook.md` §"outline.txt 强制格式骨架").
- Technical: the page-HTML stage reads only planning JSON + `style.json`, not the
  outline, so the flag propagates outline → planning JSON → page-html with the
  planning stage as the copy hop (source: `references/prompts/step4/tpl-page-html.md`
  任务包 vs `references/prompts/step4/tpl-page-planning.md` step 1).
- Technical: `planning_validator.py` ignores unknown top-level keys (uses `.get()`,
  warns only on unknown values), so a `persistent_chrome` field won't trip it
  (source: `scripts/planning_validator.py:218-235`).
- Technical: the masthead + footer recipes in `references/blocks/worksheet.md`
  group C are pipeline-safe and deck-variable-bound; `--font-mono` is a canonical
  injected variable (`references/typography.md:96` §4b; every diagram recipe binds
  it) and `--font-serif-italic` is only used with a `var(--font-primary)` fallback
  (source: `references/blocks/worksheet.md` §C).
- Technical: `schematic_blueprint`'s `decorations.masthead:true` is a style-level
  DNA hint, distinct from this deck-level author flag — a reference deck may use
  any style — so `persistent_chrome` is not derivable from the style JSON (source:
  `references/styles/light.md` schematic_blueprint block).
- Process: full-mode spec because the flag crosses the planning public interface;
  the sibling spec deferred it here for exactly that reason (source:
  `docs/backlog.md` §schematic-blueprint-runbook-restyle, 3rd item).
- Design: with the flag on, the masthead is an absolute top band above the
  (downshifted) standard slide-header and the runbook footer is an absolute
  bottom band replacing the plain `.slide-footer`, with concrete geometry and a
  reduced content usable-height fixed in `design-specs.md` §A; scope is `content`
  pages only; masthead/footer copy reaches the page-html stage via a
  `deck_chrome` object the planning stage records (not the outline, which
  page-html never reads); outline field spelled `持久化页框 (persistent_chrome)`,
  absent = off (source: user confirmation 2026-07-01; copy-source gap and
  positioning geometry raised by spec-mode adversarial review 2026-07-01).

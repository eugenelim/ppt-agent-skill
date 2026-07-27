# Spec: preview-html-design-doc

**Mode:** full (structural change — new file in `docs/product/`, AGENTS.md public surface edit, docs/product/README.md update)

- **Status:** Implementing
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** AGENTS.md ~200-line guideline; `docs/product/` "living doc" convention
- **Contract:** none (docs-only)
- **Shape:** docs

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Create `docs/product/DESIGN.md` as the canonical design artifact for the preview
HTML — the single reference for every visual, interaction, and architectural
decision in `html_packager.py`'s output.

Because `docs/product/` is a living layer ("must match current reality"), DESIGN.md
annotates every behavioral claim with its implementation status (`[current]` or
`[planned: <spec-slug>]`). This resolves the inherent tension between capturing the
design target and the living-doc constraint: the doc is always honest about what
exists today, and "planned" sections advance to "current" when the corresponding
PR lands.

Update `docs/product/README.md` to enumerate DESIGN.md as a valid product-layer file.
Update `AGENTS.md` to declare DESIGN.md as a source of truth and enforce maintenance.

## Acceptance Criteria

- [ ] AC1 — `docs/product/DESIGN.md` exists and covers all required sections:
  design intent, architecture constraints (iframe+sandbox, base64 inlining),
  navigation bar (bottom-aligned, evidence cited), controls layout, keyboard
  shortcuts table, slide jump modal, speaker notes panel schema reference,
  print/PDF, and maintenance rule. Every behavioral claim is annotated with
  `[current]` or `[planned: <spec-slug>]`.

- [ ] AC2 — Evidence for bottom nav is cited with ≥ 3 resolvable citations
  (URL or full reference). Required cites: reveal.js + ≥ 2 of (Slidev, Marp,
  Slides.com, Pitch, PowerPoint Web, Keynote), plus Hoober thumb-zone study
  (Smashing Magazine link) or Fitts's Law (CareerFoundry link), plus
  media-player convention.

- [ ] AC3 — `AGENTS.md` Source of truth table gains a row:
  `| What is the preview HTML designed to look/behave like? | \`docs/product/DESIGN.md\` |`
  The row is inside the existing Source of truth table (between the
  `docs/product/` row and the `docs/guides/` row).

- [ ] AC4 — `AGENTS.md` Non-negotiables section gains a "Keep DESIGN.md current"
  bullet immediately after the "Never leak PII" bullet. The bullet names
  `html_packager.py` as the trigger file.

- [ ] AC5 — `AGENTS.md` line delta is ≤ 10 lines added (to accommodate properly
  styled multi-line bullet). The file was already ~363 lines before this PR.

- [ ] AC6 — `docs/product/DESIGN.md` maintenance rule section explicitly names
  `scripts/html_packager.py` as the source whose changes trigger a DESIGN.md update,
  and states that drift is a bug.

- [ ] AC7 — `docs/product/README.md` "What lives here" section lists
  `DESIGN.md — preview HTML design system (layout, interaction, visual conventions)`.

- [ ] AC8 — DESIGN.md contains no client names, project names, real personal names,
  internal URLs, or ticket IDs. Neutral examples only (Acme Corp, example.com, etc.)
  where examples are needed.

## Testing Strategy

Verification mode: Visual/manual QA (doc artifact).

1. Read `docs/product/DESIGN.md`; confirm all AC1 sections present; confirm every
   behavioral claim has a `[current]` or `[planned: ...]` annotation.
2. Confirm ≥ 3 resolvable citations are present for the bottom nav evidence (AC2).
3. `grep "DESIGN.md" AGENTS.md` returns ≥ 2 lines; verify each is in the correct location
   (table row inside Source of truth table; bullet after "Never leak PII" bullet).
4. Count line delta in AGENTS.md: `git diff --stat` shows ≤ 10 lines added.
5. `grep "DESIGN.md" docs/product/README.md` returns ≥ 1 hit.
6. Grep DESIGN.md for any of: real company names, personal emails, internal URLs.
7. Run `.claude/skills/work-loop/scripts/lint-spec-status.py` to check metadata invariants.

## Boundaries

**In scope:**
- `docs/product/DESIGN.md` (new)
- `AGENTS.md` (≤ 10 lines added: 1 table row + 1 multi-line bullet)
- `docs/product/README.md` (1 line addition to "What lives here")

**Out of scope:** `docs/architecture/overview.md`, `CONVENTIONS.md`, CI hooks,
`scripts/html_packager.py`, any other product docs, any code.

**Never do:**
- Touch `scripts/html_packager.py` in this PR
- Add a new dependency
- Embed identifying client/project/personal information in any file
- Move DESIGN.md to a non-product location (it belongs in `docs/product/`)

## Assumptions

1. The `~200-line` AGENTS.md guideline is aspirational — the file already exceeds
   it; the binding constraint is "don't add more than ~10 lines."
2. Bottom nav research findings are authoritative and citable (confirmed by the
   synchronous research agent run before this spec was written).
3. DESIGN.md in `docs/product/` is correct per convention; updating README.md
   to enumerate it resolves the placement ambiguity.
4. Current html_packager.py implements: top toolbar (fixed, dark), Prev/Next
   buttons, N/total counter, arrow-key navigation, iframe sandbox isolation, base64
   image inlining. No slide jump modal, no progress bar, no speaker notes, no print
   CSS exists yet.

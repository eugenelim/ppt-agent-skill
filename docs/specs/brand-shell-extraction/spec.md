# Spec: brand-shell-extraction

**Mode:** full (structural change — new script, new public interface in deck_probe.py, file I/O)

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** none
- **Contract:** none <!-- scripts; no wire contract -->
- **Shape:** mixed

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

A user can hand the skill an external organization's `.pptx` deck and get slides
that read on-brand — same background, header accent, and text colors as the
organization's template — while retaining this repo's typography, card shapes,
layout patterns, narrative arcs, and decoration DNA.

Concretely: `scripts/brand_extract.py <input.pptx> --output <OUTPUT_DIR>/style.json`
reads the brand deck, extracts its visual shell (background, accent, and text
colors) via y-coordinate heuristics, detects light vs. dark mode from background
luminance, selects a built-in base style by mode (defaulting to a named style per
mode; hue refinement deferred), overlays
the brand shell onto that base style's metadata, and writes a complete,
contract-valid `style.json`. Dropping this file into `OUTPUT_DIR` before Step 3.5
uses the organization's shell while the Style subagent (or a direct bypass) fills
in the creative and typographic DNA from the base style.

The extraction logic lives in `deck_probe.py` as a new `probe_pptx_brand()`
function so the existing probe tool also gains a `--brand` diagnostic mode.
No prompt templates, planning schemas, or PPTX write paths are changed.

## Acceptance Criteria

- [x] AC1 — **CLI writes a valid style.json.** `python3 scripts/brand_extract.py
  <input.pptx> --output <path>` exits 0 and the output file passes
  `python3 scripts/contract_validator.py style <path>` with zero errors.

- [x] AC2 — **Light/dark detection.** The canonical luminance source is the slide
  background fill color (read from the Presentation slide background object, solid
  fills only). When no explicit slide background fill is set (theme-inherited),
  fall back to the most-frequent AUTO_SHAPE fill color across all slides. When
  neither is available, detected_mode is `"neutral"`. Given a luminance ≤ 0.18,
  the base style is selected from the dark-mode group (`dark_tech`,
  `xiaomi_orange`, `luxury_purple`, `nocturne_violet`, `cyberpunk_neon`,
  `chrome_y2k`, `noir_film`, `graphite_gold`, `graphite_violet`). Given luminance
  ≥ 0.40, from the light-mode group (`blue_white`, `fresh_green`, `minimal_gray`,
  `mocha_editorial`, `medical_pulse`, `earth_concrete`, `champagne_gold`,
  `liquid_glass`, `editorial_paper`, `schematic_blueprint`). Luminance in
  (0.18, 0.40) or `"neutral"` → `blue_white`. Vibrant, cultural, and natural
  style families are never candidates.

- [x] AC3 — **Typography not extracted.** The generated `style.json` `font_family`
  is derived from the base style's `typography.display_font` (the nested field
  present in all 30 built-in styles); no font names from the PPTX are written to
  the output. A test asserts `font_family` in the output equals the base style's
  `typography.display_font` value.

- [x] AC4 — **No image content extracted.** `PICTURE` shape pixels are never
  accessed; only scalar fill colors from `AUTO_SHAPE`/`FREEFORM` fills and font
  colors from `TextFrame` runs are used.

- [x] AC5 — **Optional footer text.** When `--footer-text` is passed, text runs
  whose top edge is ≥ 90% of the slide height and whose total length is ≤ 60 chars
  are captured and written to a top-level `brand_footer_text` key in the JSON
  (distinct from `css_variables`; not validated by the style contract). When the
  flag is absent, `brand_footer_text` is omitted. A test asserts the key is
  present with `--footer-text` and absent without it.

- [x] AC6 — **Sparse-deck fallback.** When fewer than 3 distinct fill colors are
  detected across the entire PPTX, the output is the base style with only the
  mechanical `decoration_dna.forbidden` trim applied (no shell color overlay); the
  tool exits 0.

- [x] AC7 — **Diagnostic mode.** `python3 scripts/deck_probe.py --brand <file>`
  prints the raw brand-shell extraction (detected_mode, top fill colors with
  luminance values, accent candidates, footer_text_candidates) to stdout and
  writes no files. The diagnostic does not invoke base style selection or
  css_variables mapping (those live in `brand_extract.py`). Exit 0 on success.

- [x] AC8 — **CLI cheatsheet updated.** `references/cli-cheatsheet.md` contains a
  "Brand Shell Override" subsection under Step 3.5 documenting how to run
  `brand_extract.py` as an optional replacement for the Style subagent.

- [x] AC9 — **`--base-style` override.** `brand_extract.py --base-style <style_id>`
  bypasses auto-selection and uses the specified style as the base. If the
  `style_id` is not found in the board files, the tool exits 1 with a clear error
  listing valid IDs. When omitted, auto-selection by detected mode applies.

- [x] AC10 — **`brand_mode` written to output.** The generated `style.json`
  includes a top-level `brand_mode` key with value `"light"`, `"dark"`, or
  `"neutral"` (matching the detected mode). This field is not validated by
  `contract_validator.py`; it is consumed by downstream workflow steps documented
  under `workspace.toml` backlog slug `brand-shell-interview-wiring`.

## Boundaries

### Always do

- Inherit `decoration_dna`, `design_soul`, `mood_keywords`, `variation_strategy`,
  `font_family` from the selected base style verbatim — these fields are never
  derived from the PPTX.
- Override only `css_variables`: `bg_primary`, `bg_secondary`, `text_primary`,
  `text_secondary`, `accent_1`–`accent_4` (8 of the 12 required keys), and only
  when the extracted brand value is a non-empty string (empty values keep the base
  style's value). Retain `card_bg_from`, `card_bg_to`, `card_border`, `card_radius`
  from the base style (card surface is not brand-dictated).
- Normalize `decoration_dna.forbidden` to the first 5 items if the base style has
  more (the contract validator caps it at 5; this is a mechanical compliance trim,
  not a creative change).
- Set `style_id` to `brand_shell_<8-char hex>` (first 8 chars of MD5 of the PPTX
  filename + sorted extracted colors) and `style_name` to `Brand Shell (<slug>)`
  where `<slug>` is the PPTX stem — **except in the AC6 sparse fallback**, which
  preserves the base style's `style_id` and `style_name` unmodified.

### Never do

- Extract font names from PPTX runs into the output JSON.
- Access PICTURE shape raster content.
- Write any files other than the `--output` path (and when `--footer-text` is
  used, only within that same output JSON).
- Require a network connection.
- `pip install` or import any module not already present in the repo's declared
  deps (`python-pptx`, `lxml`, stdlib).
- Process PPTX files over 50 MB (exit 1 with a clear error message before parsing
  begins). XML entity expansion is disabled by passing `resolve_entities=False` to
  lxml when applicable; python-pptx's own zip extraction is trusted as the
  existing codebase already depends on it.
- Modify any prompt template, planning schema, or validator rule.

### Ask first

- Supporting PDF, HTML, or image brand sources (PPTX-only in V1).

## Testing Strategy

| AC | Task | Verification mode | Mechanism |
|----|------|-------------------|-----------|
| AC1 | `brand_extract.py` CLI, valid output | Goal-based | `contract_validator.py style <out>` exits 0 against dark + light fixtures |
| AC1 | partial-population path | Goal-based | 3-fill/theme-text fixture → `contract_validator.py style` exits 0 |
| AC2 | luminance detection | TDD | unit tests: dark hex → "dark", light hex → "light", gray → "neutral" |
| AC2 | base style selection | TDD | dark bg → `dark_tech`, light bg → `blue_white`, neutral → `blue_white` |
| AC3 | typography not extracted | Goal-based | `test_font_family_from_base_not_pptx`: run CLI against fixture, assert output `font_family` == base `typography.display_font` |
| AC4 | no image content | TDD | `test_no_picture_access`: PICTURE-only PPTX → `BrandShell.sparse == True`, no pixel read (unit-level) |
| AC5 | footer text present/absent | Goal-based | `test_footer_text_present_with_flag`, `test_footer_text_absent_without_flag`: run CLI against fixture |
| AC6 | sparse fallback | Goal-based | 1-color PPTX → output `style_id` == base style id; `brand_mode` == detected_mode; `contract_validator` exits 0 |
| AC7 | `deck_probe.py --brand` no writes | Goal-based | run, assert no new files; stdout contains `detected_mode` |
| AC8 | cli-cheatsheet updated | Goal-based | `grep -q "Brand Shell Override" references/cli-cheatsheet.md` |
| AC9 | `--base-style` override (cross-mode) | Goal-based | light fixture + `--base-style dark_tech` → base metadata is `dark_tech` (forces non-auto style) |
| AC9 | `--base-style` unknown ID | Goal-based | `brand_extract.py fixture.pptx --base-style nonexistent` exits 1 |
| AC10 | `brand_mode` dark/light paths | Goal-based | `test_brand_mode_in_output`: dark fixture → `brand_mode == "dark"`; light → `"light"` |
| AC10 | `brand_mode` neutral path | TDD | unit test: `merge_shell(base, BrandShell(detected_mode="neutral"), "x")["brand_mode"] == "neutral"` |
| — | color mapping heuristics | TDD | unit tests: header threshold (EMU), footer ratio, accent index mapping |

A fixture PPTX (`tests/fixtures/brand-probe-fixture.pptx`) is created in task 0
so all goal-based tasks have a deterministic, repo-committable input.

## Assumptions

1. `python-pptx` is already installed (declared repo dep; confirmed in `deck_probe.py`
   import guard).
2. Base style JSON blocks are parseable from the 5 named board files in
   `references/styles/` (`dark.md`, `light.md`, `vibrant.md`, `cultural.md`,
   `natural.md`) by extracting fenced ` ```json ` blocks and filtering to objects
   with a `style_id` key. The loader resolves paths as `refs_dir / "styles" /
   board_file`, where `refs_dir` defaults to `SKILL_DIR/references`. `README.md`,
   `index.md`, and `runtime-style-rules.md` are never read. De-duplication by
   `style_id` is applied.
3. WCAG 2.1 relative luminance formula (`L = 0.2126 R + 0.7152 G + 0.0722 B` with
   linearization) is sufficient for dark/light discrimination; no perceptual
   color-science library is needed.
4. The 12 `css_variables` → nested JSON field mapping is stable for all 30 built-in
   styles (confirmed in `dark_tech`). Mapping includes: `accent.primary[0]` →
   `accent_1`, `accent.primary[1]` → `accent_2`, `accent.secondary[0]` →
   `accent_3`, `accent.secondary[1]` → `accent_4`; `card.border_radius` (int) →
   `card_radius` as f"{n}px"; `typography.display_font` → top-level `font_family`.
5. The brand deck's slides use solid fills on background shapes (the dominant
   corporate PPTX pattern); gradient-fill-only decks trigger the sparse-deck
   fallback (AC6) gracefully.

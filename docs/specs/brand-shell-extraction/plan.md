# Plan: brand-shell-extraction

- **Spec:** [`spec.md`](spec.md)
- **Status:** Drafting

## Constraints

- No new Python dependencies beyond `python-pptx` + stdlib (already-present deps).
- All output is ephemeral in `OUTPUT_DIR` (gitignored); no repo files other than
  the implementation and the cheatsheet update are committed.
- `deck_probe.py` must remain usable as a standalone script after changes (no new
  required imports at module level).

## Risks

- **Style JSON parsing from .md files:** the regex approach for extracting JSON
  code blocks from the 5 style boards needs to handle the multi-style-per-file
  layout. Risk: a malformed block fails silently. Mitigation: the loader function
  logs a warning per skipped block and falls back to the hardcoded default style
  (`blue_white` / `dark_tech`) if the board parse yields zero styles.
- **y-coordinate heuristics for accent color:** shapes used as header bars vary
  widely across corporate templates. The `shape.top < slide_height * (80/720)`
  ratio (~11% of slide height) is a reasonable heuristic; edge cases gracefully
  collapse into the fill pool without a hard failure.
- **Gradient fills:** `python-pptx` can't always read gradient fill colors. The
  code wraps per-shape fill access in a bare `except Exception` (matching the
  existing `deck_probe.py` pattern) and silently skips non-solid fills.

## Declined

- **Modifying prompt templates** (`tpl-style-phase1.md`) to inject brand
  constraints into the Style subagent — would couple this feature to the prompt
  authoring system; the standalone `brand_extract.py` → `style.json` bypass is
  sufficient.
- **Supporting PDF/HTML/image brand sources** in this PR — the PPTX path covers
  the dominant corporate use-case; other formats defer.
- **Wiring `--brand-deck` into the interview QA** — requires prompt changes and
  is a separate multi-loop spec; deferred to `workspace.toml [backlog].open`
  (slug: `brand-shell-interview-wiring`).
- **Per-style `css_snippets` merging** — the 30 built-in styles don't uniformly
  define `css_snippets`; inheriting it verbatim from the base style is correct.
- **A brand profile as a committed repo asset** — all output is ephemeral.
- **Hue-based base style selection** — computing hue distance in HSL space adds
  complexity without a strong signal (the 30 styles span a huge hue range);
  mode detection (light/dark) is the dominant axis. Hue refinement deferred.

## Design

No direct lxml parsing occurs anywhere in this feature — python-pptx handles all
zip extraction and XML deserialization internally. The `resolve_entities=False`
boundary in the spec is satisfied by not applying: lxml is never called directly.

### Architecture

Two new files, one function addition:

```
scripts/
  deck_probe.py          # existing — add probe_pptx_brand() + --brand mode
  brand_extract.py       # new — CLI wrapper: PPTX → style.json
tests/
  test_brand_extract.py  # new — unit + goal-based tests
  fixtures/
    brand-probe-fixture.pptx   # new — synthetic fixture built once in task 0
references/
  cli-cheatsheet.md      # existing — add Brand Shell Override subsection
```

### Color extraction algorithm (in `probe_pptx_brand()`)

Luminance source (canonical, per AC2):
```
1. Try to read slide background fill for each slide:
   background_fills = [slide.background.fill for slide in prs.slides
                       if fill is solid and has rgb]
   bg_candidate = most_common(background_fills) if background_fills else None

2. If bg_candidate is None:
   # theme-inherited background — fall back to most-frequent AUTO_SHAPE fill
   bg_candidate = most_common(all_shape_fills) if all_shape_fills else None

3. If bg_candidate is None → detected_mode = "neutral"
   Else → bg_primary = bg_candidate; compute luminance → set detected_mode
```

Per-slide shape loop:
```
4. For each slide, for each shape:
   a. AUTO_SHAPE / FREEFORM with solid fill:
      - shape.top < slide_height * (80/720)  [ratio ~11%, EMU-safe] → header_accent_pool
      - always → shape_fills counter (for bg fallback above)
   b. TextFrame runs:
      - font color (solid) → text_colors counter
      - shape.top ≥ 0.9 * slide_height AND len(text) ≤ 60 → footer_text_candidates list
      (all shape coordinates are EMU; comparisons are ratios or ratio-derived, no px conversion needed)
      (skip PICTURE shapes entirely — no pixel access)
```

Field resolution (BrandShell fields are "" when the source is unavailable —
merge_shell skips overrides for empty values, keeping base_css intact):
```
5. bg_secondary = second-most-frequent shape_fill color (excluding bg_primary);
   "" if fewer than 2 distinct shape_fills
6. accent_1 = most-frequent header_accent_pool color; "" if pool is empty
   accent_2 = second-most-frequent header_accent_pool color; "" if pool has < 2
   fallback attempt: if accent_1 is "", use top shape_fills that differ from
   bg_primary by luminance ≥ 0.20 (probe only; merge still handles "" gracefully)
7. text_primary = most-frequent text_color; "" if no text runs with solid colors
   text_secondary = second-most-frequent text_color; "" if fewer than 2
8. accent_3, accent_4 = next two distinct shape_fill colors after bg_primary,
   bg_secondary, accent_1, accent_2; "" if not enough distinct colors
9. Accent index mapping in nested_to_css_variables (base-style fields only):
   accent.primary[0]→accent_1, primary[1]→accent_2,
   secondary[0]→accent_3, secondary[1]→accent_4
10. footer_text = footer_text_candidates[0] if footer_text_candidates else ""
    (first candidate in slide/shape iteration order; empty string when none)

Sparse guard: if len(distinct shape_fills) < 3 → BrandShell(sparse=True)
(note: even non-sparse decks may produce "" for some fields; merge handles it)
```

### Base style selection (in `brand_extract.py`)

```
1. Load from the 5 named board files only (never glob *.md):
   ["dark.md", "light.md", "vibrant.md", "cultural.md", "natural.md"]
   Paths: refs_dir / "styles" / board_file
   (refs_dir defaults to SKILL_DIR/references; boards live in references/styles/)
   Extract fenced ```json blocks → parse → filter to dicts with a style_id key
   De-dup by style_id (first occurrence wins)

2. Partition by category value:
   dark_candidates  = styles where category == "dark_professional"
   light_candidates = styles where category == "light_premium"
   (vibrant / cultural / natural families are never candidates)

3. Based on BrandShell.detected_mode:
   - "dark"    → candidates = dark_candidates,  default_id = "dark_tech"
   - "light"   → candidates = light_candidates, default_id = "blue_white"
   - "neutral" → candidates = light_candidates, default_id = "blue_white"

4. Return the style whose style_id == default_id for V1
   (hue-distance refinement within the group is deferred)
   Fallback if default_id not found: return first style in candidates group;
   if group is empty: return None (caller handles via sys.exit(1) in main())

Note: `select_base_style` never calls `sys.exit`; both the override-not-found
and empty-group paths return None so the function remains unit-testable.
```

### `nested_to_css_variables()` mapping

Deterministic, hardcoded. Covers all 12 required keys plus `font_family`:

```python
def nested_to_css_variables(style: dict) -> tuple[dict, str]:
    """Returns (css_variables dict, font_family string)."""
    bg = style["background"]
    card = style["card"]
    text = style["text"]
    acc = style["accent"]
    typo = style["typography"]
    css = {
        "bg_primary":    bg["primary"],
        "bg_secondary":  bg["gradient_to"],
        "card_bg_from":  card["gradient_from"],
        "card_bg_to":    card["gradient_to"],
        "card_border":   card["border"],
        "card_radius":   f"{card['border_radius']}px",   # int → string
        "text_primary":  text["primary"],
        "text_secondary": text["secondary"],
        "accent_1": acc["primary"][0],
        "accent_2": acc["primary"][1],
        "accent_3": acc["secondary"][0],
        "accent_4": acc["secondary"][1],
    }
    font_family = typo["display_font"]
    return css, font_family
```

### Merge algorithm

```
base_json = parsed base style JSON (nested format from board .md files)
base_css, base_font = nested_to_css_variables(base_json)

# Normalize decoration_dna.forbidden to ≤5 items (validator cap is 2–5)
dna = deepcopy(base_json["decoration_dna"])
if isinstance(dna.get("forbidden"), list) and len(dna["forbidden"]) > 5:
    dna["forbidden"] = dna["forbidden"][:5]

output = {
  # metadata from base (verbatim, forbidden trimmed to ≤5 for validator compliance)
  "mood_keywords":      base_json["mood_keywords"],
  "design_soul":        base_json["design_soul"],
  "variation_strategy": base_json["variation_strategy"],
  "decoration_dna":     dna,
  # identity overridden
  "style_id":   "brand_shell_" + md5_hex[:8],
  "style_name": f"Brand Shell ({pptx_stem})",
  # font from base (derived from typography.display_font by nested_to_css_variables)
  "font_family": base_font,
  # css_variables: start from base (all 12 valid); override only populated brand values
  # probe may return "" for keys with no source (theme-inherited fills, no text runs)
  "css_variables": {
    **base_css,
    **{k: v for k, v in {
      "bg_primary":     brand_shell.bg_primary,
      "bg_secondary":   brand_shell.bg_secondary,
      "text_primary":   brand_shell.text_primary,
      "text_secondary": brand_shell.text_secondary,
      "accent_1":       brand_shell.accent_1,
      "accent_2":       brand_shell.accent_2,
      "accent_3":       brand_shell.accent_3,
      "accent_4":       brand_shell.accent_4,
    }.items() if v},  # only override when brand value is a non-empty string
  },
  # brand_mode: consumed by interview-wiring spec (Step 3.5 bypass, Step 4 diagram theme)
  "brand_mode": brand_shell.detected_mode,
}
# BrandShell.footer_text is the first footer_text_candidate in iteration order
# (empty string when no candidates found)
if footer_text_flag and brand_shell.footer_text:
    output["brand_footer_text"] = brand_shell.footer_text
```

In the sparse case (`brand_shell.sparse == True`): apply the same `forbidden`
trim, skip the shell color overlay, and preserve the base style's identity:
```
dna = deepcopy(base_json["decoration_dna"])
if isinstance(dna.get("forbidden"), list) and len(dna["forbidden"]) > 5:
    dna["forbidden"] = dna["forbidden"][:5]
output = {
  "style_id":           base_json["style_id"],
  "style_name":         base_json["style_name"],
  "mood_keywords":      base_json["mood_keywords"],
  "design_soul":        base_json["design_soul"],
  "variation_strategy": base_json["variation_strategy"],
  "decoration_dna":     dna,
  "font_family":        base_font,
  "css_variables":      base_css,
  "brand_mode":         brand_shell.detected_mode,
}
```

## Tasks

### Task 0 — Fixture PPTX

**Depends on:** none  
**Verification:** Goal-based  
**Done when:** `tests/fixtures/brand-probe-fixture.pptx` exists, is readable by
`python-pptx`, has ≥ 3 slides with distinct fill colors on at least 2 slides, and
its background fill luminance is < 0.18 (dark fixture).

Build it programmatically via `python-pptx` in a throwaway script (do not commit
the build script). The fixture must be deterministic (no random values) and small
(≤ 20 KB). It serves as the shared fixture for all goal-based tests and AC2.

A second lightweight fixture (`brand-probe-light-fixture.pptx`) has background
luminance ≥ 0.40 for the AC2 light-mode branch.

### Task 1 — `probe_pptx_brand()` in `deck_probe.py`

**Depends on:** Task 0 (fixture available for tests)  
**Verification:** TDD  
**Tests:** `tests/test_brand_extract.py`

```python
# Red stubs — write these first, confirm they fail, then implement

def test_luminance_dark():
    # hex "#050b1f" → relative luminance ≤ 0.18 → detected_mode == "dark"
    ...

def test_luminance_light():
    # hex "#F5F5F5" → relative luminance ≥ 0.40 → detected_mode == "light"
    ...

def test_luminance_neutral():
    # hex "#808080" → luminance in (0.18, 0.40) → detected_mode == "neutral"
    ...

def test_sparse_flag():
    # PPTX with only 1 distinct fill color → BrandShell.sparse == True
    ...

def test_header_accent_y_threshold():
    # shape.top = slide_height * 0.05 → goes into header_accent pool
    # shape.top = slide_height * 0.20 → not in header_accent pool
    ...

def test_footer_text_y_threshold():
    # text run at y ≥ 0.9 * 720 = 648px, len ≤ 60 → captured in footer_text_candidates
    # text run at y = 500px → not captured
    ...

def test_no_picture_access():
    # PPTX with PICTURE shapes only → fill_colors empty, sparse=True
    ...

def test_theme_inherited_bg_fallback():
    # PPTX with no explicit slide background fill → bg from most-frequent shape fill
    ...

```

Approach:
- Add `BrandShell` dataclass (stdlib `dataclasses`) to `deck_probe.py`.
- Add `_relative_luminance(hex_color: str) -> float` pure function.
- Add `probe_pptx_brand(path: Path, footer_text: bool) -> BrandShell` — wraps
  the per-slide loop with the extraction algorithm above.
- Keep all new code after the existing `probe_pptx()` function; preserve the
  existing function signature unchanged.

### Task 2 — `scripts/brand_extract.py`

**Depends on:** Task 1  
**Verification:** Goal-based  
**Done when:**
1. `python3 scripts/brand_extract.py tests/fixtures/brand-probe-fixture.pptx \
   --output /tmp/brand_test_style.json` exits 0.
2. `python3 scripts/contract_validator.py style /tmp/brand_test_style.json` exits 0.
3. `python3 scripts/brand_extract.py tests/fixtures/brand-probe-light-fixture.pptx \
   --output /tmp/brand_light_style.json` exits 0 and the `style_id` starts with
   `brand_shell_`.

Includes:
- `_load_styles_from_boards(refs_dir: Path) -> list[dict]` — parses JSON from
  the 5 named board files only: `dark.md`, `light.md`, `vibrant.md`,
  `cultural.md`, `natural.md`. Paths resolved as `refs_dir / "styles" / name`.
  Never globs `*.md`. De-dups by `style_id` (first occurrence wins). Returns
  list of style dicts with a `style_id` key.
- `_nested_to_css_variables(style: dict) -> dict` — hardcoded mapping from nested
  style format to the 12 flat `css_variables` keys.
- `select_base_style(shell: BrandShell, styles: list[dict], override_id: str | None) -> dict | None`
  — when `override_id` is set, returns the matching style dict or `None` if not found.
  Otherwise does mode-based selection with named default fallback (`dark_tech`/`blue_white`).
  Never calls `sys.exit`; the caller (`main()`) is responsible for `sys.exit(1)` on `None`.
  This keeps the function unit-testable without `SystemExit` patching.
- `merge_shell(base: dict, shell: BrandShell, pptx_stem: str) -> dict` — produces
  the final output dict; always includes `brand_mode` at the top level.
- `main()` — argument parsing (`argparse`: `input_pptx`, `--output`, `--refs-dir`,
  `--footer-text`, `--base-style`), calls probe → select → merge → write → validate.
  When `select_base_style` returns `None`:
  - If `--base-style` was passed: print `"Error: unknown style_id '<id>'. Valid IDs: <sorted list>"` → exit 1.
  - Otherwise (empty candidates group, i.e., board loader failure): print
    `"Error: no candidate styles found for mode '<mode>'. Check board files."` → exit 1.
  Post-write: calls `validate_style` from `contract_validator`; on failure prints errors and exits 1.

Tests (in `test_brand_extract.py`):

```python
def test_brand_extract_dark_fixture(tmp_path):
    # run against dark fixture, assert contract_validator exits 0
    ...

def test_brand_extract_light_fixture(tmp_path):
    # run against light fixture, assert style_id starts with "brand_shell_"
    # and base is from light family (blue_white)
    ...

def test_sparse_fallback(tmp_path):
    # synthetic 1-fill-color PPTX → output style_id == base style style_id (unmodified)
    # AND output["brand_mode"] == brand_shell.detected_mode (sparse branch also writes brand_mode)
    ...

def test_font_family_from_base_not_pptx(tmp_path):
    # output["font_family"] == base_style["typography"]["display_font"]
    # (no font extracted from PPTX)
    ...

def test_footer_text_present_with_flag(tmp_path):
    # --footer-text → "brand_footer_text" key present in output
    ...

def test_footer_text_absent_without_flag(tmp_path):
    # no --footer-text → "brand_footer_text" key absent from output
    ...

def test_file_size_cap(tmp_path):
    # file > 50 MB → brand_extract.py exits 1 before parsing
    ...

def test_partial_population_stays_contract_valid(tmp_path):
    # PPTX with exactly 3 distinct fill colors and theme-inherited (non-solid)
    # text-run colors → brand values for text_primary/text_secondary are ""
    # → merge keeps base_css values → contract_validator.py style exits 0
    ...

def test_base_style_override(tmp_path):
    # light fixture (auto-selects blue_white) + --base-style dark_tech
    # → output mood_keywords/design_soul matches dark_tech board entry (not blue_white)
    # proves override fires against auto-selection, not just corroborates it
    ...

def test_base_style_unknown_id(tmp_path):
    # --base-style nonexistent_id → exits 1; stderr/stdout contains list of valid IDs
    ...

def test_brand_mode_in_output(tmp_path):
    # dark fixture → output["brand_mode"] == "dark"
    # light fixture → output["brand_mode"] == "light"
    ...

def test_nested_to_css_variables_card_radius_is_string():
    # nested card.border_radius=8 → css_variables["card_radius"] == "8px"
    ...

def test_nested_to_css_variables_accent_indices():
    # accent.primary[0]→accent_1, primary[1]→accent_2,
    # secondary[0]→accent_3, secondary[1]→accent_4
    ...

def test_brand_mode_neutral_in_merge_output():
    # pure unit: merge_shell(base_style_dict, BrandShell(detected_mode="neutral"), "x")
    # → output["brand_mode"] == "neutral"; no fixture PPTX needed
    ...

def test_select_base_style_empty_candidates_returns_none():
    # select_base_style called with styles=[] → returns None (loader failure path)
    # main() is responsible for sys.exit(1) with a clear message on None
    ...
```

### Task 3 — `deck_probe.py --brand` diagnostic mode

**Depends on:** Task 1  
**Verification:** Goal-based  
**Done when:**
1. `python3 scripts/deck_probe.py --brand tests/fixtures/brand-probe-fixture.pptx`
   exits 0 and stdout contains `BRAND_SHELL`, `detected_mode`, and `bg_primary`.
2. No new files appear in the working directory after the run.
3. `brand_extract` is not imported by `deck_probe.py` (confirmed by grep).

Approach: add `--brand` flag to `deck_probe.py main()`. When set, call
`probe_pptx_brand()` and print a formatted summary of the raw `BrandShell` fields
(detected_mode, luminance value, fill colors, header_accent candidates, text
colors, footer_text_candidates). Do **not** invoke base style selection or
`nested_to_css_variables` — those live in `brand_extract.py` to avoid circular
imports. No other changes to existing `main()` logic.

### Task 4 — `references/cli-cheatsheet.md` update

**Depends on:** none (docs change)  
**Verification:** Goal-based  
**Done when:** `grep -q "Brand Shell Override" references/cli-cheatsheet.md` exits 0.

Add a "**Step 3.5.B Brand Shell Override (optional)**" subsection immediately after
the existing Step 3.5 gate-validation block. The subsection explains:
1. When to use: when the user provides an organization's `.pptx` as a brand
   reference and wants the output to use its color shell.
2. The command: `python3 SKILL_DIR/scripts/brand_extract.py <brand.pptx>
   --refs-dir SKILL_DIR/references --output OUTPUT_DIR/style.json`
3. What it replaces: run this **instead of** launching the Style subagent
   (Step 3.5 A); the contract_validator gate still applies.
4. What it preserves: typography, card shapes, decoration DNA from the closest
   built-in base style; no fonts or images from the brand deck.

## Test plan

All tests live in `tests/test_brand_extract.py`. Run with:

```bash
cd /path/to/repo
python -m pytest tests/test_brand_extract.py -v
```

No browser, snapshot, or external-reference markers needed — this is pure-Python
unit + goal-based testing.

## Rollout

No migration needed. `brand_extract.py` is additive; existing `deck_probe.py`
behavior is unchanged (new function, new flag, no modification to existing code
paths). The cheatsheet update is documentation-only.

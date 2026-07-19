# EXTRACT STYLE + UPDATE INDEXES

Only when CLASSIFY chose **new style** or **restyle**. For **primitives-only**
(the source matches an existing style), skip this whole file — record the match
in the run spec and go to `extract-primitives.md`.

## The style JSON (15 required keys)

A style is a fenced ` ```json ` block in a board file
(`references/styles/{light,dark,vibrant,cultural,natural}.md`) under a numbered
`## N. <style_id>` heading. `scripts/gallery.py` auto-discovers any ` ```json `
block containing `style_id`; `tools/smoke_test.py` enforces these **15 keys**
(`STYLE_REQUIRED_FIELDS`):

`style_id` · `style_name` · `category` · `inspiration` · `mood_keywords`
(≥3) · `design_soul` · `variation_strategy` · `decoration_dna` · `background` ·
`card` · `text` · `accent` · `typography` · `decorations` · `font_imports`.

Sub-field rules the validator also checks:

- `category` ∈ {`dark_professional`, `light_premium`, `vibrant`,
  `cultural_oriental`, `natural_retro`}.
- `decoration_dna` = `{signature_move, forbidden (≥3 items), recommended_combos}`.
- `accent.primary` = a list of **≥2** colors.
- `typography` includes at least `display_font`, `body_font`,
  `display_letter_spacing`, `tabular_nums`; use a **3-tier font stack**
  (commercial → Google → system) and real `font_imports` URLs.
- `background` / `card` / `text` carry the full color set the mocks bind to.

Model the new block on the closest existing one in the target board file (open
it and mirror its shape). Keep the palette faithful to the source but **strip
any brand/product color name** from prose fields — describe hues, not brands.

## The N-point styling spec

Beyond the JSON, capture the source's *fine* styling as a numbered **styling
spec** section in the board file (as `graphite_gold` §8 and `schematic_blueprint`
§10 do): border-rule hierarchy, focus-color discipline, `<em>`/emphasis
treatment, letter-spacing ladder, spacing rhythm, tabular numerals, any
signature decoration. This is what makes a re-implementation faithful; the JSON
alone underspecifies it.

## Update every index counter and row

A new style touches counters in **two** places — miss one and the docs drift:

**Board file** (`references/styles/<board>.md`):
- line 1 header count — `# …（N 风格）` → `N+1`.
- the 索引 table — add a row `| # | \`style_id\` | 灵感 | 一句话 |`.

**`references/styles/index.md`:**
- line 1 total — `# 风格系统索引（N 风格 / 5 板块）` → `N+1`.
- the 全景表 (panorama) — add a row `| # | style_id | 板块 | 灵感 | 适用场景 | 板块文件 |`.
- the 板块决策矩阵 (decision matrix) — add/adjust a `主题关键词 → 推荐板块 → 默认风格`
  row if the new style is the natural default for a keyword.

## Quality self-check + gate

Run the 7-point self-check in `references/styles/index.md §5` (all 15 fields;
CSS vars complete; 3-tier font stack; ≥3 `forbidden`; valid `font_imports`; mock
renders at 1280×720; `smoke_test.py --style <id>` passes). The mechanical gate is:

```bash
python3 tools/smoke_test.py --style <style_id>
```

which re-validates the JSON, the mock's pipeline-safety, and typography.

## Restyle vs. no-new-style

- **Restyle** — you rewrite an existing style's JSON + styling spec to the new
  language; the counters don't change (no new style), but the board file's row
  one-liner and the mock do. Scope stays limited to that one style.
- **No-new-style (primitives-only)** — do **not** edit board files or `index.md`
  at all. Record "matches `<style_id>` — no new style, because <palette/type/DNA
  match>" in the run spec, and proceed to primitives + icons.

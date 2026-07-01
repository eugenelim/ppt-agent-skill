# EXTRACT PRIMITIVES

Lift the source's reusable UI *structures* — argument cards, worksheets, phase
bands, architecture canvases, callouts, page chrome — into paste-ready block
recipes. Primitives load via the existing **`block_refs`** mechanism (a card
writes `resources.block_refs: ["<name>"]` to pull the recipe); **never mint a new
validator `card_type`/`page_type`** (a public-interface change — defer to
`docs/backlog.md`).

## Recipe format (enforced by `lint_diagram_recipes.py`)

Each recipe is a section headed `### <name> (<id>)` carrying **five bold
markers, fixed order**:

1. `**何时用**` — one line: when to use it.
2. `**数据格式**` — the JSON data shape the recipe consumes.
3. `**模板**` (or `**HTML 模板**`) — ≥1 paste-ready HTML/CSS block.
4. `**自检**` — a self-check list.
5. `**管线安全**` — the pipeline-safety checklist.

Lead with the paste-ready block; prose is captions, not essays.

## Theme-binding + pipeline-safety (both linted)

- **Bind to deck CSS variables** — colors/fonts reference `var(--…)` (focus =
  `var(--accent-1)`, hairline = `var(--card-border)`, etc.); the recipe recolors
  with `:root`. Hardcoded hex/rgb is flagged (only the tiny trend/status
  whitelist in the lint is exempt, and only for genuine semantic signals).
- **No forbidden techniques** in any code block: SVG `<text>`, `conic-gradient`,
  `mask-image`, `background-clip:text`, `mix-blend-mode`, `::before`/`::after`
  with visual `content:`, `stroke-dashoffset`, CSS border-triangle. Arrows use
  real `<polygon>`/`<polyline>`; connectors real `<div>`/SVG `<line>`; labels
  HTML overlay. This is the same forbidden set as `references/pipeline-compat.md`.
- **Icons inline.** When a recipe embeds an icon, paste the `<svg>` **inline,
  verbatim** (never `url()`/`<img>`); see `extract-icons.md`.

## Where the recipe lives — extend a family first

`lint_diagram_recipes.py` auto-globs `references/blocks/diagram*.md`, plus the
explicit list `timeline.md`, `worksheet.md`, `advisory-brief.md`.

- **Prefer extending an existing family file.** If the primitive is an
  architecture/flow/project/concept diagram, add the recipe *into* the matching
  `references/blocks/diagram-*.md` (e.g. an icon-node layered canvas belongs in
  `diagram-architecture.md`, alongside `architecture-component`/`-deployment`/
  `er-data-model`/`layers`). It is auto-globbed — no target-list edit, no orphan,
  no duplicate.
- **Standalone file only with justification.** A distinct primitive *kit* tied
  to one style (as `worksheet.md` is to `schematic_blueprint`, `advisory-brief.md`
  to `graphite_gold`) earns its own `references/blocks/<name>.md`, grouped
  A/B/C. Then you **must**: register it in `references/blocks/README.md` as a
  `按需加载` companion (a row + a short "which style it fits + where its styling
  spec lives" paragraph), and **append it to the target list in
  `scripts/lint_diagram_recipes.py`** (~line 201-206) — a non-`diagram*` filename
  is otherwise never linted.

## Gate

```bash
python3 scripts/lint_diagram_recipes.py
```

must pass with the recipe present (5 markers, no forbidden techniques,
CSS-var-bound). If you added a standalone file, confirm it appears in the lint's
target list (the run will lint it) and is registered in `blocks/README.md`.

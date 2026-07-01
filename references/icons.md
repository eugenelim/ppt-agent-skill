# SVG 图标库 · Icon library

The repo's own **searchable, growing** icon set. Icons are **idea-level
re-drawings** — we take the *concept* an icon expresses (a database, a pipeline,
a model) and draw our own clean monoline glyph. We never trace or byte-copy a
source glyph. The library grows mainly through the `assimilate-slides` skill's
**EXTRACT ICONS** phase, which harvests the concepts a deck's diagrams lean on
and redraws them here.

- **Search / validate:** `scripts/icon_search.py` (stdlib, CI-capable).
- **Metadata:** `assets/icons/catalog.json` · **SVGs:** `assets/icons/<id>.svg`.

## Authoring contract

Every icon is one pipeline-safe, theme-binding SVG:

- **Grid & weight.** `viewBox="0 0 24 24"`, monoline, `stroke-width` ~1.5–2,
  `stroke-linecap="round"` + `stroke-linejoin="round"`. One `<svg>` root.
- **Theme-binding paint only.** `stroke`/`fill` are `currentColor`, `none`,
  `inherit`, `transparent`, or `var(--…)` — **never a hardcoded hex/rgb/name**.
  This is what lets an icon recolor with the deck's `:root` (it inherits the
  node's text color). `--validate` fails a hardcoded paint.
- **Pipeline-safe.** No SVG `<text>` (label via HTML overlay if needed), and
  none of the forbidden techniques in
  [`pipeline-compat.md`](pipeline-compat.md) (`mask-image`, `conic-gradient`,
  `mix-blend-mode`, `background-image:url()`, `background-clip:text`,
  `filter:blur()`). Arrowheads/shapes use real `<polyline>`/`<polygon>`/
  `<path>`/`<circle>`/`<rect>` — the same rules the diagram recipes follow.

## Idea-not-copy provenance rule

Absorbing an external deck reproduces only *reusable form* (AGENTS.md §39). For
icons that means: redraw the **idea**, strip the source's identity. The catalog
`provenance` field is a **generic** string (`"assimilated: <generic deck
descriptor> (idea-level redraw)"`, or `"foundational (library seed)"`) — never a
client, product, or deck name.

## Delivery — inline, verbatim

Icons compose into mocks by pasting the `<svg>` **inline, verbatim** into the
HTML. Do **not** reference them with `background-image:url()` or `<img src>` —
both are lossy or forbidden in the html→svg→pptx pipeline. Because the paint is
`currentColor`, an inlined icon takes the color of its container
(`color: var(--accent-1)` on the node → the icon is accent-colored).

`python3 scripts/icon_search.py <query> --snippet` prints the inline `<svg>` for
the top hit, ready to paste.

## Catalog entry

```json
{
  "id": "database",           // kebab-case, == <id>.svg filename stem
  "name": "Database",
  "category": "infrastructure",   // one of catalog.json "categories"
  "tags": ["data", "storage", "db"],
  "keywords": ["datastore", "sql", "persistence"],
  "viewBox": "0 0 24 24",
  "file": "database.svg",
  "provenance": "foundational (library seed)"
}
```

`tags` are the primary search surface (ranked above `keywords`); `keywords` are
softer synonyms so a search still lands even when the exact tag isn't guessed.

## Usage

```bash
python3 scripts/icon_search.py database          # search id/name/tags/keywords
python3 scripts/icon_search.py "data flow" --json # machine-readable results
python3 scripts/icon_search.py database --snippet # inline <svg> for the top hit
python3 scripts/icon_search.py --list [--category infrastructure]
python3 scripts/icon_search.py --validate         # catalog↔file + pipeline-safety gate
```

## Contributing a new icon

1. Redraw the concept per the authoring contract (idea-level, `currentColor`).
2. Save `assets/icons/<id>.svg`; add its `catalog.json` entry.
3. `python3 scripts/icon_search.py --validate` must exit 0.
4. Search for the concept to confirm it's discoverable.

# EXTRACT ICONS

Grow the repo's searchable SVG icon library with the concepts the source's
diagrams lean on. The authoring contract, catalog schema, provenance rule, and
search/validate usage are canonical in **[`references/icons.md`](../../../../references/icons.md)**
(repo `references/icons.md`) — this file is just the assimilation workflow.

## Workflow

1. **List the icon *ideas*.** From INGEST, the source's `FREEFORM` clusters and
   repeated glyphs name the concepts its diagrams rely on (e.g. database,
   pipeline, model, dashboard, api, storage, security, users, sync, document).
   You want the *concepts*, not the artwork.

2. **Search first, redraw only the gaps.** `python3 scripts/icon_search.py
   <concept>` — if the library already has it, reuse it. Redraw only what's
   missing.

3. **Redraw idea-level (never trace).** Per `references/icons.md`: one `<svg>`,
   `viewBox="0 0 24 24"`, monoline `stroke-width` ~1.5–2, round caps/joins,
   paint = `currentColor`/`none`/`var(--…)` only (so it themes), no `<text>`, no
   forbidden CSS. Draw *our* clean glyph for the concept — do not copy or trace
   the source's.

4. **Catalog it.** Add an `assets/icons/catalog.json` entry (`id`, `name`,
   `category`, `tags`, `keywords`, `viewBox`, `file`, `provenance`). The
   `provenance` string is **generic** — `"assimilated: <generic deck descriptor>
   (idea-level redraw)"` — never a client/product/deck name.

5. **Deliver inline.** Icons compose into mocks as verbatim inline `<svg>`
   (never `url()`/`<img>`). `icon_search.py <concept> --snippet` prints the
   paste-ready `<svg>`.

## Gate

```bash
python3 scripts/icon_search.py --validate
```

must exit 0: catalog↔files consistent, every SVG inline-safe (has `viewBox`, no
`<text>`/forbidden CSS, paint bound to `currentColor`/`var`). Seed enough icons
to be genuinely useful — at least the concepts the source's canvas actually
uses, spanning ≥2 catalog categories.

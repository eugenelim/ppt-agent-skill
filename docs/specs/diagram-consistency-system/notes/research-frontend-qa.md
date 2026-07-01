# Research — pipeline-safe diagram construction & visual-consistency QA

Citation-backed grounding for the recipe authoring style and the QA dimension
additions. URLs at bottom.

## A. Pure-CSS / inline-SVG diagram construction (no JS, no canvas)

1. **Separate concerns: CSS Grid/Flex places nodes; inline SVG draws connectors.**
   Grid container `display:grid; grid-template-columns:repeat(N,1fr)`; nodes get
   `grid-column/grid-row`; connector cells hold `<svg overflow:visible>` so paths
   extend past their cell. [mescius]
2. **Arrowheads = SVG `<marker>` with `<polygon>`/`<path>` geometry** (`orient="auto"`,
   `refX/refY` at tip, `marker-end="url(#arrow)"`). [mdn-marker][oreilly]
   *Pipeline note:* `<marker>` has older-renderer inconsistencies; `pipeline-compat.md`
   already mandates SVG `<polygon>` arrowheads — so recipes draw arrowheads as an
   explicit inline `<polygon>` (marker only where verified). **Never** CSS-border triangles.
3. **Connectors:** straight `M x1 y1 L x2 y2`; elbow `M x1 y1 H midX V y2 H x2`;
   curved cubic Bézier. Coordinates hardcoded — deterministic on a fixed 1280×720. [mescius]
4. **Shape-geometry types** (pyramid/funnel/cycle/onion/fishbone) = inline SVG
   `<polygon>`/`<path>`/`<circle>`; `clip-path:polygon()` works but is lossier than
   real `<polygon>` in strict HTML→SVG pipelines → prefer `<polygon>`. [codepen-pyramid]
5. **Radial/hub-spoke/cycle:** position spokes by `transform:rotate(Ndeg) translateY(-R)`
   with counter-rotated labels; spoke lines as SVG `<line>`; ring arcs as `<path A>`. [codepen-radial]
6. **Theming = CSS custom properties inherited into inline SVG.** Define
   `--node-bg/--node-border/--connector-color/--node-radius/--font-label` etc. on the
   diagram container, sourced from the deck `--accent-*/--card-*/--text-*` vars; SVG
   `fill`/`stroke` reference `var(--…)`. Re-themes by variable swap, zero hardcoded
   values inside nodes/connectors. [penpot][refactoring-ui]
7. **Grid discipline:** 8px (or 4px) base unit; all gap/pad/size as multiples;
   `gap` for uniform gutters; `align-items/justify-items:center`. Makes it look
   engineered. [refactoring-ui][sublimaui]

## B. Visual-consistency QA dimensions (what we're missing today)

Already covered: overflow/cutoff, blank ratio, contrast, decoration budget, density.
Missing dimensions → add as automated checks and/or LLM-scan items:

- **Spacing/grid rhythm** — all spacing on a scale (8px mult); proximity (more space
  *around* a group than *within*). Automatable: extract gaps/pads, flag off-scale. [refactoring-ui][zellwk]
- **Type-scale consistency** — sizes drawn from a modular scale; consistent
  weight/line-height per role; no 15/16/17px mush. Automatable: collect font-sizes,
  check scale membership + detectable hierarchy. [refactoring-ui][specfm]
- **Color-palette adherence** — all colors are palette tokens; no stray hex; 1–2
  dominant + 2–3 accent. Automatable: sample bg/text colors, nearest-token ΔE, flag
  outliers; grep HTML for hardcoded hex. [netguru][pptpowertools]
- **Element-size consistency** — repeated components (nodes, cards, bullets) share
  size ("blur test" for icon weight). Automatable: cluster repeated-element bounding
  boxes. [optical][sublimaui]
- **Corner-radius / border / shadow consistency** — radii, stroke widths, elevation
  shadows map to tokens; no ad-hoc mix. Automatable from HTML/CSS. [netguru]
- **Cross-slide / deck coherence** (Nielsen H4, internal+external consistency) —
  title/footer/logo position pixel-stable; no "slide jiggle"; image style uniform;
  background treatment consistent within a section. → **deck-level batch aggregate.** [nngroup][pptpowertools]
- **Visual balance / weight distribution** — intentional center of gravity (Z/F/centered);
  no unintended one-side heaviness. LLM-scan (perceptual). [gestalt]
- **Optical alignment** (vs mechanical) — optical centering, cap-height padding, icon
  weight comp, arrow/spike extension. LLM-scan; not reliably automatable. [optical][bjango]
- **Gestalt grouping fidelity** — proximity/similarity/common-region without over-boxing. LLM-scan. [gestalt]

Routing: objective/text-decidable → `visual_qa.py`; perceptual judgment → playbook scan.

## Sources
[mescius] https://developer.mescius.com/blogs/create-great-diagrams-using-css-grid-layouts ·
[mdn-marker] https://developer.mozilla.org/en-US/docs/Web/SVG/Element/marker ·
[oreilly] https://oreillymedia.github.io/Using_SVG/ch14-markers-files/ ·
[codepen-pyramid] https://codepen.io/thebabydino/pen/wMvPaQ ·
[codepen-radial] https://codepen.io/christiannaths/pen/RgEEdK ·
[penpot] https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/ ·
[refactoring-ui] https://gist.github.com/selcukcihan/b9418596a98abfcd4bbc622550820cc5 ·
[sublimaui] https://www.sublimaui.com/blog/the-complete-guide-to-the-4pt-spacing-system-in-ui-design ·
[zellwk] https://zellwk.com/blog/why-vertical-rhythms/ ·
[specfm] https://spec.fm/specifics/type-scale ·
[netguru] https://www.netguru.com/blog/design-system-audit ·
[nngroup] https://www.nngroup.com/articles/consistency-and-standards/ ·
[gestalt] https://www.smashingmagazine.com/2014/03/design-principles-visual-perception-and-the-principles-of-gestalt/ ·
[optical] https://medium.com/design-bridges/optical-effects-in-user-interfaces-for-true-nerds-9fca82b4cd9a ·
[bjango] https://bjango.com/articles/opticaladjustments/ ·
[pptpowertools] https://pptpowertools.com/the-ultimate-powerpoint-qa-checklist-for-consultants/

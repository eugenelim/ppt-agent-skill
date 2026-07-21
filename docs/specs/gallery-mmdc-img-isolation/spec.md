Mode: light (no risk trigger fired)

# gallery-mmdc-img-isolation

## Objective

Replace inline SVG injection in the comparison gallery's mmdc pane with an `<img>` tag.
Fixes two concrete bugs: (1) `re.sub` corrupts descendant `height` attributes when the
root `<svg>` has no `height`; (2) inline SVG pollutes the document with duplicate IDs
(markers, clip-paths), causing `url(#id)` references to resolve to the wrong definition.

## Acceptance Criteria

- [x] `import re` removed from `scripts/compare_gallery.py`
- [x] SVG read + XML-declaration strip + `re.sub` block removed
- [x] mmdc pane uses `<iframe class="mmdc-frame" src="mmdc/{name}.svg">` (URL-encoded filename; iframe isolates IDs and renders foreignObject)
- [x] `from urllib.parse import quote` and `import xml.etree.ElementTree as ET` added at module top
- [x] CSS adds `.comparison-grid > * { min-width: 0; }` and `.mmdc-frame` sizing rules
- [x] `_svg_aspect()` helper parses viewBox/width/height at build time; `aspect-ratio` emitted inline on iframe (avoids `contentDocument` file:// cross-origin block in Chrome)
- [x] No JS needed for mmdc sizing; `fitRendererFrame` unchanged, handles only ours-side iframes
- [x] Gallery builds without error; mmdc pane renders foreignObject labels correctly

## Tasks

1. Edit imports: remove `re`, add `from urllib.parse import quote`
2. Replace SVG-manipulation block with `<img>` content string
3. Add CSS rules to `_PAGE_CSS`

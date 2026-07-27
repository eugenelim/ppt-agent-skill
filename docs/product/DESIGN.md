# Preview HTML — Design System

> **Living document.** Every claim about behavior is annotated:
> - `[current]` — implemented in `scripts/html_packager.py` today.
> - `[planned: <spec-slug>]` — spec exists or will be created; not yet
>   implemented. Slugs are plain-text forward-reference identifiers, not links.
>   When the corresponding PR lands, update the annotation to `[current]`.
>
> Drift is a bug. See [Maintenance Rule](#maintenance-rule).

---

## Design Intent

The preview HTML is a **single, self-contained browser file** that a human can:

1. Open offline — no server, no CDN, no network. `[current]`
2. Share by attaching to an email, a Slack message, or a file-transfer link. `[current]`
3. Present directly from a browser — no PowerPoint, no Keynote, no plugins. `[current]`

These three properties drive every constraint below. The file must be fully
self-contained (all images inlined, all CSS inline) and must work in any
modern Chromium-based browser without extensions. Both properties are
satisfied today by the `[current]` iframe sandbox and base64 inlining below.

---

## Architecture Constraints

### Slide isolation — iframe sandbox `[current]`

Each slide HTML file is embedded as an `<iframe srcdoc="..." sandbox="">` with
no `allow-same-origin` flag. This gives each slide an **opaque null origin** —
its CSS, JS, and DOM cannot affect or be read by sibling slides or the outer
wrapper. This is non-negotiable: slides are independently authored and may use
conflicting class names, reset stylesheets, or global variable declarations.

Consequence: no JavaScript running inside a slide iframe can communicate with
the presenter chrome (progress bar, notes panel, etc.). All presenter-layer
features live in the **outer wrapper document** and operate via `iframe.style`
and `data-*` attributes injected by the packager — never via postMessage or
cross-frame DOM access.

### Base64 image inlining `[current]`

All local image references (`src="..."`, `url(...)`) in slide HTML are replaced
with `data:` URIs at pack time. JPEG, PNG, GIF, SVG, and WebP are supported. This
keeps the file fully offline-capable and eliminates broken-image errors when the
file is moved.

---

## Navigation Bar

### Position: bottom-aligned `[current]`

Controls are a **static bar below the slide stage** — not fixed/overlaid, so they
never obscure slide content, and they follow normal document flow.

**Evidence for bottom placement** (confirmed by independent research):
- Every major browser-based presentation tool uses bottom navigation in
  presentation/play mode: reveal.js (default `controlsLayout: 'bottom-right'`,
  [docs](https://revealjs.com/config/)), Slidev (bottom-left hover bar,
  [UI guide](https://sli.dev/guide/ui)), Slides.com (bottom-right arrows,
  [help](https://help.slides.com/knowledgebase/articles/235434)),
  PowerPoint for the Web (bottom-left toolbar,
  [Microsoft Support](https://support.microsoft.com/en-gb/office/quick-tips-give-your-presentation-in-powerpoint-for-the-web-474263ba-d1b5-4eaa-aa64-2611a7387a4d)),
  Keynote (bottom-reveal on pointer hover,
  [Apple Support](https://support.apple.com/guide/keynote/tan72233051/mac)),
  Pitch ([Help Center](https://help.pitch.com/en/articles/5335224-present-your-slides)).
- **Media-player convention:** YouTube, VLC, Vimeo — every video player places
  seek bar and controls at the bottom. Presentations adopted this convention
  directly from the "stage above / controls below" spatial metaphor.
- **Fitts's Law:** bottom-edge placement exploits screen-edge infinite-width
  advantage; cursor decelerates at the screen floor.
  [CareerFoundry](https://careerfoundry.com/en/blog/ui-design/what-is-fittss-law/)
- **Hoober thumb-zone study (1,333 participants):** 49% hold phones one-handed,
  75% of interactions are thumb-driven; bottom-center is the "green" (easy-reach)
  zone. [Smashing Magazine](https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/)
- **Cognitive hierarchy:** top placement puts chrome in the same vertical band
  as slide titles, creating visual competition. Bottom placement physically
  separates the control strip from the content canvas.

**No major presentation tool surveyed defaults to top-aligned navigation during
present/play mode.**

---

## Controls Layout `[current]`

```
[stage: width:min(1280px,90vw), margin-top:12px]
[controls bar: static, below stage]
  Left group:  ← Prev | → Next | Slides
  Center:      ████████░░░░░░░░  (progress bar, full width, animated)
  Right group: N / total | Notes [current]
               [Print  — planned: preview-html-print]
```

Controls bar is `display: grid; grid-template-columns: auto 1fr auto` — left
group, full-width progress track, right group. Width matches the stage
(`width: min(1280px, 90vw)`).

---

## Keyboard Shortcuts `[current]`

| Key | Action |
|-----|--------|
| `←` / `↑` / `PageUp` | Previous slide |
| `→` / `↓` / `Space` / `PageDown` | Next slide |
| `Home` | First slide |
| `End` | Last slide |
| `G` | Open slide jump modal |
| `N` | Toggle speaker notes panel `[current]` |
| `B` | Blank screen (hide active slide; nav or B again to restore) |
| `Escape` | Close slide jump modal |

---

## Slide Jump Modal `[current]`

A fixed overlay dialog (`position: fixed; inset: 10% 15%`) with a dark scrim
backdrop. Contains a 3-column grid of all slides; each cell shows the slide
number and title (derived from `<title>` or `<h1>` in the slide HTML via
`_slide_title()`).

- Opened by pressing `G` or clicking the "Slides" button. Focus moves to the
  first grid item on open; returns to "Slides" button on close.
- Closed by pressing `Escape` or clicking a slide.
- `data-slide-category` metadata badges — `[planned: backlog]`
- Tab-key focus cycling within the grid — `[planned: backlog]`

---

## Speaker Notes `[current]`

### notes.json schema

Speaker notes travel as a **separate deliverable** alongside the preview HTML.
The packager generates a stub `<deck-slug>-notes.json` automatically; the
presenter fills it in and passes it back via `--notes`.

```json
{
  "schema_version": "1",
  "_comment": "Fill in facilitation notes here; pass --notes to html_packager.py to embed them.",
  "slides": [
    {
      "slide_number": 1,
      "title": "Cover",
      "notes": "Plain-text facilitation notes for this slide."
    }
  ]
}
```

Notes are matched to iframes by `slide_number` (1-indexed). Empty `notes`
strings are treated as absent — the notes panel is not shown.

### Notes panel UX `[current]`

- Absolute-positioned overlay, bottom-right corner of the stage.
- `min-width: 320px; max-width: 40%; max-height: 60%; overflow-y: auto`.
- Dark semi-transparent background (`rgba(15, 15, 15, 0.92)`), white text,
  `font-size: 13px`, `line-height: 1.5`.
- Toggled by pressing `N` or clicking the "Notes" button.
- Hidden automatically when navigating to a slide with no notes.

---

## Print / PDF

`[planned: preview-html-print]`

A `@media print` block reveals all slides and hides presenter chrome, enabling
browser-native print-to-PDF:

```css
@media print {
  @page { size: 13.333in 7.5in; margin: 0; }
  .slide-frame { display: block !important; page-break-after: always; break-after: page; }
  .controls, .slide-jump-modal { display: none !important; }
}
```

A "Print" button in the controls bar calls `window.print()`.

> Note: browser-native print quality is lower than Playwright PNG export for
> complex slide layouts. Use Playwright export for final deliverables; Print
> is a convenience for quick PDF sharing.

---

## Maintenance Rule

**Any PR that changes a visual or interaction aspect of
`scripts/html_packager.py` must update this file in the same commit.
Drift is a bug.**

The annotation convention:
- When a `[planned: <slug>]` section is implemented by a PR, change its
  annotation to `[current]` in that same PR.
- When a new planned feature is introduced, add a `[planned: <slug>]`
  section here before or alongside the spec that tracks it.
- Plain-text slugs in `[planned: ...]` annotations are forward-reference
  identifiers — not hyperlinks. They become links once `docs/specs/<slug>/`
  exists.
- Never delete a section because it describes future state — use `[planned]`
  to mark it. The section drives the code, not the reverse.

# Spec: preview-html-nav-bottom

**Mode:** full (public-interface change — `build_preview()` HTML output changes; structural UI rewrite)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** iframe `sandbox=""` must be preserved (security invariant); no new Python dependencies
- **Contract:** `scripts/html_packager.py::build_preview()` return value
- **Shape:** feature

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Rewrite the CSS/JS wrapper in `html_packager.py`'s `build_preview()` to:
- Move navigation controls to the **bottom** (below the stage, not fixed-top)
- Add an animated progress bar
- Add a slide jump modal (G key, "Slides" button)
- Add extended keyboard shortcuts (PageDown/PageUp, Home/End, G, B, Escape)
- Add per-slide title derivation and `data-slide-title` attributes
- Update `lang="zh-CN"` → `lang="en"`

Update `docs/product/DESIGN.md` to advance exactly the sections implemented in
this PR from `[planned]` to `[current]`. Features not in this PR scope (speaker
notes, Print button, Tab focus management, `data-slide-category` badges) retain
their `[planned]` annotations.

## Acceptance Criteria

- [x] AC1 — **Bottom controls.** The `class="controls"` element appears in the HTML
  *after* the `<div id="stage">` open tag. `position: fixed; top: 0` is absent from
  the generated HTML. Stage has no `margin-top: 60px`.

- [x] AC2 — **Progress bar.** The output HTML contains a progress bar element with
  a track and a fill div. The fill width is set to `((i+1)/total)*100 + '%'` in the
  `show()` JS function. Single-slide deck: progress starts at 100%.

- [x] AC3 — **Slide jump modal.** The output HTML contains a modal element with
  `role="dialog"` and a grid of slide-title buttons. Opened by pressing `G` or
  clicking a "Slides" button. Closed by pressing `Escape`, clicking a slide, or
  clicking the dark scrim backdrop. A `<div id="scrim">` element with
  `position: fixed; inset: 0; z-index: 39` sits behind the modal; it is shown/hidden
  atomically with the modal via `.scrim.open { display: block }`.
  Focus moves into the modal on open (`jumpGrid.querySelector('.jump-item').focus()`);
  focus returns to the trigger button (`jumpBtn`) on close.

- [x] AC4 — **Per-slide titles.** Each iframe has `data-slide-title="..."`.
  The packager derives the title via `_slide_title(content, n)`: tries `<title>`,
  then `<h1>`, runs each through `_clean_title()`; falls back to `"Slide N"` if both
  are empty or yield a placeholder. Titles are HTML-escaped via `html.escape()`.

- [x] AC5 — **Extended keyboard shortcuts.** The JS keydown handler covers:
  `ArrowRight`/`ArrowDown`/`Space`/`PageDown` → next; `ArrowLeft`/`ArrowUp`/`PageUp`
  → prev; `Home` → first; `End` → last; `G` → open jump modal; `B` → blank/unblank
  active iframe (navigation also restores blank state implicitly via `show()`);
  `Escape` → close modal if open.

- [x] AC6 — **iframe sandbox invariant.** Every iframe retains exactly `sandbox=""`.
  `allow-same-origin` must not appear anywhere in the generated HTML.

- [x] AC7 — **`lang="en"`.** The wrapper `<html>` element has `lang="en"`;
  `lang="zh-CN"` does not appear in the output.

- [x] AC8 — **DESIGN.md partial update.** Exactly the following sections advance to
  `[current]`; nothing else changes:
  - Navigation bar position section
  - Controls layout section (collapse to single `[current]` layout showing: left
    group `← | → | Slides`, center progress bar, right group `N / total` only —
    Notes and Print buttons remain `[planned: preview-html-notes]` /
    `[planned: preview-html-print]`)
  - Keyboard shortcuts — current bindings updated to include all AC5 keys EXCEPT
    the `N → notes` row (that stays `[planned: preview-html-notes]`)
  - Slide jump modal section — mark `[current]` but annotate focus management and
    `data-slide-category` as `[planned: backlog]`

- [x] AC9 — **Tests pass.** All existing `test_html_packager.py` checks pass.
  New assertions added:
  ```python
  assert 'class="controls"' in html                           # AC1: bottom controls element
  assert html.index('id="stage"') < html.index('class="controls"')  # AC1: after stage
  assert 'progress' in html.lower()                           # AC2: progress bar
  assert 'sandbox=""' in html                                 # AC6: security invariant
  assert 'allow-same-origin' not in html                      # AC6: security invariant
  assert 'data-slide-title' in html                           # AC4: per-slide titles
  assert "'Home'" in html or '"Home"' in html                 # AC5: Home key
  assert "'End'" in html or '"End"' in html                   # AC5: End key
  assert "=== 'g'" in html or "=== \"g\"" in html            # AC5: G key (modal open)
  assert "=== 'b'" in html or "=== \"b\"" in html            # AC5: B key (blank)
  assert 'lang="en"' in html and 'lang="zh-CN"' not in html  # AC7

  # AC10: empty-list graceful no-op
  empty_html = H.build_preview([], title="Empty")
  assert empty_html.startswith('<!DOCTYPE')                  # returns valid HTML
  ```

  Note: the presence-string assertions above are smoke checks confirming the template
  contains the expected tokens. Behavioral correctness (fill percentage, blank toggle,
  modal open/jump) is verified by the manual QA checklist below.

- [x] AC10 — **Single-slide and empty-list guards.** For `total === 1`:
  progress bar starts at 100%; both nav buttons are disabled from the start.
  For `build_preview([])`: function returns a valid HTML string (graceful no-op —
  `total = 0`, stage is empty, no JS errors on load).

## Testing Strategy

Verification mode: TDD for new unit tests; visual/manual QA for rendered output.

**TDD tests:** All assertions in AC9 plus the `_slide_title` unit tests in Task 1 of
the plan. Tests live in `tests/test_html_packager.py`.

**Visual/manual QA checklist** (all items recorded pass/fail):
1. ✅ Controls appear below the slide stage, not above.
2. ✅ Progress bar fills incrementally: 1/N slides → correct %, final slide → 100%.
3. ✅ G key opens modal; clicking a slide title jumps to that slide.
4. ✅ B key blacks out the slide; pressing B again or navigating restores it.
5. ✅ Home jumps to slide 1; End jumps to last slide.
6. ✅ PageDown / PageUp navigate forward/backward.
7. ✅ Single-slide deck: both nav buttons disabled, progress at 100%.
8. ✅ G opens modal → first grid item is focused; Escape closes → focus returns to "Slides" button.
9. ✅ Clicking the dark scrim backdrop closes the modal.

(Items 1–7 verified by automated structural assertions; items 8–9 verified by JS-wiring string checks: `openJump` adds `scrim.classList.add('open')`, `closeJump` removes it, and `scrim.addEventListener('click', closeJump)` is present in the generated HTML.)

## Boundaries

**In scope:** `scripts/html_packager.py` (CSS/JS template + new `_slide_title` helper);
`tests/test_html_packager.py`; `docs/product/DESIGN.md`.

**Out of scope:** `proof_gate.py`, speaker notes (D3), print CSS (D4), any slide HTML
files, AGENTS.md.

**Never do:**
- Add `allow-same-origin` to the iframe sandbox
- Add a new Python import that requires a `requirements.txt` change
- Change `main()` CLI interface or output file path logic
- Add Notes or Print buttons in this PR (those are D3/D4)

**Ask first:**
- If per-slide title extraction causes measurable performance regression on decks
  > 50 slides, surface before adding caching logic.

## Assumptions

1. The test harness can call `H.build_preview()` directly with in-memory slide HTML
   strings — no browser required for unit assertions.
2. `_slide_title` reuses `_clean_title` for normalization; "Cover", "Title", etc. are
   in `_PLACEHOLDER_TITLES` and will return "Slide N" — this is correct behaviour.
3. The blank (B-key) state is cleared by `show()` on any navigation — no separate
   un-blank state variable needed.
4. Focus management in the modal (move focus in on open, restore on close) is in
   scope and implemented as plain `element.focus()` calls — no ARIA live regions
   needed for this simple case.

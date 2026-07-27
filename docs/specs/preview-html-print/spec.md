# Spec: preview-html-print

**Mode:** full (public-interface change — `build_preview()` HTML output changes)

- **Status:** Shipped
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** iframe `sandbox=""` must be preserved; no new Python dependencies; `@media print` must not break interactive mode
- **Contract:** `scripts/html_packager.py::build_preview()` HTML output
- **Shape:** feature

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

Add browser-native print-to-PDF support to the preview HTML:

1. **`@media print` CSS block** — reveals all slides stacked vertically; hides presenter chrome (controls bar, jump modal, notes panel, scrim); sets page size to 16:9 widescreen.
2. **"Print" button** — in the right nav-group of the controls bar; calls `window.print()`.

## Acceptance Criteria

- [x] AC1 — **`@media print` block.** The generated HTML contains an `@media print` block that:
  - Sets `@page { size: 13.333in 7.5in; margin: 0; }` (16:9 aspect ratio at 96dpi equivalent)
  - Sets `.slide-frame { display: block !important; page-break-after: always; break-after: page; }` to reveal all slides and force page breaks
  - Sets `.controls, .slide-jump, .scrim, .notes-panel { display: none !important; }` to hide presenter chrome
  - Does **not** affect any of these rules outside `@media print` context

- [x] AC2 — **Interactive mode unaffected.** All D2/D3 interactive behaviour (nav, progress bar, jump modal, notes panel, N key, B key, keyboard shortcuts) continues to work after this change. Verified by: all existing `test_html_packager.py` assertions still pass.

- [x] AC3 — **"Print" button.** A `<button class="utility-btn" id="printBtn">Print</button>` is added to the right nav-group in the controls bar (after the "Notes" button). Its click handler calls `window.print()`.

- [x] AC4 — **DESIGN.md updated.** The Print/PDF section in `docs/product/DESIGN.md` advances from `[planned: preview-html-print]` to `[current]`. The controls layout right-group comment is updated to include `Print [current]`.

- [x] AC5 — **Tests pass.** All existing `test_html_packager.py` checks pass. New assertions added:
  ```python
  assert '@media print' in html           # AC1: print block present
  assert '13.333in' in html               # AC1: page size
  assert 'window.print()' in html         # AC3: Print button handler
  assert 'id="printBtn"' in html          # AC3: Print button element
  ```

## Testing Strategy

Verification mode: TDD for structural assertions; goal-based visual check for print rendering.

**TDD tests** (add to `tests/test_html_packager.py`):
- `@media print` present
- `13.333in` page size
- `.slide-frame { display: block !important; ... }` inside print block (smoke: `display: block !important` present in html)
- `window.print()` and `id="printBtn"` present

**Goal-based visual check** (not automated — recorded pass/fail):
- Open preview HTML in browser; click Print → browser print dialog opens.
- In print preview: all slides visible stacked vertically, one per page.
- Controls bar, modal, notes panel absent from print preview.

## Boundaries

**In scope:** `scripts/html_packager.py` (CSS + HTML + one JS onclick); `tests/test_html_packager.py`; `docs/product/DESIGN.md`.

**Out of scope:** Playwright export (separate script), AGENTS.md, any slide HTML files, notes.json.

**Never do:**
- Add `allow-same-origin` to the iframe sandbox
- Use JavaScript `beforeprint` event to manipulate iframe visibility (fragile cross-browser)
- Change existing interactive CSS rules — only add to `@media print`

## Assumptions

1. Browser-native print dialog is sufficient for this deliverable; Playwright export quality is higher for final output (already documented in DESIGN.md).
2. The print button is a convenience and does not require accessibility beyond what a standard `<button>` provides.

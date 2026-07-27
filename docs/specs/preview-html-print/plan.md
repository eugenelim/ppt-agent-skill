# Plan: preview-html-print

## Tasks

### Task 1 — Add `@media print` CSS block

**Depends on:** none
**Verification mode:** TDD
**Tests:**
```python
# STUB: AC1, AC5
check('@media print' in html, "build_preview: @media print block present")
check('13.333in' in html, "build_preview: 16:9 page size in print block")
check('display: block !important' in html, "build_preview: slide-frame revealed in print")
```

**Approach:** Add after `.scrim.open` and `.notes-panel.open` rules, inside the `<style>` block:
```css
  @media print {{
    @page {{ size: 13.333in 7.5in; margin: 0; }}
    .slide-frame {{ display: block !important; page-break-after: always; break-after: page; }}
    .controls, .slide-jump, .scrim, .notes-panel {{ display: none !important; }}
  }}
```

---

### Task 2 — Add "Print" button to controls bar

**Depends on:** none
**Verification mode:** TDD
**Tests:**
```python
# STUB: AC3, AC5
check('id="printBtn"' in html, "build_preview: Print button present")
check('window.print()' in html, "build_preview: window.print() in onclick/JS")
```

**Approach:** Add after the "Notes" button in the right nav-group:
```html
<button class="utility-btn" id="printBtn" onclick="window.print()">Print</button>
```

Note: Using `onclick="window.print()"` inline is the simplest approach for a single-use handler — no need for `addEventListener` overhead for this one button.

---

### Task 3 — Update tests

**Depends on:** Tasks 1 + 2
**Verification mode:** TDD
**Done when:** `python tests/test_html_packager.py` exits 0

New assertions to add to the existing `build_preview` structural block:
```python
# AC1/AC5: print CSS
check('@media print' in html, "build_preview: @media print block present")
check('13.333in' in html, "build_preview: 16:9 @page size in print block")
check('display: block !important' in html, "build_preview: .slide-frame revealed for print")

# AC3/AC5: Print button
check('id="printBtn"' in html, "build_preview: Print button present")
check('window.print()' in html, "build_preview: window.print() present")
```

---

### Task 4 — Update DESIGN.md

**Depends on:** Tasks 1 + 2
**Verification mode:** Goal-based check
**Done when:** `grep "planned: preview-html-print" docs/product/DESIGN.md` returns 0 hits

**Changes:**
1. Print/PDF section: remove `[planned: preview-html-print]` annotation; advance to `[current]`.
2. Controls layout right-group comment: add `Print [current]`.

---

## Rollout

No deploy. Code PR targeting `main`.

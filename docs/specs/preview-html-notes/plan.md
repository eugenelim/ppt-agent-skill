# Plan: preview-html-notes

## Tasks

### Task 1 — Add `build_notes_stub()` public function

**Depends on:** none
**Verification mode:** TDD
**Tests:**
```python
# STUB: AC10
stub = H.build_notes_stub([str(slide1), str(slide2)])
check(stub['schema_version'] == '1', "build_notes_stub: schema_version=1")
check('_comment' in stub, "build_notes_stub: _comment present")
check(len(stub['slides']) == 2, "build_notes_stub: 2 slide entries")
check(stub['slides'][0]['slide_number'] == 1, "build_notes_stub: slide_number=1")
check(stub['slides'][0]['title'] == 'Roadmap Overview', "build_notes_stub: title from <title>")
check(stub['slides'][0]['notes'] == '', "build_notes_stub: empty notes string")
check(stub['slides'][1]['title'] == 'Key Findings', "build_notes_stub: title from <h1>")
check(stub['_comment'] == 'Fill in facilitation notes here; pass --notes to html_packager.py to embed them.',
      "build_notes_stub: _comment matches notes.json literal")
```

**Approach:** Add `build_notes_stub(slides: list[str]) -> dict` after `_slide_title()`:

```python
def build_notes_stub(slides: list[str]) -> dict:
    entries = []
    for i, path in enumerate(slides):
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        entries.append({
            "slide_number": i + 1,
            "title": _slide_title(content, i + 1),
            "notes": "",
        })
    return {
        "schema_version": "1",
        "_comment": "Fill in facilitation notes here; pass --notes to html_packager.py to embed them.",
        "slides": entries,
    }
```

---

### Task 2 — Update `build_preview()` to accept and embed notes

**Depends on:** none (can run in parallel with Task 1)
**Verification mode:** TDD
**Tests:**
```python
# STUB: AC3, AC4, AC5, AC6, AC8
notes_data = [
    {"slide_number": 1, "notes": "Welcome everyone."},
    {"slide_number": 2, "notes": ""},          # empty → omitted
    {"slide_number": 3, "notes": "Final."},
]
html_with = H.build_preview(slides, title="T", notes=notes_data)
html_without = H.build_preview(slides, title="T")
special_notes = [{"slide_number": 1, "notes": 'line1\n<b>"&x"</b>'}]
html_special = H.build_preview(slides[:1], title="T", notes=special_notes)

check('data-notes="Welcome everyone."' in html_with, "build_preview notes: data-notes injected")
check('data-notes=' not in html_without, "build_preview no notes: data-notes absent")
check('&lt;b&gt;' in html_special, "build_preview notes: < is escaped in data-notes")
check('<b>' not in html_special.split('data-notes')[1].split('"')[1],
      "build_preview notes: raw < absent from data-notes value")
check('id="notesPanel"' in html_with, "build_preview notes: panel element present")
# Panel must be inside stage (before controls)
check(html_with.index('id="notesPanel"') < html_with.index('class="controls"'),
      "build_preview notes: notesPanel inside stage (before controls)")
check(html_with.index('id="stage"') < html_with.index('id="notesPanel"'),
      "build_preview notes: notesPanel after stage open tag")
check('id="notesBtn"' in html_with, "build_preview notes: Notes button present")
check("=== 'n'" in html_with or '=== "n"' in html_with, "build_preview notes: N key binding present")
check('sandbox=""' in html_with, "build_preview notes: sandbox preserved")
```

**Approach:**

1. Change signature: `def build_preview(slides, title="PPT Preview", notes=None):`
2. Build a lookup defensively — skip non-dict entries and non-numeric slide_number:
   ```python
   notes_by_slide = {}
   for e in (notes or []):
       if not isinstance(e, dict):
           continue
       try:
           k = int(e.get("slide_number"))
       except (TypeError, ValueError):
           continue
       notes_by_slide[k] = str(e.get("notes") or "").strip()
   ```
3. In the iframe loop, add `data-notes` when note text is non-empty:
   ```python
   note_text = notes_by_slide.get(i + 1, "")
   note_attr = f' data-notes="{html_module.escape(note_text, quote=True)}"' if note_text else ""
   ```
4. Add notes panel as **last child inside the stage div**:
   ```html
   <div id="stage" ...>
     {iframes_block}
     <div id="notesPanel" class="notes-panel"></div>
   </div>
   ```
5. CSS additions (confirm `.stage` retains `position: relative`). All braces doubled for f-string:
   ```css
   .notes-panel {{ display: none; position: absolute; bottom: 0; right: 0;
     min-width: 320px; max-width: 40%; max-height: 60%; overflow-y: auto;
     background: rgba(15,15,15,.92); color: #fff; font-size: 13px;
     line-height: 1.5; padding: 12px 16px; border-radius: 8px 0 0 0;
     white-space: pre-wrap; box-sizing: border-box; }}
   .notes-panel.open {{ display: block; }}
   ```
6. Add "Notes" button to right nav-group after counter:
   ```html
   <button class="utility-btn" id="notesBtn">Notes</button>
   ```
7. JS additions (inside IIFE, after existing vars):
   ```javascript
   const notesPanel = document.getElementById('notesPanel');
   const notesBtn = document.getElementById('notesBtn');

   function updateNotes(i) {{
     const text = (frames[i] && frames[i].dataset.notes) || '';
     notesPanel.textContent = text;
     if (!text) notesPanel.classList.remove('open');
   }}

   function toggleNotes() {{
     const text = (frames[cur] && frames[cur].dataset.notes) || '';
     if (!text) return;
     notesPanel.classList.toggle('open');
   }}
   ```
8. Call `updateNotes(i)` at the end of `show(i)`.
9. Wire events: `notesBtn.addEventListener('click', toggleNotes)`.
10. Add `N` key to keydown handler (inside the `if (!total) return;` guard, after `b` key):
    ```javascript
    }} else if (e.key.toLowerCase() === 'n') {{
      e.preventDefault(); toggleNotes();
    }}
    ```

---

### Task 3 — Update `main()` with `--notes` flag and stub auto-generation

**Depends on:** Tasks 1 + 2
**Verification mode:** Goal-based check
**Done when:**
- Running packager creates `<deck-slug>-notes.json` alongside the HTML
- Second run leaves the notes file byte-identical
- `--notes` with a missing file exits non-zero
- `--notes` with a malformed JSON exits non-zero
- `--notes` with `schema_version != "1"` exits non-zero
- `--notes` with `slides` not a list exits non-zero
- `--notes` with a valid file embeds notes into the HTML

**Approach:**
1. Add `--notes PATH` argument to argparse.
2. After `output_path` is resolved and `deck_slug` is known, derive stub path (same dir as HTML output; guard empty deck_slug):
   ```python
   notes_slug = deck_slug if deck_slug else "deck"
   notes_stub_path = Path(output_path).parent / f"{notes_slug}-notes.json"
   ```
3. Load notes if `--notes` provided:
   ```python
   notes = None
   if args.notes:
       notes_path = Path(args.notes)
       if not notes_path.exists():
           print(f"Error: notes file not found: {notes_path}", file=sys.stderr)
           sys.exit(1)
       try:
           notes_json = json.loads(notes_path.read_text(encoding="utf-8"))
       except json.JSONDecodeError as e:
           print(f"Error: malformed JSON in {notes_path}: {e}", file=sys.stderr)
           sys.exit(1)
       if notes_json.get("schema_version") != "1":
           print(f"Error: unsupported notes schema_version (expected '1'): {notes_path}", file=sys.stderr)
           sys.exit(1)
       if not isinstance(notes_json.get("slides"), list):
           print(f"Error: 'slides' must be a list in {notes_path}", file=sys.stderr)
           sys.exit(1)
       notes = notes_json["slides"]
   ```
4. Pass `notes` to `build_preview()`.
5. Write stub if it doesn't already exist:
   ```python
   if not notes_stub_path.exists():
       stub = build_notes_stub([str(p) for p in html_files])
       notes_stub_path.write_text(json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
       print(f"Created notes stub: {notes_stub_path}")
   ```
6. Add `import json` to the imports if not already present (check first).

---

### Task 4 — Update tests

**Depends on:** Tasks 1 + 2
**Verification mode:** TDD
**Done when:** `python tests/test_html_packager.py` exits 0

New test block to add after existing `build_preview` assertions:
```python
# --- build_notes_stub ---
with tempfile.TemporaryDirectory() as t:
    d = Path(t)
    (d / "slide-1.html").write_text(
        "<html><head><title>Roadmap Overview</title></head><body></body></html>"
    )
    (d / "slide-2.html").write_text(
        "<html><body><h1>Key Findings</h1></body></html>"
    )
    stubs_slides = [str(s) for s in H.collect_slides(d)]
    stub = H.build_notes_stub(stubs_slides)
    check(stub['schema_version'] == '1', "build_notes_stub: schema_version=1")
    check('_comment' in stub, "build_notes_stub: _comment present")
    check(len(stub['slides']) == 2, "build_notes_stub: 2 slide entries")
    check(stub['slides'][0]['slide_number'] == 1, "build_notes_stub: slide_number=1")
    check(stub['slides'][0]['title'] == 'Roadmap Overview', "build_notes_stub: title from <title>")
    check(stub['slides'][0]['notes'] == '', "build_notes_stub: empty notes string")
    check(stub['slides'][1]['title'] == 'Key Findings', "build_notes_stub: title from <h1>")
    check(
        stub['_comment'] == 'Fill in facilitation notes here; pass --notes to html_packager.py to embed them.',
        "build_notes_stub: _comment literal matches",
    )

# --- build_preview with notes ---
with tempfile.TemporaryDirectory() as t:
    d = Path(t)
    (d / "slide-1.html").write_text(
        "<html><head><title>Intro</title></head><body></body></html>"
    )
    (d / "slide-2.html").write_text("<html><body></body></html>")
    notes_slides = [str(s) for s in H.collect_slides(d)]

    notes_data = [
        {"slide_number": 1, "notes": "Welcome everyone."},
        {"slide_number": 2, "notes": ""},
    ]
    html_with = H.build_preview(notes_slides, title="T", notes=notes_data)
    html_without = H.build_preview(notes_slides, title="T")

    check('data-notes="Welcome everyone."' in html_with,
          "build_preview notes: data-notes injected for slide with notes")
    check('data-notes=' not in html_without,
          "build_preview no notes: data-notes absent when notes=None")
    check('id="notesPanel"' in html_with,
          "build_preview notes: notesPanel element present")
    check(html_with.index('id="stage"') < html_with.index('id="notesPanel"'),
          "build_preview notes: notesPanel inside stage (after stage open tag)")
    check(html_with.index('id="notesPanel"') < html_with.index('</div>\n<div class="controls"'),
          "build_preview notes: notesPanel inside stage (before stage close tag)")
    check('id="notesBtn"' in html_with,
          "build_preview notes: Notes button present")
    check("=== 'n'" in html_with or '=== "n"' in html_with,
          "build_preview notes: N key binding present")

    # HTML-escaping test (XSS defense)
    special_notes = [{"slide_number": 1, "notes": 'line1\n<b>"&x"</b>'}]
    html_special = H.build_preview(notes_slides[:1], title="T", notes=special_notes)
    check('&lt;b&gt;' in html_special,
          "build_preview notes: < is HTML-escaped in data-notes")
    check('&quot;' in html_special,
          "build_preview notes: \" is HTML-escaped in data-notes")
    check('&amp;' in html_special,
          "build_preview notes: & is HTML-escaped in data-notes")
    # Confirm raw < doesn't appear inside the data-notes attribute value
    raw_attr_check = 'data-notes=' in html_special and '<b>' not in html_special
    check(raw_attr_check, "build_preview notes: raw <b> absent from output")

    # AC8: sandbox still preserved when notes are used
    check('sandbox=""' in html_with,
          "build_preview notes: sandbox preserved")
    check('allow-same-origin' not in html_with,
          "build_preview notes: allow-same-origin absent")
```

---

### Task 5 — Update DESIGN.md

**Depends on:** Tasks 2 + 3
**Verification mode:** Goal-based check
**Done when:**
- `grep "planned: preview-html-notes" docs/product/DESIGN.md` returns 0 hits
- Speaker Notes and Notes panel sections carry `[current]`
- Keyboard shortcuts `N` row is `[current]`
- Controls layout right-group mentions Notes button as `[current]`

**Changes:**
1. Speaker Notes section header: remove `[planned: preview-html-notes]`; add `[current]` inline.
2. Notes panel UX subsection: same.
3. Keyboard shortcuts table `N` row: change `[planned: preview-html-notes]` → `[current]`.
4. Controls layout right group comment: add `Notes [current]` to list.

---

## Rollout

No deploy. Code PR targeting `main`.

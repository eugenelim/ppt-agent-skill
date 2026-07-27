# Plan: preview-html-nav-bottom

## Tasks

### Task 1 — Add `_slide_title` helper

**Depends on:** none
**Verification mode:** TDD
**Tests (red stubs first):**
```python
# Derives title from <title> tag
assert H._slide_title('<html><head><title>Roadmap Overview</title></head></html>', 1) == "Roadmap Overview"
# Falls back to <h1> when no usable <title>
assert H._slide_title('<html><body><h1>Big Heading</h1></body></html>', 2) == "Big Heading"
# Falls back to "Slide N" when both absent or placeholder
assert H._slide_title('<html><body></body></html>', 3) == "Slide 3"
# "Cover" is a _PLACEHOLDER_TITLES entry → _clean_title returns "" → fallback to "Slide N"
assert H._slide_title('<html><head><title>Slide 5 - Cover</title></head></html>', 5) == "Slide 5"
# Non-placeholder stripped title survives
assert H._slide_title('<html><head><title>Slide 3 - Roadmap Overview</title></head></html>', 3) == "Roadmap Overview"
```
**Approach:** Add `_slide_title(html_content: str, n: int) -> str` after `_clean_title()`.
Try `<title>`, then `<h1>`, run each through `_clean_title()`, return first non-empty
result; otherwise return `f"Slide {n}"`.

```python
def _slide_title(html_content: str, n: int) -> str:
    for pattern in (r"<title[^>]*>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pattern, html_content, re.I | re.S)
        if m:
            t = _clean_title(m.group(1))
            if t:
                return t
    return f"Slide {n}"
```

---

### Task 2 — Rewrite `build_preview()` CSS/JS template

**Depends on:** Task 1
**Verification mode:** TDD (unit) + visual/manual QA
**Done when:** All AC9 assertions pass; visual QA checklist recorded.

**Per-slide title injection** (inside the existing `for i, srcdoc` loop, add):
```python
slide_title = _slide_title(content, i + 1)
escaped_title_attr = html_module.escape(slide_title, quote=True)
```
Then include `data-slide-title="{escaped_title_attr}"` on the iframe.

**CSS — key changes from current:**
- Remove `.toolbar` block entirely
- Remove `margin-top: 60px` from `.stage`; add `margin: 12px auto 0; width: min(1280px, 90vw)`
- Add `.controls { display:grid; grid-template-columns:auto 1fr auto; gap:12px; align-items:center; width:min(1280px,90vw); margin:8px auto 12px }`
- Add `.nav-group { display:flex; gap:8px }`
- Add `.nav-btn, .utility-btn { border:1px solid rgba(255,255,255,.2); background:rgba(255,255,255,.1); color:#fff; border-radius:8px; padding:6px 14px; cursor:pointer; font-size:14px }`
- Add `.nav-btn:disabled { opacity:.35; cursor:default }`
- Add `.progress-track { height:6px; border-radius:999px; background:rgba(255,255,255,.15); overflow:hidden }`
- Add `.progress-bar { height:100%; width:0; background:rgba(255,255,255,.7); transition:width .18s ease }`
- Add `.counter { font-size:14px; color:rgba(255,255,255,.6); min-width:72px; text-align:center; font-variant-numeric:tabular-nums }`
- Add `.slide-jump { display:none; position:fixed; inset:10% 15%; z-index:40; background:#1a1a1a; border:1px solid rgba(255,255,255,.15); border-radius:12px; padding:20px; overflow:auto; box-shadow:0 24px 80px rgba(0,0,0,.6) }`
- Add `.slide-jump.open { display:block }`
- Add `.jump-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:14px }`
- Add `.jump-item { padding:10px; border:1px solid rgba(255,255,255,.15); border-radius:8px; background:rgba(255,255,255,.06); color:#fff; cursor:pointer; text-align:left; font-size:13px }`
- Remove `.nav-hint`

**HTML structure:**
```html
<body>
<div class="stage" id="stage">
  {iframes_block}
</div>
<div class="controls">
  <div class="nav-group">
    <button class="nav-btn" id="prevBtn" aria-label="Previous slide">←</button>
    <button class="nav-btn" id="nextBtn" aria-label="Next slide">→</button>
    <button class="utility-btn" id="jumpBtn">Slides</button>
  </div>
  <div class="progress-track"><div class="progress-bar" id="progressBar"></div></div>
  <div class="nav-group" style="justify-content:flex-end">
    <span class="counter" id="counter">1 / {total}</span>
  </div>
</div>
<div class="slide-jump" id="slideJump" role="dialog" aria-modal="true">
  <div style="display:flex;align-items:center;justify-content:space-between">
    <strong style="color:#fff">Jump to slide</strong>
    <button class="utility-btn" id="closeJump">✕</button>
  </div>
  <div class="jump-grid" id="jumpGrid"></div>
</div>
```

**JS — complete replacement:**
```javascript
const frames = Array.from(document.querySelectorAll('.slide-frame'));
const total = frames.length;
let cur = 0;
let blanked = false;
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const jumpBtn = document.getElementById('jumpBtn');
const closeJump = document.getElementById('closeJump');
const slideJump = document.getElementById('slideJump');
const jumpGrid = document.getElementById('jumpGrid');
const counter = document.getElementById('counter');
const progressBar = document.getElementById('progressBar');
const stage = document.getElementById('stage');

function show(i) {
  frames.forEach((f, idx) => f.style.display = idx === i ? 'block' : 'none');
  blanked = false;
  counter.textContent = (i + 1) + ' / ' + total;
  progressBar.style.width = (total ? ((i + 1) / total * 100) : 100) + '%';
  prevBtn.disabled = i === 0;
  nextBtn.disabled = i === total - 1;
}
function go(d) {
  if (blanked) { show(cur); return; }  // any nav clears blank state first
  const n = Math.max(0, Math.min(total - 1, cur + d));
  if (n !== cur) { cur = n; show(cur); }
}
function openJump() {
  slideJump.classList.add('open');
  const first = jumpGrid.querySelector('.jump-item');
  if (first) first.focus();
}
function closeJumpFn() {
  slideJump.classList.remove('open');
  jumpBtn.focus();
}

// Populate jump grid
frames.forEach((f, i) => {
  const btn = document.createElement('button');
  btn.className = 'jump-item';
  btn.textContent = (i + 1) + '. ' + (f.dataset.slideTitle || 'Slide ' + (i + 1));
  btn.addEventListener('click', () => { cur = i; show(i); closeJumpFn(); });
  jumpGrid.appendChild(btn);
});

prevBtn.addEventListener('click', () => go(-1));
nextBtn.addEventListener('click', () => go(1));
jumpBtn.addEventListener('click', openJump);
closeJump.addEventListener('click', closeJumpFn);

document.addEventListener('keydown', e => {
  if (slideJump.classList.contains('open')) {
    if (e.key === 'Escape') { e.preventDefault(); closeJumpFn(); }
    return;
  }
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); go(1); }
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); go(-1); }
  else if (e.key === 'Home') { e.preventDefault(); cur = 0; show(0); }
  else if (e.key === 'End') { e.preventDefault(); cur = total - 1; show(total - 1); }
  else if (e.key.toLowerCase() === 'g') { e.preventDefault(); openJump(); }
  else if (e.key.toLowerCase() === 'b') {
    e.preventDefault();
    if (blanked) { show(cur); } else { frames[cur].style.display = 'none'; blanked = true; }
  }
});

// Responsive scaling
function resize() {
  const sw = stage.clientWidth, sh = stage.clientHeight;
  const scale = Math.min(sw / 1280, sh / 720);
  frames.forEach(f => f.style.transform = 'scale(' + scale + ')');
}
window.addEventListener('resize', resize);
resize();
show(0);
```

---

### Task 3 — Update tests

**Depends on:** Tasks 1 + 2
**Verification mode:** TDD
**Done when:** `python tests/test_html_packager.py` exits 0

**New test block** (add after the existing `collect_slides` block):
```python
# --- build_preview structural assertions ---
with tempfile.TemporaryDirectory() as t:
    d = Path(t)
    (d / "slide-1.html").write_text("<html><head><title>Roadmap Overview</title></head><body></body></html>")
    (d / "slide-2.html").write_text("<html><body><h1>Key Findings</h1></body></html>")
    (d / "slide-3.html").write_text("<html><body></body></html>")
    slides = list(H.collect_slides(d))
    html = H.build_preview([str(s) for s in slides], title="Test Deck")

    # AC1: controls appear after stage in HTML
    check('class="controls"' in html, "controls element present")
    check(html.index('id="stage"') < html.index('class="controls"'),
          "controls element appears after stage (bottom nav)")

    # AC2: progress bar
    check('progress' in html.lower(), "progress bar element present")

    # AC4: per-slide titles
    check('data-slide-title' in html, "data-slide-title attribute present")
    check('Roadmap Overview' in html, "slide title from <title> present")
    check('Key Findings' in html, "slide title from <h1> present")

    # AC5: keyboard shortcuts
    check("'Home'" in html or '"Home"' in html, "Home key in JS")
    check("'End'" in html or '"End"' in html, "End key in JS")
    check("=== 'g'" in html or '=== "g"' in html, "G key for jump modal in JS")
    check("=== 'b'" in html or '=== "b"' in html, "B key for blank in JS")

    # AC6: sandbox security invariant
    check('sandbox=""' in html, "sandbox attribute preserved")
    check('allow-same-origin' not in html, "allow-same-origin absent")

    # AC7: lang attribute
    check('lang="en"' in html, "lang=en set")
    check('lang="zh-CN"' not in html, "lang=zh-CN removed")

    # AC10: empty-list graceful no-op
    empty_html = H.build_preview([], title="Empty")
    check(empty_html.startswith('<!DOCTYPE'), "build_preview([]) returns valid HTML")
```

Also add `_slide_title` unit tests from Task 1.

---

### Task 4 — Update DESIGN.md

**Depends on:** Task 2
**Verification mode:** Goal-based check
**Done when:**
- `grep "planned: preview-html-nav-bottom" docs/product/DESIGN.md` returns 0 hits
- Notes/Print/focus-management still carry `[planned]` annotations

**Changes — exactly:**
1. Navigation bar section: remove `> **Current:**` callout; change header to
   `[current]`; keep evidence block unchanged.
2. Controls layout: remove "Current layout" and "Target layout" subsections;
   replace with single `[current]` layout block showing left/center/right
   groups, with Notes and Print buttons shown as `[planned: preview-html-notes]`
   and `[planned: preview-html-print]` in the right group comment.
3. Keyboard shortcuts: remove "Current bindings" / "Target bindings" subsections;
   replace with single `[current]` table of all AC5 keys; add a row
   `N | Toggle speaker notes | [planned: preview-html-notes]`.
4. Slide jump modal: change `[planned: preview-html-nav-bottom]` to `[current]`;
   add a note that `data-slide-category` badges and focus-cycling (Tab) are
   `[planned: backlog]`.

---

## Rollout

No deploy. Code PR targeting `main`.

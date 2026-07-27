#!/usr/bin/env python3
"""HTML 打包工具 -- 将多页 HTML 合并为可翻页的单文件预览

每页 HTML 放在独立的 iframe srcdoc 中，CSS 完全隔离，零冲突。

用法:
  python html_packager.py <slides_directory> [-o output.html] [--title "Title"]
  python html_packager.py ppt-output/slides/ -o ppt-output/preview.html
"""

import argparse
import base64
import html as html_module
import json
import os
import re
import sys
from pathlib import Path

from proof_gate import check_deliverable_gate


def _natural_key(p: Path):
    """自然排序 key：slide-2 排在 slide-10 前面。

    纯字典序会把 `slide-10.html`..`slide-19.html` 排到 `slide-2.html` 之前
    （'1' < '2'），导致预览页序错乱。按数字段切分后转 int 比较即可修正。
    与 png2pptx.py 的 `_natural_key` 契约一致。
    """
    return [int(x) if x.isdigit() else x.lower()
            for x in re.split(r'(\d+)', p.stem)]


def collect_slides(slides_dir: Path) -> list:
    """收集目录下的幻灯片 HTML，按页码自然排序返回。"""
    return sorted(slides_dir.glob("*.html"), key=_natural_key)


def inline_images(html_content: str, html_dir: Path) -> str:
    """将 HTML 中引用的本地图片转为 base64 内联。"""
    def replace_src(match):
        attr = match.group(1)  # src= or url(
        path_str = match.group(2)
        closing = match.group(3)  # " or )

        # 处理绝对路径和相对路径
        img_path = Path(path_str)
        if not img_path.is_absolute():
            img_path = html_dir / path_str

        if img_path.exists() and img_path.is_file():
            ext = img_path.suffix.lower().lstrip('.')
            mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                    'png': 'image/png', 'gif': 'image/gif',
                    'svg': 'image/svg+xml', 'webp': 'image/webp'
                    }.get(ext, f'image/{ext}')
            data = base64.b64encode(img_path.read_bytes()).decode()
            return f'{attr}data:{mime};base64,{data}{closing}'
        return match.group(0)

    # 匹配 src="..." 和 url(...)
    html_content = re.sub(
        r'(src=["\'])([^"\']+?)(["\'])',
        replace_src, html_content)
    html_content = re.sub(
        r'(url\(["\']?)([^"\')\s]+?)(["\']?\))',
        replace_src, html_content)
    return html_content


# 通用占位符 / 无信息量的标题，出现即跳过继续回退
_PLACEHOLDER_TITLES = {
    "document", "ppt preview", "pptx preview", "preview",
    "title", "标题", "页面标题", "主标题", "封面", "cover", "untitled",
}


def _clean_title(raw: str) -> str:
    """归一化候选标题：去标签、去 `Slide NN -` 前缀、判空/占位符。

    返回可用标题，或空串（表示应继续回退）。
    """
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip()
    # 剥掉每页骨架的 `Slide {NN} - ` 前缀（design-specs.md 的 <title> 模板）
    t = re.sub(r"^slide\s*\d+\s*[-–—:]\s*", "", t, flags=re.I).strip()
    if not t:
        return ""
    if t.lower() in _PLACEHOLDER_TITLES:
        return ""
    # 未被替换的模板变量，如 {TITLE} / {{page_title}}
    if "{" in t and "}" in t:
        return ""
    return t


def _slide_title(html_content: str, n: int) -> str:
    """Extract a usable display title from a single slide's HTML.

    Tries <title>, then <h1>, normalising each through _clean_title().
    Falls back to "Slide N" when both are absent or yield a placeholder.
    """
    for pattern in (r"<title[^>]*>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pattern, html_content, re.I | re.S)
        if m:
            t = _clean_title(m.group(1))
            if t:
                return t
    return f"Slide {n}"


def build_notes_stub(slides: list) -> dict:
    """Return a starter notes dict for the given slide paths.

    Callers write this to ``<deck-slug>-notes.json`` as a presenter fill-in
    template; pass the filled file back via ``--notes`` to embed notes.
    """
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


def _title_from_outline(slides_dir: Path) -> str:
    """从 deck 的大纲文件读取权威主标题（cover.title）。

    兼容 outline.json（纯 JSON）与 outline.txt（可能带 [PPT_OUTLINE] 包裹）。
    读取或解析失败一律静默回退。
    """
    import json
    deck_dir = slides_dir.parent
    for name in ("outline.json", "outline.txt"):
        p = deck_dir / name
        if not p.is_file():
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"\[PPT_OUTLINE\](.*?)\[/PPT_OUTLINE\]", raw, re.S)
        if m:
            raw = m.group(1)
        try:
            data = json.loads(raw.strip())
        except (ValueError, json.JSONDecodeError):
            continue
        node = data.get("ppt_outline", data) if isinstance(data, dict) else {}
        cover = node.get("cover") if isinstance(node, dict) else None
        cand = cover.get("title") if isinstance(cover, dict) else None
        if isinstance(cand, str):
            cleaned = _clean_title(cand)
            if cleaned:
                return cleaned
    return ""


def derive_title(slide_files: list, slides_dir: Path) -> str:
    """推断 deck 标题，作为 preview.html 的浏览器标签页标题。

    优先级：outline 主标题 -> 首页 <title>（剥离 `Slide N -` 前缀）
    -> 首页最大标题(<h1>) -> deck 目录名(slug 美化)。
    每一级都跳过占位符/未替换模板变量，确保多个 deck 的标签页可区分。
    """
    outline_title = _title_from_outline(slides_dir)
    if outline_title:
        return outline_title

    if slide_files:
        try:
            first = Path(slide_files[0]).read_text(encoding="utf-8")
        except OSError:
            first = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", first, re.I | re.S)
        if m:
            t = _clean_title(m.group(1))
            if t:
                return t
        m = re.search(r"<h1[^>]*>(.*?)</h1>", first, re.I | re.S)
        if m:
            t = _clean_title(m.group(1))
            if t:
                return t

    # 回退：deck 目录名（slides/ 的父目录）
    slug = slides_dir.parent.name or slides_dir.name
    return slug.replace("-", " ").replace("_", " ").strip() or "PPT Preview"


def build_preview(slide_files: list, title: str = "PPT Preview", notes=None) -> str:
    """Build a single-file paged preview; each slide in an isolated iframe srcdoc.

    ``notes`` is an optional list of dicts from a notes.json ``slides`` array.
    Each entry with a non-empty ``notes`` field is injected as a ``data-notes``
    HTML-escaped attribute on the corresponding iframe; the outer wrapper JS
    reads it to populate the speaker notes panel.
    """
    # Build notes lookup: slide_number (1-indexed) → stripped text.
    # Defensive: skip non-dict entries and entries with non-numeric slide_number.
    notes_by_slide: dict = {}
    for e in (notes or []):
        if not isinstance(e, dict):
            continue
        try:
            k = int(e.get("slide_number"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        notes_by_slide[k] = str(e.get("notes") or "").strip()

    slides_data = []  # (srcdoc_escaped, slide_title, note_attr)

    for i, f in enumerate(slide_files):
        html_dir = Path(f).parent
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()

        content = inline_images(content, html_dir)
        slide_title = _slide_title(content, i + 1)
        escaped = html_module.escape(content, quote=True)
        note_text = notes_by_slide.get(i + 1, "")
        note_attr = f' data-notes="{html_module.escape(note_text, quote=True)}"' if note_text else ""
        slides_data.append((escaped, slide_title, note_attr))

    total = len(slides_data)
    escaped_title = html_module.escape(title)

    iframes = []
    for i, (srcdoc, slide_title, note_attr) in enumerate(slides_data):
        display = "block" if i == 0 else "none"
        escaped_slide_title = html_module.escape(slide_title, quote=True)
        # sandbox="" gives each srcdoc frame an opaque (null) origin — no allow-same-origin,
        # so a crafted slide cannot read file:// siblings or the parent document (LLM05/CWE-79).
        iframes.append(
            f'<iframe class="slide-frame" id="slide-{i}" '
            f'data-slide-title="{escaped_slide_title}"'
            f'{note_attr} '
            f'style="display:{display}" '
            f'srcdoc="{srcdoc}" '
            f'sandbox="" '
            f'frameborder="0" scrolling="no"></iframe>'
        )

    iframes_block = '\n'.join(iframes)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0a0a;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }}
  .stage {{
    margin: 12px auto 0;
    width: min(1280px, 90vw);
    aspect-ratio: 16/9;
    overflow: hidden;
    border-radius: 8px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    background: #111;
    position: relative;
  }}
  .slide-frame {{
    width: 1280px; height: 720px;
    transform-origin: top left;
    position: absolute; top: 0; left: 0;
    border: none;
  }}
  .controls {{
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 12px;
    align-items: center;
    width: min(1280px, 90vw);
    margin: 8px auto 12px;
  }}
  .nav-group {{ display: flex; gap: 8px; }}
  .nav-btn, .utility-btn {{
    border: 1px solid rgba(255,255,255,.2);
    background: rgba(255,255,255,.1);
    color: #fff;
    border-radius: 8px;
    padding: 6px 14px;
    cursor: pointer;
    font-size: 14px;
  }}
  .nav-btn:hover, .utility-btn:hover {{ background: rgba(255,255,255,.18); }}
  .nav-btn:disabled {{ opacity: .35; cursor: default; }}
  .progress-track {{
    height: 6px;
    border-radius: 999px;
    background: rgba(255,255,255,.15);
    overflow: hidden;
  }}
  .progress-bar {{
    height: 100%;
    width: 0;
    background: rgba(255,255,255,.7);
    transition: width .18s ease;
  }}
  .counter {{
    font-size: 14px;
    color: rgba(255,255,255,.6);
    min-width: 72px;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }}
  .slide-jump {{
    display: none;
    position: fixed;
    inset: 10% 15%;
    z-index: 40;
    background: #1a1a1a;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 12px;
    padding: 20px;
    overflow: auto;
    box-shadow: 0 24px 80px rgba(0,0,0,.6);
  }}
  .slide-jump.open {{ display: block; }}
  .jump-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    color: #fff;
  }}
  .jump-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }}
  .jump-item {{
    padding: 10px;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: 8px;
    background: rgba(255,255,255,.06);
    color: #fff;
    cursor: pointer;
    text-align: left;
    font-size: 13px;
  }}
  .jump-item:hover {{ background: rgba(255,255,255,.14); }}
  .scrim {{
    display: none;
    position: fixed;
    inset: 0;
    z-index: 39;
    background: rgba(0,0,0,.6);
  }}
  .scrim.open {{ display: block; }}
  .notes-panel {{
    display: none;
    position: absolute;
    bottom: 0;
    right: 0;
    min-width: 320px;
    max-width: 40%;
    max-height: 60%;
    overflow-y: auto;
    background: rgba(15,15,15,.92);
    color: #fff;
    font-size: 13px;
    line-height: 1.5;
    padding: 12px 16px;
    border-radius: 8px 0 0 0;
    white-space: pre-wrap;
    box-sizing: border-box;
    z-index: 10;
  }}
  .notes-panel.open {{ display: block; }}
</style>
</head>
<body>
<div class="stage" id="stage">
{iframes_block}
<div id="notesPanel" class="notes-panel"></div>
</div>
<div class="controls">
  <div class="nav-group">
    <button class="nav-btn" id="prevBtn" aria-label="Previous slide">&#8592;</button>
    <button class="nav-btn" id="nextBtn" aria-label="Next slide">&#8594;</button>
    <button class="utility-btn" id="jumpBtn">Slides</button>
  </div>
  <div class="progress-track" aria-hidden="true">
    <div class="progress-bar" id="progressBar"></div>
  </div>
  <div class="nav-group" style="justify-content:flex-end">
    <span class="counter" id="counter">1 / {total}</span>
    <button class="utility-btn" id="notesBtn">Notes</button>
  </div>
</div>
<div class="scrim" id="scrim"></div>
<div class="slide-jump" id="slideJump" role="dialog" aria-modal="true" aria-label="Slide navigator">
  <div class="jump-header">
    <strong>Jump to slide</strong>
    <button class="utility-btn" id="closeJump" aria-label="Close navigator">&#x2715;</button>
  </div>
  <div class="jump-grid" id="jumpGrid"></div>
</div>
<script>
(function() {{
  const frames = Array.from(document.querySelectorAll('.slide-frame'));
  const total = frames.length;
  let cur = 0;
  let blanked = false;
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const jumpBtn = document.getElementById('jumpBtn');
  const closeJumpBtn = document.getElementById('closeJump');
  const slideJump = document.getElementById('slideJump');
  const scrim = document.getElementById('scrim');
  const jumpGrid = document.getElementById('jumpGrid');
  const counter = document.getElementById('counter');
  const progressBar = document.getElementById('progressBar');
  const stage = document.getElementById('stage');
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

  function show(i) {{
    frames.forEach((f, idx) => {{ f.style.display = idx === i ? 'block' : 'none'; }});
    blanked = false;
    counter.textContent = (i + 1) + ' / ' + total;
    progressBar.style.width = (total ? ((i + 1) / total * 100) : 100) + '%';
    prevBtn.disabled = i === 0;
    nextBtn.disabled = i === total - 1;
    updateNotes(i);
  }}

  function go(d) {{
    if (blanked) {{ show(cur); return; }}
    const n = Math.max(0, Math.min(total - 1, cur + d));
    if (n !== cur) {{ cur = n; show(cur); }}
  }}

  function openJump() {{
    slideJump.classList.add('open');
    scrim.classList.add('open');
    const first = jumpGrid.querySelector('.jump-item');
    if (first) first.focus();
  }}

  function closeJump() {{
    slideJump.classList.remove('open');
    scrim.classList.remove('open');
    jumpBtn.focus();
  }}

  // Populate jump grid from data-slide-title attributes
  frames.forEach((f, i) => {{
    const btn = document.createElement('button');
    btn.className = 'jump-item';
    btn.textContent = (i + 1) + '. ' + (f.dataset.slideTitle || 'Slide ' + (i + 1));
    btn.addEventListener('click', () => {{ cur = i; show(i); closeJump(); }});
    jumpGrid.appendChild(btn);
  }});

  prevBtn.addEventListener('click', () => go(-1));
  nextBtn.addEventListener('click', () => go(1));
  jumpBtn.addEventListener('click', openJump);
  closeJumpBtn.addEventListener('click', closeJump);
  scrim.addEventListener('click', closeJump);
  notesBtn.addEventListener('click', toggleNotes);

  document.addEventListener('keydown', e => {{
    if (!total) return;
    if (slideJump.classList.contains('open')) {{
      if (e.key === 'Escape') {{ e.preventDefault(); closeJump(); }}
      return;
    }}
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') {{
      e.preventDefault(); go(1);
    }} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {{
      e.preventDefault(); go(-1);
    }} else if (e.key === 'Home') {{
      e.preventDefault(); cur = 0; show(0);
    }} else if (e.key === 'End') {{
      e.preventDefault(); cur = total - 1; show(total - 1);
    }} else if (e.key.toLowerCase() === 'g') {{
      e.preventDefault(); openJump();
    }} else if (e.key.toLowerCase() === 'b') {{
      e.preventDefault();
      if (blanked) {{ show(cur); }} else {{ frames[cur].style.display = 'none'; blanked = true; }}
    }} else if (e.key.toLowerCase() === 'n') {{
      e.preventDefault(); toggleNotes();
    }}
  }});

  function resize() {{
    const sw = stage.clientWidth, sh = stage.clientHeight;
    const scale = Math.min(sw / 1280, sh / 720);
    frames.forEach(f => {{ f.style.transform = 'scale(' + scale + ')'; }});
  }}
  window.addEventListener('resize', resize);
  resize();
  show(0);
}})();
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="HTML Packager for PPT Agent")
    parser.add_argument("path", help="Directory containing slide HTML files")
    parser.add_argument("-o", "--output", default=None, help="Output HTML file")
    parser.add_argument("--title", default=None,
                        help="浏览器标签页标题；省略则自动从首页封面/deck 目录名推断")
    parser.add_argument("--notes", default=None, metavar="PATH",
                        help="Path to a notes.json file; embeds speaker notes into the HTML")
    args = parser.parse_args()

    slides_dir = Path(args.path)
    if not slides_dir.is_dir():
        print(f"Error: {slides_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    ok, msg = check_deliverable_gate(slides_dir.parent, deck_required=True)
    if not ok:
        print(f"error: deliverable gate not satisfied — {msg}", file=sys.stderr)
        sys.exit(1)

    html_files = collect_slides(slides_dir)
    if not html_files:
        print(f"Error: No HTML files in {slides_dir}", file=sys.stderr)
        sys.exit(1)

    # Default output carries the deck-slug (parent dir name) so a file
    # downloaded on its own still reads as "<topic>-preview.html".
    deck_slug = slides_dir.parent.name
    default_name = f"{deck_slug}-preview.html" if deck_slug else "preview.html"
    output_path = args.output or str(slides_dir.parent / default_name)

    title = args.title or derive_title(html_files, slides_dir)

    # Load notes if provided; validate before building.
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
        if not isinstance(notes_json, dict):
            print(f"Error: notes file must be a JSON object: {notes_path}", file=sys.stderr)
            sys.exit(1)
        if notes_json.get("schema_version") != "1":
            print(
                f"Error: unsupported notes schema_version (expected '1'): {notes_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not isinstance(notes_json.get("slides"), list):
            print(f"Error: 'slides' must be a list in {notes_path}", file=sys.stderr)
            sys.exit(1)
        notes = notes_json["slides"]

    result = build_preview([str(p) for p in html_files], title=title, notes=notes)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Created: {output_path} ({len(html_files)} slides)")

    # Auto-generate notes stub alongside HTML if it doesn't exist yet.
    notes_slug = deck_slug if deck_slug else "deck"
    notes_stub_path = Path(output_path).parent / f"{notes_slug}-notes.json"
    if not notes_stub_path.exists():
        stub = build_notes_stub([str(p) for p in html_files])
        notes_stub_path.write_text(
            json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Created notes stub: {notes_stub_path}")


if __name__ == "__main__":
    main()

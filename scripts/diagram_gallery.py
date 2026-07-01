#!/usr/bin/env python3
"""diagram_gallery.py — 图解配方可视化画廊生成器

把 references/blocks/diagram*.md + timeline.md 里每个配方的第一段 paste-ready
HTML 模板抽出来，套上一套 canonical 主题 :root（deck 变量），渲染成 PNG，并生成
index.html 网格预览 —— 让本会话新增的图解 block 可以直接被"看到"。

与 gallery.py 互补：gallery.py 预览 26 种风格，本脚本预览图解配方本身。

用法:
    python3 scripts/diagram_gallery.py                 # 生成 HTML（dark 主题）
    python3 scripts/diagram_gallery.py --style light   # light / editorial / dark
    python3 scripts/diagram_gallery.py --screenshots   # + 调 html2png 出 PNG

输出:
    ppt-output/diagram-gallery/<id>.html / .png
    ppt-output/diagram-gallery/index.html
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = ROOT / "references" / "blocks"
OUT = ROOT / "ppt-output" / "diagram-gallery"

RECIPE_HEADING = re.compile(r"^###\s+(.*?)\s*\((.+?)\)\s*$", re.MULTILINE)
HTML_BLOCK = re.compile(r"```html\s*\n(.*?)```", re.DOTALL)

# canonical deck 调色板（与真实管线一致的变量名，非 style-gallery 的 ad-hoc 命名）
PALETTES = {
    "dark": """:root{--bg-primary:#0a0e1a;--bg-secondary:#121829;--card-bg-from:#161d2e;--card-bg-to:#0f1422;
--card-border:#2a3447;--card-radius:8px;--text-primary:#e8eef7;--text-secondary:#94a3b8;
--accent-1:#22d3ee;--accent-2:#6366f1;--accent-3:#f59e0b;--accent-4:#34d399;--font-primary:-apple-system,'Inter',sans-serif;}""",
    "light": """:root{--bg-primary:#ffffff;--bg-secondary:#f6f8fb;--card-bg-from:#ffffff;--card-bg-to:#f1f5fb;
--card-border:#d2dbe8;--card-radius:8px;--text-primary:#0a1d3a;--text-secondary:#64748b;
--accent-1:#2563eb;--accent-2:#7c3aed;--accent-3:#0891b2;--accent-4:#059669;--font-primary:-apple-system,'Inter',sans-serif;}""",
    "editorial": """:root{--bg-primary:#f4eee4;--bg-secondary:#ebe1d2;--card-bg-from:#fbf7f0;--card-bg-to:#efe6d6;
--card-border:#cbbb9f;--card-radius:6px;--text-primary:#3a2e22;--text-secondary:#8a7a64;
--accent-1:#a0522d;--accent-2:#6b4423;--accent-3:#c9803a;--accent-4:#7d8c5c;--font-primary:Georgia,serif;}""",
}

SHELL = """<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><style>
{root}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{width:1280px;height:720px;overflow:hidden;background:var(--bg-primary);color:var(--text-primary);
display:flex;align-items:center;justify-content:center;padding:48px;}}
</style></head><body>{body}</body></html>"""


def recipes() -> list[tuple[str, str, str, str]]:
    """(file, title, id, first_html_template) for every recipe."""
    out = []
    files = sorted(BLOCKS.glob("diagram*.md")) + [BLOCKS / "timeline.md"]
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        heads = list(RECIPE_HEADING.finditer(text))
        for i, m in enumerate(heads):
            start = m.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = text[start:end]
            hb = HTML_BLOCK.search(body)
            if hb:
                out.append((f.name, m.group(1).strip(), m.group(2).strip(), hb.group(1).strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="dark", choices=list(PALETTES))
    ap.add_argument("--screenshots", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    root = PALETTES[args.style]

    recs = recipes()
    for _file, _title, rid, tpl in recs:
        (OUT / f"{rid}.html").write_text(SHELL.format(root=root, body=tpl), encoding="utf-8")

    if args.screenshots:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "html2png.py"), str(OUT), "-o", str(OUT), "--scale", "0.5"],
                       check=False)

    # index
    cards = "\n".join(
        f'<figure><div class="thumb"><img src="{rid}.png" alt="{rid}" '
        f'onerror="this.style.display=\'none\'"></div>'
        f'<figcaption><b>{title}</b><code>{rid}</code><span>{file}</span></figcaption></figure>'
        for file, title, rid, _tpl in recs
    )
    index = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<title>Diagram Recipe Gallery ({args.style})</title><style>
body{{font-family:-apple-system,'Inter',sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:32px;}}
h1{{font-size:22px;}} p{{color:#8b949e;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:20px;margin-top:24px;}}
figure{{margin:0;background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden;}}
.thumb{{background:#0a0e1a;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;}}
.thumb img{{width:100%;height:100%;object-fit:contain;}}
figcaption{{padding:10px 14px;display:flex;flex-direction:column;gap:2px;}}
figcaption code{{color:#58a6ff;font-size:12px;}} figcaption span{{color:#6e7681;font-size:11px;}}
</style></head><body>
<h1>Diagram Recipe Gallery — {len(recs)} recipes · {args.style} theme</h1>
<p>本会话新增的图解配方渲染预览。用 <code>--screenshots</code> 生成 PNG，<code>--style light|editorial</code> 换主题。</p>
<div class="grid">{cards}</div></body></html>"""
    (OUT / "index.html").write_text(index, encoding="utf-8")
    print(f"diagram_gallery: {len(recs)} recipes -> {OUT}/index.html (style={args.style}, screenshots={args.screenshots})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

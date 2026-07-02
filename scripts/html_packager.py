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
import os
import re
import sys
from pathlib import Path


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


def derive_title(slide_files: list, slides_dir: Path) -> str:
    """从首页封面推断标题，失败则回退到 deck 目录名。

    优先级：首页 <title> -> 首页最大标题(<h1>) -> deck 目录名(slug 美化)。
    这样每个 deck 的 preview.html 标签页都能自我区分。
    """
    def strip_tags(s: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

    if slide_files:
        try:
            first = Path(slide_files[0]).read_text(encoding="utf-8")
        except OSError:
            first = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", first, re.I | re.S)
        if m:
            t = strip_tags(m.group(1))
            if t and t.lower() not in ("document", "ppt preview", "pptx preview"):
                return t
        m = re.search(r"<h1[^>]*>(.*?)</h1>", first, re.I | re.S)
        if m:
            t = strip_tags(m.group(1))
            if t:
                return t

    # 回退：deck 目录名（slides/ 的父目录）
    slug = slides_dir.parent.name or slides_dir.name
    return slug.replace("-", " ").replace("_", " ").strip() or "PPT Preview"


def build_preview(slide_files: list, title: str = "PPT Preview") -> str:
    """构建可翻页的预览 HTML，每页用独立 iframe 实现 CSS 隔离。"""
    slides_srcdoc = []

    for f in slide_files:
        html_dir = Path(f).parent
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()

        # 内联图片为 base64
        content = inline_images(content, html_dir)

        # 转义为 srcdoc 安全内容（& -> &amp;  " -> &quot;）
        escaped = html_module.escape(content, quote=True)
        slides_srcdoc.append(escaped)

    total = len(slides_srcdoc)
    escaped_title = html_module.escape(title)

    # 生成 iframe 列表
    iframes = []
    for i, srcdoc in enumerate(slides_srcdoc):
        display = "block" if i == 0 else "none"
        iframes.append(
            f'<iframe class="slide-frame" id="slide-{i}" '
            f'style="display:{display}" '
            f'srcdoc="{srcdoc}" '
            f'sandbox="allow-same-origin" '
            f'frameborder="0" scrolling="no"></iframe>'
        )

    iframes_block = '\n'.join(iframes)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
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
    font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }}
  .toolbar {{
    position: fixed; top: 0; left: 0; right: 0; height: 48px;
    background: rgba(10,10,10,0.95); border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex; align-items: center; justify-content: center; gap: 16px;
    z-index: 1000; backdrop-filter: blur(10px);
  }}
  .toolbar button {{
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
    color: #fff; padding: 6px 16px; border-radius: 6px; cursor: pointer;
    font-size: 14px; transition: background 0.2s;
  }}
  .toolbar button:hover {{ background: rgba(255,255,255,0.2); }}
  .toolbar button:disabled {{ opacity: 0.3; cursor: not-allowed; }}
  .page-info {{ font-size: 14px; color: rgba(255,255,255,0.7); min-width: 80px; text-align: center; }}
  .deck-title {{
    position: absolute; left: 16px; max-width: 40vw;
    font-size: 14px; color: rgba(255,255,255,0.55);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .stage {{
    margin-top: 60px; width: 90vw; max-width: 1280px;
    aspect-ratio: 16/9; overflow: hidden;
    border-radius: 8px; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    background: #111; position: relative;
  }}
  .slide-frame {{
    width: 1280px; height: 720px;
    transform-origin: top left;
    position: absolute; top: 0; left: 0;
    border: none;
  }}
  .nav-hint {{
    position: fixed; bottom: 12px;
    color: rgba(255,255,255,0.25); font-size: 12px;
  }}
</style>
</head>
<body>
<div class="toolbar">
  <span class="deck-title" title="{escaped_title}">{escaped_title}</span>
  <button id="btn-prev" onclick="nav(-1)">Prev</button>
  <span class="page-info" id="page-info">1 / {total}</span>
  <button id="btn-next" onclick="nav(1)">Next</button>
</div>
<div class="stage" id="stage">
{iframes_block}
</div>
<div class="nav-hint">Arrow keys to navigate</div>
<script>
let cur = 0;
const frames = document.querySelectorAll('.slide-frame');
const total = frames.length;
const info = document.getElementById('page-info');
const stage = document.getElementById('stage');

function resize() {{
  const sw = stage.clientWidth, sh = stage.clientHeight;
  const scale = Math.min(sw / 1280, sh / 720);
  frames.forEach(f => f.style.transform = 'scale(' + scale + ')');
}}
function show(i) {{
  frames.forEach((f, idx) => f.style.display = idx === i ? 'block' : 'none');
  info.textContent = (i+1) + ' / ' + total;
  document.getElementById('btn-prev').disabled = i === 0;
  document.getElementById('btn-next').disabled = i === total - 1;
}}
function nav(d) {{
  const n = cur + d;
  if (n >= 0 && n < total) {{ cur = n; show(cur); }}
}}
document.addEventListener('keydown', e => {{
  if (e.key==='ArrowLeft'||e.key==='ArrowUp') nav(-1);
  if (e.key==='ArrowRight'||e.key==='ArrowDown'||e.key===' ') nav(1);
}});
window.addEventListener('resize', resize);
resize();
show(0);
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="HTML Packager for PPT Agent")
    parser.add_argument("path", help="Directory containing slide HTML files")
    parser.add_argument("-o", "--output", default=None, help="Output HTML file")
    parser.add_argument("--title", default=None,
                        help="浏览器标签页标题；省略则自动从首页封面/deck 目录名推断")
    args = parser.parse_args()

    slides_dir = Path(args.path)
    if not slides_dir.is_dir():
        print(f"Error: {slides_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    html_files = sorted(slides_dir.glob("*.html"))
    if not html_files:
        print(f"Error: No HTML files in {slides_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or str(slides_dir.parent / "preview.html")

    title = args.title or derive_title(html_files, slides_dir)

    result = build_preview(html_files, title=title)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Created: {output_path} ({len(html_files)} slides)")


if __name__ == "__main__":
    main()

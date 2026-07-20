#!/usr/bin/env python3
"""compare_gallery.py -- side-by-side mermaid_render vs mmdc comparison gallery.

Usage:
    python3 scripts/compare_gallery.py                 # all fixtures in tests/fixtures/
    python3 scripts/compare_gallery.py --open          # open in default browser after build
    python3 scripts/compare_gallery.py path/to/my.mmd  # specific file(s)

Output:
    ppt-output/compare/index.html    -- side-by-side gallery (open in browser)
    ppt-output/compare/ours/<name>.html  -- our impl HTML
    ppt-output/compare/mmdc/<name>.svg   -- mmdc SVG output
"""
from __future__ import annotations

import argparse
import html as _html_mod
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"
OUT_DIR = ROOT / "ppt-output" / "compare"

sys.path.insert(0, str(ROOT / "scripts"))
import mermaid_render


_PAGE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, Inter, sans-serif;
    background: #f5f4f0;
    color: #1a1a18;
}
header {
    padding: 16px 24px;
    background: #1a1a18;
    color: #f5f4f0;
    display: flex;
    align-items: center;
    gap: 12px;
}
header h1 { font-size: 16px; font-weight: 700; }
header span { font-size: 12px; opacity: 0.6; }
nav {
    padding: 8px 24px;
    background: #fff;
    border-bottom: 1px solid #ddd;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
nav a {
    font-size: 11px;
    padding: 3px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    text-decoration: none;
    color: #333;
    background: #f9f9f7;
}
nav a:hover { background: #e8e5e0; }
.diagram-section {
    padding: 24px;
    border-bottom: 1px solid #ddd;
    background: #fff;
    margin-bottom: 12px;
}
.diagram-section h2 {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #eee;
}
.comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.pane-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666;
    margin-bottom: 8px;
    padding: 4px 8px;
    border-radius: 4px;
}
.pane-ours .pane-header { background: #e8f4e8; color: #2d6e3a; }
.pane-mmdc .pane-header { background: #e8ecf8; color: #2a3f8f; }
.render-box {
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: auto;
    background: #fff;
    min-height: 120px;
    padding: 8px;
}
.pane-ours .render-box { border-color: #b8d8b8; }
.pane-mmdc .render-box { border-color: #b8c4e0; }
.error-box {
    background: #fff8f8;
    border: 1px solid #f0c0c0;
    border-radius: 6px;
    padding: 12px;
    font-family: monospace;
    font-size: 11px;
    color: #c0392b;
    white-space: pre-wrap;
    word-break: break-all;
}
details {
    margin-top: 8px;
}
details summary {
    font-size: 10px;
    color: #888;
    cursor: pointer;
    user-select: none;
}
details pre {
    margin-top: 6px;
    padding: 8px;
    background: #f7f6f2;
    border: 1px solid #e0ddd8;
    border-radius: 4px;
    font-size: 10px;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 200px;
    overflow: auto;
}
.status-badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 600;
    margin-left: 8px;
    vertical-align: middle;
}
.badge-ok { background: #d4edda; color: #1e6e34; }
.badge-err { background: #f8d7da; color: #842029; }
"""


def _run_mmdc(src: str, out_svg: Path) -> tuple[bool, str]:
    """Run mmdc and return (success, stderr)."""
    with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False) as f:
        f.write(src)
        tmp = Path(f.name)
    try:
        r = subprocess.run(
            ["mmdc", "-i", str(tmp), "-o", str(out_svg), "--quiet"],
            capture_output=True, text=True, timeout=30
        )
        ok = r.returncode == 0 and out_svg.exists()
        return ok, r.stderr.strip()
    except Exception as e:
        return False, str(e)
    finally:
        tmp.unlink(missing_ok=True)


def _render_ours(src: str) -> tuple[str | None, str]:
    """Return (html_fragment, error_msg). html_fragment is None on error."""
    try:
        return mermaid_render.to_html(src), ""
    except Exception as e:
        return None, str(e)


def _build_gallery(mmd_files: list[Path], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ours").mkdir(exist_ok=True)
    (out_dir / "mmdc").mkdir(exist_ok=True)

    sections: list[str] = []
    nav_items: list[str] = []

    for mmd_path in sorted(mmd_files):
        name = mmd_path.stem
        src = mmd_path.read_text(encoding="utf-8").strip()

        ours_html, ours_err = _render_ours(src)
        mmdc_svg_path = out_dir / "mmdc" / f"{name}.svg"
        mmdc_ok, mmdc_err = _run_mmdc(src, mmdc_svg_path)

        # Save our HTML for iframe-less embedding
        if ours_html:
            (out_dir / "ours" / f"{name}.html").write_text(ours_html, encoding="utf-8")

        ours_status = "ok" if ours_html else "err"
        mmdc_status = "ok" if mmdc_ok else "err"

        nav_items.append(
            f'<a href="#{name}">{name}'
            f'<span class="status-badge badge-{ours_status}">O</span>'
            f'<span class="status-badge badge-{mmdc_status}">M</span>'
            f'</a>'
        )

        src_escaped = _html_mod.escape(src)

        if ours_html:
            ours_content = f'<div class="render-box">{ours_html}</div>'
        else:
            ours_content = (
                f'<div class="error-box">{_html_mod.escape(ours_err)}</div>'
            )

        if mmdc_ok:
            svg_content = mmdc_svg_path.read_text(encoding="utf-8")
            # Strip XML declaration if present
            if svg_content.startswith("<?xml"):
                svg_content = svg_content[svg_content.index("<svg"):]
            mmdc_content = (
                f'<div class="render-box" style="overflow:auto;">'
                f'{svg_content}</div>'
            )
        else:
            mmdc_content = (
                f'<div class="error-box">{_html_mod.escape(mmdc_err or "mmdc failed (no output)")}</div>'
            )

        sections.append(f"""
<div class="diagram-section" id="{name}">
  <h2>{_html_mod.escape(name)}
    <span class="status-badge badge-{ours_status}">ours: {ours_status}</span>
    <span class="status-badge badge-{mmdc_status}">mmdc: {mmdc_status}</span>
  </h2>
  <div class="comparison-grid">
    <div class="pane-ours">
      <div class="pane-header">Our renderer</div>
      {ours_content}
    </div>
    <div class="pane-mmdc">
      <div class="pane-header">mmdc 11.15.0</div>
      {mmdc_content}
    </div>
  </div>
  <details>
    <summary>Mermaid source</summary>
    <pre>{src_escaped}</pre>
  </details>
</div>""")

    nav_html = "\n".join(nav_items)
    sections_html = "\n".join(sections)

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>mermaid_render vs mmdc — comparison gallery</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <header>
    <h1>mermaid_render vs mmdc comparison</h1>
    <span>O = ours &nbsp;|&nbsp; M = mmdc &nbsp;|&nbsp; green = ok, red = error</span>
  </header>
  <nav>{nav_html}</nav>
  {sections_html}
</body>
</html>"""

    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    return index_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Build side-by-side mermaid_render vs mmdc gallery")
    ap.add_argument("files", nargs="*", help=".mmd files to include (default: all tests/fixtures/*.mmd)")
    ap.add_argument("--open", action="store_true", help="Open result in browser")
    args = ap.parse_args()

    if args.files:
        mmd_files = [Path(f).resolve() for f in args.files]
    else:
        mmd_files = sorted(FIXTURES_DIR.glob("*.mmd"))

    if not mmd_files:
        print("No .mmd files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Building comparison gallery for {len(mmd_files)} diagram(s)...")
    index_path = _build_gallery(mmd_files, OUT_DIR)
    print(f"Gallery: file://{index_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{index_path}")


if __name__ == "__main__":
    main()

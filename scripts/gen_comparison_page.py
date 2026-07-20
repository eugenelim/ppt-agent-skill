#!/usr/bin/env python3
"""Generate a side-by-side comparison page: committed baseline vs current render.

Usage:
    python scripts/gen_comparison_page.py [--output /path/to/out.html] [--theme light|dark|both]

Outputs a self-contained HTML page with all fixtures shown as:
  Left column  — committed baseline PNG (or "no baseline" if absent)
  Right column — freshly rendered PNG via _dispatch + playwright/html2png

Skips unsupported diagram types.
"""
from __future__ import annotations

import argparse
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_LIGHT = REPO_ROOT / "tests" / "snapshots" / "light"
SNAPSHOTS_DARK = REPO_ROOT / "tests" / "snapshots" / "dark"
HTML2PNG = REPO_ROOT / "scripts" / "html2png.py"
PPT_OUT = REPO_ROOT / "ppt-output"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _render(mmd_path: Path, theme: str, tmp_dir: Path) -> Path | None:
    from mermaid_layout import _dispatch, make_page  # type: ignore

    src = mmd_path.read_text()
    try:
        fragment = _dispatch(src, None, 800)
    except ValueError:
        return None

    html = make_page(fragment, theme=theme)
    PPT_OUT.mkdir(exist_ok=True)
    html_path = PPT_OUT / f"{mmd_path.stem}-{theme}-compare.html"
    html_path.write_text(html, encoding="utf-8")
    png_dir = tmp_dir / "png"
    png_dir.mkdir(exist_ok=True)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(HTML2PNG),
                str(html_path),
                "-o",
                str(png_dir),
                "--scale",
                "1",
                "--fullpage",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  render failed: {mmd_path.stem}: {e}", file=sys.stderr)
        return None
    finally:
        html_path.unlink(missing_ok=True)

    out = png_dir / f"{mmd_path.stem}-{theme}-compare.png"
    if not out.exists():
        # html2png may strip the theme suffix — try plain name
        alt = png_dir / f"{mmd_path.stem}.png"
        if alt.exists():
            out = alt
    return out if out.exists() else None


def _img_tag(png: Path | None, label: str, width: int = 400) -> str:
    if png is None or not png.exists():
        return f'<div class="missing">no {label}</div>'
    b64 = _b64(png)
    return f'<img src="data:image/png;base64,{b64}" width="{width}" alt="{label}" />'


def build_page(themes: list[str], output: Path) -> None:
    fixtures = sorted(FIXTURES_DIR.glob("*.mmd"))
    rows_html: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for i, fixture in enumerate(fixtures):
            stem = fixture.stem
            print(f"[{i+1}/{len(fixtures)}] {stem} ...", flush=True)
            for theme in themes:
                baseline_dir = SNAPSHOTS_LIGHT if theme == "light" else SNAPSHOTS_DARK
                baseline = baseline_dir / f"{stem}.png"
                fresh = _render(fixture, theme, tmp_path)

                if fresh is None and not baseline.exists():
                    # unsupported + no baseline — skip
                    continue

                label = f"{stem} [{theme}]"
                baseline_img = _img_tag(baseline if baseline.exists() else None, "baseline")
                fresh_img = _img_tag(fresh, "current")

                status = "new" if not baseline.exists() else ("unsupported" if fresh is None else "compare")
                rows_html.append(f"""
  <tr class="{status}">
    <td class="name">{label}</td>
    <td class="img baseline">{baseline_img}<br/><span class="caption">committed baseline</span></td>
    <td class="img current">{fresh_img}<br/><span class="caption">current render</span></td>
  </tr>""")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Mermaid snapshot comparison — baseline vs current</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #111; color: #ddd; padding: 1rem; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.5rem; }}
  p.meta {{ font-size: 0.85rem; color: #888; margin: 0 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  tr + tr {{ border-top: 1px solid #333; }}
  td {{ vertical-align: top; padding: 0.5rem 0.75rem; }}
  td.name {{ width: 200px; font-size: 0.85rem; font-weight: 600; color: #aaa; white-space: nowrap; }}
  td.img {{ text-align: center; }}
  td.img img {{ max-width: 400px; border: 1px solid #444; border-radius: 4px; }}
  span.caption {{ font-size: 0.75rem; color: #666; }}
  div.missing {{ color: #666; font-style: italic; font-size: 0.8rem; padding: 2rem 0; }}
  tr.new td.name::after {{ content: " NEW"; color: #4af; font-size: 0.7rem; }}
  tr.unsupported {{ opacity: 0.5; }}
</style>
</head>
<body>
<h1>Mermaid snapshot comparison — committed baseline vs current render</h1>
<p class="meta">Left: committed PNG baseline &nbsp;·&nbsp; Right: freshly rendered current output</p>
<table>
  <thead>
    <tr>
      <th>Fixture</th>
      <th>Baseline (committed)</th>
      <th>Current render</th>
    </tr>
  </thead>
  <tbody>
{"".join(rows_html)}
  </tbody>
</table>
</body>
</html>"""

    output.write_text(page, encoding="utf-8")
    print(f"\nWrote comparison page → {output}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default=str(REPO_ROOT / "ppt-output" / "snapshot-comparison.html"))
    p.add_argument("--theme", default="light", choices=["light", "dark", "both"])
    args = p.parse_args()
    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    out = Path(args.output)
    out.parent.mkdir(exist_ok=True)
    build_page(themes, out)


if __name__ == "__main__":
    main()

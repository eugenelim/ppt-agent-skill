#!/usr/bin/env python3
"""compare_gallery.py -- side-by-side mermaid_render vs mmdc comparison gallery.

Usage:
    python3 tools/compare_gallery.py                 # all fixtures in tests/fixtures/
    python3 tools/compare_gallery.py --open          # open in default browser after build
    python3 tools/compare_gallery.py path/to/my.mmd  # specific file(s)
    python3 tools/compare_gallery.py --output-dir PATH       # write gallery to PATH/
    python3 tools/compare_gallery.py --metadata-only         # write only metadata.json
    python3 tools/compare_gallery.py --width-hint 800        # force renderer width hint

Output:
    <output-dir>/index.html          -- side-by-side gallery (open in browser)
    <output-dir>/ours/<name>.html    -- our impl HTML
    <output-dir>/mmdc/<name>.svg     -- mmdc SVG output
    <output-dir>/metadata.json       -- provenance record for this gallery run
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html as _html_mod
import json
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"
OUT_DIR = ROOT / "ppt-output" / "compare"

sys.path.insert(0, str(ROOT / "scripts"))
import mermaid_render

_RENDERER_SCHEMA_VERSION = "2026-07-21"


def _assert_module_provenance(repo_root: Path) -> None:
    """Exit with an error if the imported mermaid_render is not from this checkout."""
    module_file = Path(mermaid_render.__file__).resolve()
    repo_resolved = repo_root.resolve()
    try:
        module_file.relative_to(repo_resolved)
    except ValueError:
        print(
            f"ERROR: mermaid_render imported from {module_file} "
            f"which is outside the repository root {repo_resolved}. "
            "Gallery generation aborted to prevent stale-source results.",
            file=sys.stderr,
        )
        sys.exit(1)


def _collect_metadata(
    mmd_files: list[Path],
    out_dir: Path,
    width_hint: int,
    cli_args: list[str],
) -> dict:
    """Gather provenance data for the current gallery run."""
    import PIL
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    dirty_out = subprocess.run(
        ["git", "status", "--short"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    mmdc_ver = subprocess.run(
        ["mmdc", "--version"], capture_output=True, text=True
    ).stdout.strip()

    # Chromium version via playwright (best-effort)
    chromium_version = None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            chromium_version = b.version
            b.close()
    except Exception:
        pass

    # Playwright version (best-effort)
    playwright_version = None
    try:
        import playwright
        playwright_version = playwright.__version__
    except Exception:
        pass

    # Resolved font path and family (best-effort via _text module if present)
    resolved_font_path = None
    resolved_font_family = None
    try:
        from mermaid_render.layout._text import resolve_font
        fp, fam = resolve_font()
        resolved_font_path = str(fp) if fp else None
        resolved_font_family = fam
    except Exception:
        pass

    fixture_records = []
    for f in mmd_files:
        data = f.read_bytes()
        fixture_records.append({
            "path": str(f.relative_to(ROOT)),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    # SHA256 of key renderer source files
    strategies_file = ROOT / "scripts" / "mermaid_render" / "layout" / "_strategies.py"
    text_file = ROOT / "scripts" / "mermaid_render" / "layout" / "_text.py"
    strategies_sha = hashlib.sha256(strategies_file.read_bytes()).hexdigest() if strategies_file.exists() else None
    text_sha = hashlib.sha256(text_file.read_bytes()).hexdigest() if text_file.exists() else None
    module_path = str(Path(mermaid_render.__file__).resolve())

    return {
        "git_sha": sha,
        "git_dirty": bool(dirty_out),
        "generation_timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "pillow_version": PIL.__version__,
        "playwright_version": playwright_version,
        "chromium_version": chromium_version,
        "mmdc_version": mmdc_ver,
        "platform": platform.platform(),
        "renderer_width_hint": width_hint,
        "renderer_schema_version": _RENDERER_SCHEMA_VERSION,
        "mermaid_render_module_path": module_path,
        "strategies_sha256": strategies_sha,
        "text_sha256": text_sha,
        "output_dir": str(out_dir),
        "fixture_paths": [r["path"] for r in fixture_records],
        "fixture_sha256": {r["path"]: r["sha256"] for r in fixture_records},
        "resolved_font_path": resolved_font_path,
        "resolved_font_family": resolved_font_family,
        "command_line_args": cli_args,
    }


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
.nav-group { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-right: 12px; }
.nav-type { font-size: 11px; font-weight: 700; color: #555; padding: 2px 0; margin-right: 2px; white-space: nowrap; }
.type-group-header {
    padding: 10px 24px 6px;
    font-size: 13px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: #666;
    border-top: 2px solid #ddd; margin-top: 8px; background: #f9f8f5;
}
.badge-warn { background: #fff3cd; color: #856404; }
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
.comparison-grid > * {
    min-width: 0;
}
.mmdc-frame {
    width: 100%;
    border: none;
    display: block;
    min-height: 80px;
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
.render-frame {
    width: 100%;
    border: none;
    display: block;
    min-height: 80px;
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
.badge-unvalidated { background: #e9ecef; color: #6c757d; }
.badge-partial { background: #fff3cd; color: #856404; }
.status-lanes { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
"""


def _classify_status(
    render_exception: "BaseException | None" = None,
    geometry_errors: bool = False,
    geometry_warnings: bool = False,
) -> str:
    """Classify a render result into one of: ok / warning / invalid / error.

    Priority: error > invalid > warning > ok.
    - error: render raised an exception
    - invalid: geometry constraint violated (node overlap, clip, etc.)
    - warning: soft geometry concern (label near edge, tight spacing)
    - ok: clean render with no issues
    """
    if render_exception is not None:
        return "error"
    if geometry_errors:
        return "invalid"
    if geometry_warnings:
        return "warning"
    return "ok"


def _svg_aspect(svg_path: Path) -> tuple[float, float] | None:
    """Return (w, h) from root <svg> viewBox or width/height attributes, or None."""
    def _px(s: str) -> float:
        s = s.strip()
        for unit in ("px", "pt", "em", "rem", "%"):
            if s.endswith(unit):
                s = s[: -len(unit)]
                break
        try:
            return float(s)
        except ValueError:
            return 0.0

    try:
        root = ET.parse(svg_path).getroot()
        vb = root.get("viewBox")
        if vb:
            parts = [float(x) for x in vb.strip().replace(",", " ").split()]
            if len(parts) >= 4 and parts[2] and parts[3]:
                return parts[2], parts[3]
        w = _px(root.get("width") or "0")
        h = _px(root.get("height") or "0")
        if w and h:
            return w, h
    except Exception:
        pass
    return None


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


def _render_ours(src: str, width_hint: int = 0) -> tuple[str | None, str]:
    """Return (full_html, error_msg). full_html is None on error."""
    try:
        return mermaid_render.to_html(src, width_hint=width_hint), ""
    except Exception as e:
        return None, str(e)


def _diagram_type(name: str) -> str:
    """Extract diagram type prefix from fixture filename, e.g. 'flowchart-basic' → 'flowchart'."""
    return name.split("-")[0]


def _lane_badge_cls(status: str) -> str:
    """Return a CSS badge class for a four-status lane value."""
    if status == "pass":
        return "badge-ok"
    if status in ("fail",):
        return "badge-err"
    if status in ("partial", "warning"):
        return "badge-partial"
    return "badge-unvalidated"


def _build_gallery(mmd_files: list[Path], out_dir: Path, width_hint: int = 0) -> "tuple[Path, bool]":
    import shutil
    from collections import defaultdict
    from mermaid_render.layout._geometry import ValidationResult

    # Build into a temp directory; atomically replace dest at the end.
    tmp_dir = Path(tempfile.mkdtemp(prefix="gallery_tmp_"))
    try:
        return _build_gallery_into(mmd_files, tmp_dir, out_dir, width_hint)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def _build_gallery_into(
    mmd_files: list[Path],
    tmp_dir: Path,
    dest_dir: Path,
    width_hint: int,
) -> "tuple[Path, bool]":
    import shutil
    from collections import defaultdict
    from mermaid_render.layout._geometry import ValidationResult

    (tmp_dir / "ours").mkdir(exist_ok=True)
    (tmp_dir / "mmdc").mkdir(exist_ok=True)

    # Tuple: (name, src, vr, ours_err, mmdc_svg_path_in_tmp, mmdc_ok, mmdc_err)
    # vr: ValidationResult with four-status lanes.
    # ours_html is NOT held in memory — written to disk, re-read per section.
    type_results: dict[str, list[tuple]] = defaultdict(list)

    sorted_files = sorted(mmd_files)
    n_total = len(sorted_files)
    for i, mmd_path in enumerate(sorted_files):
        name = mmd_path.stem
        src = mmd_path.read_text(encoding="utf-8").strip()
        print(f"  [{i + 1}/{n_total}] {name} ...", end=" ", flush=True)

        ours_html, ours_err = _render_ours(src, width_hint=width_hint)
        if ours_html:
            (tmp_dir / "ours" / f"{name}.html").write_text(ours_html, encoding="utf-8")
            vr = mermaid_render.validate(src)
        else:
            vr = ValidationResult(render="fail", syntax_coverage="fail")

        mmdc_svg_path = tmp_dir / "mmdc" / f"{name}.svg"
        mmdc_ok, mmdc_err = _run_mmdc(src, mmdc_svg_path)

        print(
            f"render:{vr.render}  syntax:{vr.syntax_coverage}  "
            f"geometry:{vr.geometry}  oracle:{vr.mmdc_oracle}  "
            f"mmdc:{'ok' if mmdc_ok else 'err'}"
        )

        dtype = _diagram_type(name)
        type_results[dtype].append((name, src, vr, ours_err, mmdc_svg_path, mmdc_ok, mmdc_err))

    # Build nav — requires all results, so collected first.
    nav_parts: list[str] = []
    for dtype in sorted(type_results):
        items = type_results[dtype]
        n_render_ok = sum(1 for _, _, vr, _, _, _, _ in items if vr.render == "pass")
        n_items = len(items)
        group_status = "ok" if n_render_ok == n_items else ("err" if n_render_ok == 0 else "warn")
        badge_cls = "badge-ok" if group_status == "ok" else ("badge-err" if group_status == "err" else "badge-warn")
        nav_parts.append(
            f'<div class="nav-group">'
            f'<span class="nav-type">{_html_mod.escape(dtype)}'
            f'<span class="status-badge {badge_cls}">{n_render_ok}/{n_items}</span></span>'
        )
        for name, _, vr, _, _, mmdc_ok, _ in items:
            short = name[len(dtype):].lstrip("-") or name
            _obadge = _lane_badge_cls(vr.render)
            nav_parts.append(
                f'<a href="#{name}">{_html_mod.escape(short)}'
                f'<span class="status-badge {_obadge}">O</span>'
                f'<span class="status-badge badge-{"ok" if mmdc_ok else "err"}">M</span>'
                f'</a>'
            )
        nav_parts.append('</div>')

    total_diags = sum(len(v) for v in type_results.values())
    n_ours_ok = sum(1 for items in type_results.values() for _, _, vr, _, _, _, _ in items if vr.render == "pass")
    n_mmdc_ok = sum(m for items in type_results.values() for _, _, _, _, _, m, _ in items)
    n_syntax_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, _, _, _, _ in items if vr.syntax_coverage == "pass"
    )
    n_geom_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, _, _, _, _ in items if vr.geometry == "pass"
    )
    n_geom_total = sum(
        1 for dtype, items in type_results.items()
        for _, _, vr, _, _, _, _ in items
        if vr.geometry != "unvalidated"
    )
    n_oracle_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, _, _, _, _ in items if vr.mmdc_oracle == "pass"
    )
    n_types = len(type_results)
    nav_html = "\n".join(nav_parts)

    # Stream index.html — write one section at a time to avoid holding all HTML in memory.
    index_path = tmp_dir / "index.html"
    with index_path.open("w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>mermaid_render vs mmdc — comparison gallery</title>
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <header>
    <h1>mermaid_render vs mmdc comparison</h1>
    <span>{total_diags} diagrams &nbsp;·&nbsp; {n_types} types &nbsp;·&nbsp;
      render {n_ours_ok}/{total_diags} &nbsp;·&nbsp;
      syntax {n_syntax_ok}/{total_diags} &nbsp;·&nbsp;
      geometry {n_geom_ok}/{n_geom_total} &nbsp;·&nbsp;
      oracle {n_oracle_ok}/{total_diags} &nbsp;·&nbsp;
      mmdc {n_mmdc_ok}/{total_diags}</span>
  </header>
  <nav>{nav_html}</nav>
""")

        for dtype in sorted(type_results):
            items = type_results[dtype]
            f.write(f'  <div class="type-group-header" id="type-{dtype}">{_html_mod.escape(dtype)}</div>\n')
            for name, src, vr, ours_err, mmdc_svg_path, mmdc_ok, mmdc_err in items:
                mmdc_status = "ok" if mmdc_ok else "err"

                if vr.render == "pass":
                    ours_html = (tmp_dir / "ours" / f"{name}.html").read_text(encoding="utf-8")
                    ours_srcdoc = _html_mod.escape(ours_html, quote=True)
                    ours_content = (
                        '<div class="render-box">'
                        f'<iframe class="render-frame" srcdoc="{ours_srcdoc}"></iframe>'
                        '</div>'
                    )
                else:
                    ours_content = f'<div class="error-box">{_html_mod.escape(ours_err)}</div>'

                if mmdc_ok:
                    mmdc_url = f"mmdc/{quote(mmdc_svg_path.name)}"
                    aspect = _svg_aspect(mmdc_svg_path)
                    ar_style = (
                        f' style="aspect-ratio: {aspect[0]} / {aspect[1]};"'
                        if aspect else ""
                    )
                    mmdc_content = (
                        '<div class="render-box">'
                        f'<iframe class="mmdc-frame" src="{mmdc_url}"{ar_style}'
                        f' title="mmdc rendering of {_html_mod.escape(name, quote=True)}">'
                        '</iframe>'
                        '</div>'
                    )
                else:
                    mmdc_content = (
                        '<div class="error-box">'
                        f'{_html_mod.escape(mmdc_err or "mmdc failed (no output)")}'
                        '</div>'
                    )

                f.write(f"""
<div class="diagram-section" id="{name}">
  <h2>{_html_mod.escape(name)}</h2>
  <div class="status-lanes">
    <span class="status-badge {_lane_badge_cls(vr.render)} badge-render">render: {vr.render}</span>
    <span class="status-badge {_lane_badge_cls(vr.syntax_coverage)} badge-syntax">syntax: {vr.syntax_coverage}</span>
    <span class="status-badge {_lane_badge_cls(vr.geometry)} badge-geometry">geometry: {vr.geometry}</span>
    <span class="status-badge {_lane_badge_cls(vr.mmdc_oracle)} badge-oracle">oracle: {vr.mmdc_oracle}</span>
    <span class="status-badge badge-{"ok" if mmdc_ok else "err"}">mmdc: {mmdc_status}</span>
  </div>
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
    <pre>{_html_mod.escape(src)}</pre>
  </details>
</div>
""")

        f.write("""  <script>
    function fitRendererFrame(frame) {
      const doc = frame.contentDocument;
      if (!doc) return;
      const stage = doc.querySelector(".diagram");
      if (!stage) return;
      doc.body.style.padding = "0";
      doc.body.style.overflow = "hidden";
      stage.style.zoom = "1";
      const intrinsicWidth = stage.offsetWidth;
      const scale = Math.min(1, frame.clientWidth / intrinsicWidth);
      stage.style.zoom = String(scale);
      frame.style.height = `${Math.ceil(stage.offsetHeight * scale)}px`;
    }
    function attachFrameObservers() {
      document.querySelectorAll("iframe.render-frame").forEach(frame => {
        frame.addEventListener("load", () => fitRendererFrame(frame));
        new ResizeObserver(() => fitRendererFrame(frame)).observe(frame.parentElement);
      });
    }
    document.addEventListener("DOMContentLoaded", attachFrameObservers);
  </script>
</body>
</html>""")

    # "statediagram-v2" is unreachable: _diagram_type() returns name.split("-")[0],
    # so statediagram-v2 fixtures produce dtype="statediagram".
    _geom_validated_types = frozenset({"flowchart", "graph", "statediagram"})
    has_failures = any(
        vr.render == "fail"
        or vr.geometry == "fail"
        or (vr.geometry == "unvalidated" and dtype in _geom_validated_types)
        or vr.renderer_backend.endswith("-stub")
        or bool(vr.errors)
        for dtype, items in type_results.items()
        for _, _, vr, _, _, _, _ in items
    )

    # Atomically replace destination with tmp_dir.
    import shutil
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.move(str(tmp_dir), str(dest_dir))

    return dest_dir / "index.html", has_failures


def main() -> None:
    ap = argparse.ArgumentParser(description="Build side-by-side mermaid_render vs mmdc gallery")
    ap.add_argument("files", nargs="*", help=".mmd files to include (default: all tests/fixtures/*.mmd)")
    ap.add_argument("--open", action="store_true", help="Open result in browser")
    ap.add_argument("--type", dest="diagram_type", metavar="TYPE",
                    help="Only include diagrams of this type prefix (e.g. flowchart, sequence, c4)")
    ap.add_argument("--output-dir", dest="output_dir", metavar="PATH", default=None,
                    help="Write gallery files to this directory (default: ppt-output/compare/)")
    ap.add_argument("--metadata-only", action="store_true",
                    help="Write only metadata.json to --output-dir; skip gallery HTML")
    ap.add_argument("--width-hint", dest="width_hint", type=int, default=0,
                    help="Renderer width hint in px (default: 0 = auto); does not alter gallery CSS")
    args = ap.parse_args()

    out_dir = Path(args.output_dir).resolve() if args.output_dir else OUT_DIR

    if args.files:
        mmd_files = [Path(f).resolve() for f in args.files]
    else:
        mmd_files = sorted(FIXTURES_DIR.glob("*.mmd"))

    if args.diagram_type:
        mmd_files = [f for f in mmd_files if _diagram_type(f.stem) == args.diagram_type]
        if not mmd_files:
            print(f"No .mmd files found for type '{args.diagram_type}'.", file=sys.stderr)
            sys.exit(1)

    if not mmd_files:
        print("No .mmd files found.", file=sys.stderr)
        sys.exit(1)

    # Assert module provenance before generating any output.
    _assert_module_provenance(ROOT)

    # Always write metadata.json first so provenance is recorded even on failures.
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = _collect_metadata(mmd_files, out_dir, args.width_hint, sys.argv[1:])
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Metadata: {out_dir}/metadata.json")

    if args.metadata_only:
        return

    print(f"Building comparison gallery for {len(mmd_files)} diagram(s)...")
    index_path, has_failures = _build_gallery(mmd_files, out_dir, width_hint=args.width_hint)
    print(f"Gallery: file://{index_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{index_path}")

    if has_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

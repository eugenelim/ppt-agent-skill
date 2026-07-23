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
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"
OUT_DIR = ROOT / "ppt-output" / "compare"

sys.path.insert(0, str(ROOT / "scripts"))
import mermaid_render

# Best-effort import for ELK fallback detection during gallery runs.
try:
    from mermaid_render.layout import elk_adapter as _elk_mod
    _ElkUnavailable = _elk_mod.ElkUnavailable
except Exception:  # noqa: BLE001
    _elk_mod = None  # type: ignore[assignment]
    _ElkUnavailable = None  # type: ignore[assignment]

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

    # Node.js version (best-effort)
    node_version = None
    try:
        node_version = subprocess.run(
            ["node", "--version"], capture_output=True, text=True
        ).stdout.strip() or None
    except Exception:  # noqa: BLE001
        pass

    # elkjs version from node_modules package.json (best-effort)
    elkjs_version = None
    try:
        _elkjs_pkg = (
            ROOT / "scripts" / "mermaid_render" / "layout"
            / "node_modules" / "elkjs" / "package.json"
        )
        if _elkjs_pkg.exists():
            elkjs_version = json.loads(_elkjs_pkg.read_text(encoding="utf-8")).get("version")
    except Exception:  # noqa: BLE001
        pass

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

    # SHA256 of key renderer source files (stored in modules dict keyed by filename)
    _layout_dir = ROOT / "scripts" / "mermaid_render" / "layout"
    _tracked_modules = ["_strategies.py", "_text.py", "_geometry.py"]
    modules: dict = {}
    for _mod_name in _tracked_modules:
        _mod_file = _layout_dir / _mod_name
        _mod_sha = hashlib.sha256(_mod_file.read_bytes()).hexdigest() if _mod_file.exists() else None
        modules[_mod_name] = {"sha256": _mod_sha, "path": str(_mod_file)}
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
        "node_version": node_version,
        "elkjs_version": elkjs_version,
        "mmdc_version": mmdc_ver,
        "platform": platform.platform(),
        "renderer_width_hint": width_hint,
        "renderer_schema_version": _RENDERER_SCHEMA_VERSION,
        "mermaid_render_module_path": module_path,
        "modules": modules,
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
    border: none;
    display: block;
    margin: 0 auto;
    max-width: 100%;
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
    overflow: hidden;
    background: #fff;
    min-height: 120px;
    padding: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.render-frame {
    border: none;
    display: block;
    margin: 0 auto;
    max-width: 100%;
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


def _svg_is_valid(path: Path) -> bool:
    """True if path is a non-empty, well-formed SVG document."""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return False
        root = ET.parse(path).getroot()
        return root.tag.split("}")[-1] == "svg"
    except Exception:
        return False


def _terminate_group(proc: "subprocess.Popen") -> None:
    """Kill the process's whole group so mmdc's chromium children don't orphan."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass


def _run_mmdc(src: str, out_svg: Path, deadline_s: float = 60.0) -> tuple[bool, str]:
    """Run mmdc and return (success, note).

    Under some Node/puppeteer versions mermaid-cli renders the SVG correctly
    but then hangs (or exits non-zero) while shutting down the headless
    browser. Treat a non-empty, well-formed SVG as success regardless of exit
    status: poll for the file, and as soon as it is valid, kill mmdc's whole
    process group and move on (this also prevents orphaned chromium pileup that
    otherwise starves later renders).
    """
    with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False) as f:
        f.write(src)
        tmp = Path(f.name)
    if out_svg.exists():
        out_svg.unlink()

    proc = subprocess.Popen(
        ["mmdc", "-i", str(tmp), "-o", str(out_svg), "--quiet"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )
    note = ""
    deadline = time.monotonic() + deadline_s
    try:
        while True:
            if proc.poll() is not None:
                _, err = proc.communicate()
                note = (err or "").strip()
                break
            if _svg_is_valid(out_svg):
                _terminate_group(proc)
                note = "rendered; mmdc did not exit cleanly (killed after render)"
                break
            if time.monotonic() > deadline:
                _terminate_group(proc)
                note = f"mmdc timed out after {deadline_s:.0f}s"
                break
            time.sleep(0.25)
    finally:
        tmp.unlink(missing_ok=True)
        _terminate_group(proc)

    if _svg_is_valid(out_svg):
        return True, note
    return False, note or "mmdc produced no valid SVG"


def _render_ours(src: str, width_hint: int = 0) -> tuple[str | None, str]:
    """Return (full_html, error_msg). full_html is None on error."""
    try:
        return mermaid_render.to_html(src, width_hint=width_hint), ""
    except Exception as e:
        return None, str(e)


def _render_fidelity(src: str, width_hint: int = 0) -> tuple[str | None, str]:
    """Return (full_html, error_msg) rendered with faithful=True and neutral theme."""
    try:
        return mermaid_render.to_html(src, faithful=True, theme="neutral", width_hint=width_hint), ""
    except Exception as e:
        return None, str(e)


def _html_svg_dims(html: str) -> "tuple[str | None, str | None, str | None]":
    """Extract (viewBox, width, height) from the first <svg> tag in an HTML string."""
    import re  # noqa: PLC0415
    m = re.search(r"<svg\b([^>]*)>", html, re.IGNORECASE)
    if not m:
        return None, None, None
    attrs = m.group(1)
    vb = re.search(r'\bviewBox="([^"]*)"', attrs)
    w = re.search(r'\bwidth="([^"]*)"', attrs)
    h = re.search(r'\bheight="([^"]*)"', attrs)
    return (
        vb.group(1) if vb else None,
        w.group(1) if w else None,
        h.group(1) if h else None,
    )


def _validate_outputs(
    fixture_results: "list[dict]",
    out_dir: Path,
    target_names: "list[str] | None" = None,
) -> "list[str]":
    """Return a list of failure strings; empty means no hard failures.

    Checks (Task 4):
    1. Each expected mmdc SVG exists in out_dir/mmdc/.
    2. Each per-fixture provenance dict has a non-empty actual_layout_backend.
    3. python-fallback records must have a non-empty fallback_reason.
    4. fixture_sha256 values must match the file on disk (if provided).
    """
    failures: list[str] = []
    for rec in fixture_results:
        name = rec.get("name", rec.get("path", "?"))
        # Guard 1: mmdc SVG must exist when mmdc was expected to have produced one.
        if rec.get("mmdc_ok") and target_names is not None and name in target_names:
            svg_path = out_dir / "mmdc" / f"{name}.svg"
            if not svg_path.exists():
                failures.append(f"{name}: mmdc SVG missing from {svg_path}")
        # Guard 2: actual_layout_backend must be non-empty
        backend = rec.get("actual_layout_backend", "")
        if not backend:
            failures.append(f"{name}: actual_layout_backend is empty or absent")
        # Guard 3: python-fallback must have a reason
        if backend == "python-fallback":
            reason = rec.get("fallback_reason")
            if not reason:
                failures.append(f"{name}: python-fallback recorded without fallback_reason")
        # Guard 4: fixture sha256 on disk must match provenance (if path recorded)
        disk_path_str = rec.get("path")
        prov_sha = rec.get("fixture_sha256")
        if disk_path_str and prov_sha:
            disk_path = ROOT / disk_path_str if not Path(disk_path_str).is_absolute() else Path(disk_path_str)
            if disk_path.exists():
                import hashlib  # noqa: PLC0415
                actual_sha = hashlib.sha256(disk_path.read_bytes()).hexdigest()
                if actual_sha != prov_sha:
                    failures.append(
                        f"{name}: fixture SHA-256 mismatch "
                        f"(provenance={prov_sha[:8]}… disk={actual_sha[:8]}…)"
                    )
    return failures


def _resolve_svg_references(svg_str: str) -> str:
    """Post-process an SVG string to remove external relative references.

    Replaces relative <image href="..."> with a data-URI so the SVG is
    self-contained. Returns the (possibly unchanged) SVG string.
    """
    import re  # noqa: PLC0415
    # Replace relative href values in <image> tags with empty data URIs.
    # External absolute URLs (http/https) and data: URIs are left untouched.
    def _replace_image_href(m: "re.Match[str]") -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://", "data:", "#")):
            return m.group(0)
        # Replace with a transparent 1×1 PNG data URI.
        return m.group(0).replace(href, "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    svg_str = re.sub(r'<image[^>]+\bhref="([^"]*)"', _replace_image_href, svg_str)
    svg_str = re.sub(r'<image[^>]+\bxlink:href="([^"]*)"', _replace_image_href, svg_str)
    return svg_str


def _compare_mmdc_semantic(src: str, mmdc_svg_path: Path) -> str:
    """Compare mmdc SVG semantic elements against our SequenceGeometry.

    Returns "pass", "warning", or "unvalidated".
    - "pass": participant and message counts match
    - "warning": counts differ (soft mismatch)
    - "unvalidated": not a sequence diagram, or mmdc SVG unparseable
    """
    from mermaid_render.layout._parser import _detect_directive, _strip_frontmatter  # noqa: PLC0415
    from mermaid_render.layout._strategies import compile_sequence  # noqa: PLC0415

    clean = _strip_frontmatter(src)
    directive, _ = _detect_directive(clean)
    if directive.lower() != "sequencediagram":
        return "unvalidated"

    try:
        tree = ET.parse(mmdc_svg_path)
        root = tree.getroot()
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        ns_prefix = f"{{{ns}}}" if ns else ""

        def _count_data_et(et_val: str) -> int:
            return sum(
                1 for el in root.iter()
                if el.get("data-et") == et_val
            )

        mmdc_participants = _count_data_et("participant")
        mmdc_messages = _count_data_et("message")
    except Exception:
        return "unvalidated"

    try:
        compiled = compile_sequence(clean)
        geom = compiled.geometry
        our_participants = len(geom.participants)
        our_messages = len(geom.messages)
    except Exception:
        return "unvalidated"

    if mmdc_participants == our_participants and mmdc_messages == our_messages:
        return "pass"
    return "warning"


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


def _atomic_write_gallery(out_dir: Path, *, raise_mid_write: bool = False) -> None:
    """Atomically stage a gallery into out_dir via a temp directory.

    Creates a sibling temp dir, then renames it over out_dir only after all
    writes succeed — so a failure mid-write leaves the existing out_dir intact.

    raise_mid_write: test-only flag; raises RuntimeError before the swap to
    verify the atomicity guarantee without touching out_dir.
    """
    import shutil
    tmp = Path(tempfile.mkdtemp(dir=out_dir.parent, prefix="gallery_atomic_"))
    try:
        if raise_mid_write:
            raise RuntimeError("simulated mid-write failure (test-only)")
        if out_dir.exists():
            shutil.rmtree(out_dir)
        os.rename(str(tmp), str(out_dir))
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def _build_gallery(
    mmd_files: list[Path],
    out_dir: Path,
    width_hint: int = 0,
    strict: bool = False,
    allow_dirty: bool = False,
    mode: str = "both",
) -> "tuple[Path, bool, list[dict]]":
    import shutil

    # Dirty-tree guard (Task 3): fail fast before creating any output.
    if not allow_dirty:
        dirty_out = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True, cwd=ROOT
        ).stdout.strip()
        if dirty_out:
            error_record = {
                "error": "dirty-tree",
                "git_status": dirty_out,
                "message": "Working tree is dirty — pass allow_dirty=True or --allow-dirty to override",
            }
            return out_dir / "index.html", True, [error_record]

    # Build into a temp directory; atomically replace dest at the end.
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(dir=out_dir.parent, prefix="gallery_tmp_"))
    try:
        return _build_gallery_into(mmd_files, tmp_dir, out_dir, width_hint, strict=strict, mode=mode)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def _build_gallery_into(
    mmd_files: list[Path],
    tmp_dir: Path,
    dest_dir: Path,
    width_hint: int,
    strict: bool = False,
    mode: str = "both",
) -> "tuple[Path, bool, list[dict]]":
    import hashlib  # noqa: PLC0415
    import shutil
    from collections import defaultdict
    from mermaid_render.layout._geometry import ValidationResult

    (tmp_dir / "ours").mkdir(exist_ok=True)
    (tmp_dir / "mmdc").mkdir(exist_ok=True)

    # Collect git SHA for HTML header (best-effort).
    _git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip() or "unknown"

    # Tuple: (name, src, vr, ours_err, mmdc_svg_path_in_tmp, mmdc_ok, mmdc_err, prov_dict)
    # vr: ValidationResult with four-status lanes.
    # ours_html is NOT held in memory — written to disk, re-read per section.
    type_results: dict[str, list[tuple]] = defaultdict(list)
    # Per-fixture provenance records.
    fixture_results: list[dict] = []

    sorted_files = sorted(mmd_files)
    n_total = len(sorted_files)
    run_timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    for i, mmd_path in enumerate(sorted_files):
        name = mmd_path.stem
        src = mmd_path.read_text(encoding="utf-8").strip()
        src_sha256 = hashlib.sha256(mmd_path.read_bytes()).hexdigest()
        mmd_rel = str(mmd_path.relative_to(ROOT)) if mmd_path.is_relative_to(ROOT) else str(mmd_path)
        print(f"  [{i + 1}/{n_total}] {name} ...", end=" ", flush=True)

        # ELK tracking: temporarily wrap layout_with_elk to detect fallback.
        elk_state: dict = {"called": False, "ok": True, "reason": None}
        if _elk_mod is not None:
            _orig_elk = _elk_mod.layout_with_elk

            def _track_elk(graph: object, spacing: object = None) -> object:
                elk_state["called"] = True
                try:
                    return _orig_elk(graph, spacing=spacing)  # type: ignore[arg-type]
                except _elk_mod.ElkUnavailable as exc:  # type: ignore[union-attr]
                    elk_state["ok"] = False
                    elk_state["reason"] = str(exc)
                    raise

            _elk_mod.layout_with_elk = _track_elk  # type: ignore[assignment]

        # When mode is "fidelity", use _render_fidelity as the primary render.
        # When mode is "editorial" or "both", use _render_ours for the editorial pane.
        _primary_is_fidelity = mode == "fidelity"

        try:
            if _primary_is_fidelity:
                # Fidelity-only: skip editorial render.
                ours_html, ours_err = None, ""
            else:
                ours_html, ours_err = _render_ours(src, width_hint=width_hint)
        finally:
            if _elk_mod is not None:
                _elk_mod.layout_with_elk = _orig_elk  # type: ignore[assignment]

        if ours_html:
            (tmp_dir / "ours" / f"{name}.html").write_text(ours_html, encoding="utf-8")
            vr = mermaid_render.validate(src)
        else:
            vr = ValidationResult(render="fail", syntax_coverage="fail")

        # Determine actual layout backend from ELK tracking.
        if elk_state["called"]:
            actual_layout_backend = "elk" if elk_state["ok"] else "python-fallback"
            fallback_reason: str | None = elk_state["reason"] if not elk_state["ok"] else None
        else:
            actual_layout_backend = vr.renderer_backend or "native"
            fallback_reason = None

        # Extract SVG dimensions from rendered HTML.
        output_viewbox, output_width, output_height = (
            _html_svg_dims(ours_html) if ours_html else (None, None, None)
        )

        # Fidelity lane (mode "fidelity" or "both").
        fidelity_html: str | None = None
        fidelity_err = ""
        fidelity_faithful = False
        if mode in ("fidelity", "both"):
            fidelity_html, fidelity_err = _render_fidelity(src, width_hint=width_hint)
            fidelity_faithful = True
            if fidelity_html:
                (tmp_dir / "ours" / f"{name}_fidelity.html").write_text(fidelity_html, encoding="utf-8")

        mmdc_svg_path = tmp_dir / "mmdc" / f"{name}.svg"
        mmdc_ok, mmdc_err = _run_mmdc(src, mmdc_svg_path)

        if mmdc_ok:
            from dataclasses import replace as _dc_replace  # noqa: PLC0415
            oracle = _compare_mmdc_semantic(src, mmdc_svg_path)
            vr = _dc_replace(vr, mmdc_oracle=oracle)
            # Post-process SVG to remove unresolved relative references.
            try:
                mmdc_svg_path.write_text(
                    _resolve_svg_references(mmdc_svg_path.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001
                pass

        print(
            f"render:{vr.render}  syntax:{vr.syntax_coverage}  "
            f"structural_geometry:{vr.structural_geometry}  "
            f"semantic_geometry:{vr.semantic_geometry}  "
            f"oracle:{vr.mmdc_oracle}  "
            f"mmdc:{'ok' if mmdc_ok else 'err'}  "
            f"backend:{actual_layout_backend}"
        )

        dtype = _diagram_type(name)
        # Provenance records the primary lane's parameters.
        _prov_faithful = _primary_is_fidelity
        _prov_theme = "neutral" if _primary_is_fidelity else None
        prov: dict = {
            "name": name,
            "path": mmd_rel,
            "fixture_sha256": src_sha256,
            "diagram_type": dtype,
            "renderer_backend": vr.renderer_backend,
            "actual_layout_backend": actual_layout_backend,
            "fallback_reason": fallback_reason,
            "renderer_api": "to_html",
            "faithful": _prov_faithful,
            "theme": _prov_theme,
            "width_hint": width_hint,
            "height_hint": 0,
            "output_width": output_width,
            "output_height": output_height,
            "output_viewbox": output_viewbox,
            "geometry": vr.geometry,
            "render": vr.render,
            "mmdc_ok": mmdc_ok,
            "timestamp_utc": run_timestamp,
        }
        # In "both" mode, also record fidelity lane parameters as a sub-record.
        if fidelity_faithful:
            prov["fidelity_lane"] = {
                "faithful": True,
                "theme": "neutral",
                "render": "pass" if fidelity_html else "fail",
            }
        type_results[dtype].append((name, src, vr, ours_err, mmdc_svg_path, mmdc_ok, mmdc_err, prov, fidelity_html, fidelity_err))
        fixture_results.append(prov)

    # Hard-fail validation pass (Task 4).
    target_names = [p.stem for p in sorted_files]
    validation_failures = _validate_outputs(fixture_results, tmp_dir, target_names)

    # Build nav — requires all results, so collected first.
    nav_parts: list[str] = []
    for dtype in sorted(type_results):
        items = type_results[dtype]
        n_render_ok = sum(1 for _, _, vr, *_ in items if vr.render == "pass")
        n_items = len(items)
        group_status = "ok" if n_render_ok == n_items else ("err" if n_render_ok == 0 else "warn")
        badge_cls = "badge-ok" if group_status == "ok" else ("badge-err" if group_status == "err" else "badge-warn")
        nav_parts.append(
            f'<div class="nav-group">'
            f'<span class="nav-type">{_html_mod.escape(dtype)}'
            f'<span class="status-badge {badge_cls}">{n_render_ok}/{n_items}</span></span>'
        )
        for name, _, vr, _, _, mmdc_ok, *_ in items:
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
    n_ours_ok = sum(1 for items in type_results.values() for _, _, vr, *_ in items if vr.render == "pass")
    n_mmdc_ok = sum(m for items in type_results.values() for _, _, _, _, _, m, *_ in items)
    n_syntax_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, *_ in items if vr.syntax_coverage == "pass"
    )
    n_geom_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, *_ in items if vr.geometry == "pass"
    )
    n_geom_total = sum(
        1 for dtype, items in type_results.items()
        for _, _, vr, *_ in items
        if vr.geometry != "unvalidated"
    )
    n_oracle_ok = sum(
        1 for items in type_results.values()
        for _, _, vr, *_ in items if vr.mmdc_oracle == "pass"
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
  <style>{_PAGE_CSS}
.mmdc-inline-svg svg {{ max-width: 100%; height: auto; display: block; margin: 0 auto; }}
  </style>
</head>
<body>
  <header>
    <h1>mermaid_render vs mmdc comparison</h1>
    <span>{total_diags} diagrams &nbsp;·&nbsp; {n_types} types &nbsp;·&nbsp;
      render {n_ours_ok}/{total_diags} &nbsp;·&nbsp;
      syntax {n_syntax_ok}/{total_diags} &nbsp;·&nbsp;
      geometry {n_geom_ok}/{n_geom_total} &nbsp;·&nbsp;
      oracle {n_oracle_ok}/{total_diags} &nbsp;·&nbsp;
      mmdc {n_mmdc_ok}/{total_diags} &nbsp;·&nbsp;
      sha: {_html_mod.escape(_git_sha)}</span>
  </header>
  <nav>{nav_html}</nav>
""")

        for dtype in sorted(type_results):
            items = type_results[dtype]
            f.write(f'  <div class="type-group-header" id="type-{dtype}">{_html_mod.escape(dtype)}</div>\n')
            for name, src, vr, ours_err, mmdc_svg_path, mmdc_ok, mmdc_err, prov, fidelity_html, fidelity_err in items:
                mmdc_status = "ok" if mmdc_ok else "err"

                if vr.render == "pass":
                    ours_html_str = (tmp_dir / "ours" / f"{name}.html").read_text(encoding="utf-8")
                    ours_srcdoc = _html_mod.escape(ours_html_str, quote=True)
                    ours_content = (
                        '<div class="render-box">'
                        f'<iframe class="render-frame" srcdoc="{ours_srcdoc}"></iframe>'
                        '</div>'
                    )
                else:
                    ours_content = f'<div class="error-box">{_html_mod.escape(ours_err)}</div>'

                # mmdc pane: inline SVG directly (Task 6).
                if mmdc_ok and mmdc_svg_path.exists():
                    try:
                        mmdc_svg_str = mmdc_svg_path.read_text(encoding="utf-8")
                        mmdc_content = (
                            '<div class="render-box">'
                            f'<div class="mmdc-inline-svg">{mmdc_svg_str}</div>'
                            '</div>'
                        )
                    except Exception:  # noqa: BLE001
                        mmdc_content = (
                            '<div class="error-box">mmdc SVG read error</div>'
                        )
                else:
                    mmdc_content = (
                        '<div class="error-box">'
                        f'{_html_mod.escape(mmdc_err or "mmdc failed (no output)")}'
                        '</div>'
                    )

                # Fidelity pane (shown when mode includes fidelity).
                fidelity_section = ""
                if fidelity_html is not None:
                    fidelity_srcdoc = _html_mod.escape(fidelity_html, quote=True)
                    fidelity_section = f"""
  <div class="pane-fidelity" style="margin-top:12px;">
    <div class="pane-header" style="background:#f0e8f8;color:#6b2e8f;">Fidelity lane (faithful=True, neutral)</div>
    <div class="render-box">
      <iframe class="render-frame" srcdoc="{fidelity_srcdoc}"></iframe>
    </div>
  </div>"""
                elif fidelity_err:
                    fidelity_section = f"""
  <div class="pane-fidelity" style="margin-top:12px;">
    <div class="pane-header" style="background:#f0e8f8;color:#6b2e8f;">Fidelity lane (error)</div>
    <div class="error-box">{_html_mod.escape(fidelity_err)}</div>
  </div>"""

                # Provenance details block (Task 7).
                prov_json = json.dumps(prov, indent=2)
                prov_section = (
                    f'<details><summary>provenance</summary>'
                    f'<pre>{_html_mod.escape(prov_json)}</pre></details>'
                )

                f.write(f"""
<div class="diagram-section" id="{name}">
  <h2>{_html_mod.escape(name)}</h2>
  <div class="status-lanes">
    <span class="status-badge {_lane_badge_cls(vr.render)} badge-render">render: {vr.render}</span>
    <span class="status-badge {_lane_badge_cls(vr.syntax_coverage)} badge-syntax">syntax: {vr.syntax_coverage}</span>
    <span class="status-badge {_lane_badge_cls(vr.structural_geometry)} badge-structural-geometry">structural_geometry: {vr.structural_geometry}</span>
    <span class="status-badge {_lane_badge_cls(vr.semantic_geometry)} badge-semantic-geometry">semantic_geometry: {vr.semantic_geometry}</span>
    <span class="status-badge {_lane_badge_cls(vr.mmdc_oracle)} badge-oracle">mmdc_oracle: {vr.mmdc_oracle}</span>
    <span class="status-badge badge-{"ok" if mmdc_ok else "err"}">mmdc: {mmdc_status}</span>
    <span class="status-badge badge-unvalidated">backend: {_html_mod.escape(prov.get("actual_layout_backend", ""))}</span>
  </div>
  <div class="comparison-grid">
    <div class="pane-ours">
      <div class="pane-header">Our renderer (editorial)</div>
      {ours_content}
    </div>
    <div class="pane-mmdc">
      <div class="pane-header">mmdc 11.15.0</div>
      {mmdc_content}
    </div>
  </div>{fidelity_section}
  <details>
    <summary>Mermaid source</summary>
    <pre>{_html_mod.escape(src)}</pre>
  </details>
  {prov_section}
</div>
""")

        f.write("""  <script>
    const MAX_H = 600;
    function boxInnerWidth(el) {
      const cs = getComputedStyle(el);
      return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    }
    function fitOursFrame(frame) {
      const doc = frame.contentDocument;
      if (!doc) return;
      const stage = doc.querySelector(".diagram");
      if (!stage) return;
      doc.body.style.margin = "0";
      doc.body.style.padding = "0";
      doc.body.style.overflow = "hidden";
      stage.style.zoom = "1";
      const iw = stage.offsetWidth, ih = stage.offsetHeight;
      if (!iw || !ih) return;
      const scale = Math.min(boxInnerWidth(frame) / iw, MAX_H / ih);
      stage.style.zoom = String(scale);
      frame.style.width = `${Math.ceil(iw * scale)}px`;
      frame.style.height = `${Math.ceil(ih * scale)}px`;
    }
    function attachFrameObservers() {
      document.querySelectorAll("iframe.render-frame").forEach(frame => {
        frame.addEventListener("load", () => fitOursFrame(frame));
        new ResizeObserver(() => fitOursFrame(frame)).observe(frame.parentElement);
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
        for _, _, vr, *_ in items
    )

    # Hard-fail guard: validation failures (Task 4).
    if validation_failures:
        has_failures = True

    if strict:
        has_failures = has_failures or any(
            vr.structural_geometry == "fail"
            or vr.semantic_geometry == "fail"
            or any(
                getattr(d, "severity", None) == "error"
                for d in vr.diagnostics
            )
            for items in type_results.values()
            for _, _, vr, *_ in items
        )

    # Atomically replace destination with tmp_dir.
    import shutil
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    os.rename(str(tmp_dir), str(dest_dir))

    return dest_dir / "index.html", has_failures, fixture_results


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
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any fixture has render/structural_geometry fail or error-severity diagnostic")
    ap.add_argument("--allow-dirty", dest="allow_dirty", action="store_true",
                    help="Allow generation from a dirty working tree (skips dirty-tree guard)")
    ap.add_argument("--mode", choices=["editorial", "fidelity", "both"], default="both",
                    help="Rendering mode: editorial (default styling), fidelity (faithful=True, neutral theme), or both")
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
    meta_path = out_dir / "metadata.json"

    if args.metadata_only:
        # Provenance check: compare stored module SHAs vs freshly computed SHAs.
        if meta_path.exists():
            stored = json.loads(meta_path.read_text(encoding="utf-8"))
            stored_modules = stored.get("modules", {})
            fresh_modules = metadata.get("modules", {})
            mismatch_found = False
            for mod_name, fresh_entry in fresh_modules.items():
                stored_entry = stored_modules.get(mod_name, {})
                if stored_entry.get("sha256") != fresh_entry.get("sha256"):
                    print(
                        f"ERROR: module SHA256 mismatch for {mod_name}: "
                        f"stored={stored_entry.get('sha256')!r} "
                        f"computed={fresh_entry.get('sha256')!r}",
                        file=sys.stderr,
                    )
                    mismatch_found = True
            if mismatch_found:
                sys.exit(1)
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"Metadata: {meta_path}")
        return

    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out_dir / "metadata.json.bak").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Metadata: {meta_path}")

    print(f"Building comparison gallery for {len(mmd_files)} diagram(s)...")
    index_path, has_failures, fixture_results = _build_gallery(
        mmd_files, out_dir,
        width_hint=args.width_hint,
        strict=args.strict,
        allow_dirty=args.allow_dirty,
        mode=args.mode,
    )
    # Add per-fixture provenance to metadata (Task D).
    metadata["fixture_results"] = fixture_results
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Gallery: file://{index_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{index_path}")

    if has_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

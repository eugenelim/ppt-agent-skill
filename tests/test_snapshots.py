"""Snapshot regression tests for the mermaid renderer.

Renders each fixture in tests/fixtures/*.mmd to PNG via scripts/html2png.py
(puppeteer) and compares against a committed baseline in tests/snapshots/.

Run modes:
  pytest tests/test_snapshots.py                  # regression (compare)
  pytest tests/test_snapshots.py --snapshot-capture  # re-capture baselines

The entire module is skipped when `node` is not on PATH (CI or developer
machines without puppeteer) or when SNAPSHOT_BASELINE_PLATFORM is set and
does not match sys.platform (prevents cross-platform false-failures).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_LIGHT_DIR = REPO_ROOT / "tests" / "snapshots" / "light"
SNAPSHOTS_DARK_DIR = REPO_ROOT / "tests" / "snapshots" / "dark"
HTML2PNG = REPO_ROOT / "scripts" / "html2png.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Skip the entire module when node is unavailable.
if shutil.which("node") is None:
    pytest.skip("node not found — snapshot tests require puppeteer", allow_module_level=True)

# Skip when the baseline was captured on a different platform.
_baseline_platform = os.environ.get("SNAPSHOT_BASELINE_PLATFORM", "")
if _baseline_platform and _baseline_platform != sys.platform:
    pytest.skip(
        f"baseline captured on {_baseline_platform}, running on {sys.platform}",
        allow_module_level=True,
    )

_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))


_PPT_OUT = REPO_ROOT / "ppt-output"


def _render_to_png(mmd_path: Path, tmp_dir: Path, theme: str) -> Path:
    from mermaid_layout import _dispatch, make_page

    src = mmd_path.read_text()
    html = make_page(_dispatch(src, None, 800), theme=theme)
    # Place the HTML inside ppt-output so html2png.py's get_dep_dir() resolves
    # node_modules relative to the project's ppt-output (not a random tmp path).
    _PPT_OUT.mkdir(exist_ok=True)
    html_path = _PPT_OUT / (mmd_path.stem + f"-{theme}.html")
    html_path.write_text(html, encoding="utf-8")
    try:
        png_dir = tmp_dir / "png"
        png_dir.mkdir(exist_ok=True)
        subprocess.run(
            [sys.executable, str(HTML2PNG), str(html_path), "-o", str(png_dir),
             "--scale", "1", "--fullpage"],
            check=True,
            capture_output=True,
        )
    finally:
        html_path.unlink(missing_ok=True)
    return png_dir / (mmd_path.stem + f"-{theme}.png")


def _compare_or_capture(rendered: Path, baseline: Path, stem: str, capture: bool) -> None:
    if capture:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        import shutil as _sh
        _sh.copy2(rendered, baseline)
        return

    if not baseline.exists():
        pytest.skip(f"no baseline for {stem} — run with --snapshot-capture first")

    from PIL import Image, ImageChops
    import numpy as np
    img_new = Image.open(rendered).convert("RGB")
    img_base = Image.open(baseline).convert("RGB")
    if img_new.size != img_base.size:
        img_new = img_new.resize(img_base.size, Image.LANCZOS)
    diff = ImageChops.difference(img_new, img_base)
    arr = np.array(diff)
    nonzero = int((arr > 0).any(axis=-1).sum())
    total = img_base.width * img_base.height
    pct = nonzero / total
    assert pct <= 0.005, (
        f"{stem}: {pct:.1%} pixels differ (threshold 0.5%)"
    )


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_snapshot_light(fixture: Path, request):
    capture = request.config.getoption("--snapshot-capture")
    baseline = SNAPSHOTS_LIGHT_DIR / (fixture.stem + ".png")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rendered = _render_to_png(fixture, tmp_path, "light")
        _compare_or_capture(rendered, baseline, fixture.stem + " [light]", capture)


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_snapshot_dark(fixture: Path, request):
    capture = request.config.getoption("--snapshot-capture")
    baseline = SNAPSHOTS_DARK_DIR / (fixture.stem + ".png")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rendered = _render_to_png(fixture, tmp_path, "dark")
        _compare_or_capture(rendered, baseline, fixture.stem + " [dark]", capture)

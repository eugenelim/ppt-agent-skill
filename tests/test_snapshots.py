"""Snapshot regression tests for the mermaid renderer.

Renders each fixture in tests/fixtures/*.mmd to PNG via Playwright/Chromium
and compares against a committed baseline in tests/snapshots/.

One BrowserSession handles all renders for the entire pytest session.
Each (fixture, theme) pair is rendered exactly once and reused by both
the smoke and fidelity comparison lanes.

Two comparison lanes share the same baseline PNGs:

  SMOKE   (test_snapshot_light / test_snapshot_dark)
    Resizes new render to baseline dimensions before diffing.  Catches gross
    content regressions regardless of incidental size changes.  Threshold 0.5%.

  FIDELITY (test_fidelity_light / test_fidelity_dark)
    No resize.  Asserts four metrics independently:
      1. canvas width / height — exact match required
      2. content bounding box  — within ±16 px tolerance
      3. pixel diff at original dimensions — threshold 0.5%
    A canvas-size change is reported as its own failure, not silently absorbed
    into a resized pixel diff.

Run modes:
  pytest -m snapshot tests/test_snapshots.py                  # both lanes, compare
  pytest -m snapshot tests/test_snapshots.py --snapshot-capture  # re-capture baselines

Browser tier:
  All tests carry @pytest.mark.browser + @pytest.mark.snapshot.
  Do NOT combine with -n/xdist — the session-scoped browser fixture is not
  xdist-safe.

The entire module is skipped when playwright is not importable or when
SNAPSHOT_BASELINE_PLATFORM is set and does not match sys.platform.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_LIGHT_DIR = REPO_ROOT / "tests" / "snapshots" / "light"
SNAPSHOTS_DARK_DIR = REPO_ROOT / "tests" / "snapshots" / "dark"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Skip the entire module when Playwright+Chromium is unavailable.
try:
    from playwright.sync_api import sync_playwright as _sp  # noqa: F401
    _playwright_importable = True
except ImportError:
    _playwright_importable = False

if not _playwright_importable:
    pytest.skip("playwright not installed — snapshot tests require playwright + chromium", allow_module_level=True)

# Skip when the baseline was captured on a different platform.
_baseline_platform = os.environ.get("SNAPSHOT_BASELINE_PLATFORM", "")
if _baseline_platform and _baseline_platform != sys.platform:
    pytest.skip(
        f"baseline captured on {_baseline_platform}, running on {sys.platform}",
        allow_module_level=True,
    )

_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))
_PPT_OUT = REPO_ROOT / "ppt-output"


# ── session-scoped lazy renderer ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def _png_cache(tmp_path_factory):
    """One BrowserSession for the whole pytest session; lazy per-(fixture, theme) render.

    Returns a callable ``get_png(fixture_path, theme) -> Path | None``.
    ``None`` means the fixture type is unsupported by the native renderer.

    Each (fixture, theme) pair is rendered at most once; subsequent calls for
    the same key return the cached path.  This means smoke and fidelity lanes
    share the same PNG — no duplicate renders.

    The cross-process flock (browser_budget) is held for the entire session so
    that concurrent pytest invocations do not start competing browser sessions.
    """
    from mermaid_layout import _dispatch, make_page
    from mermaid_render.browser import BrowserSession
    from mermaid_render.browser_lock import browser_budget

    cache_dir = tmp_path_factory.mktemp("snapshot_pngs", numbered=False)
    _cache: dict[tuple[str, str], "Path | None"] = {}
    _PPT_OUT.mkdir(exist_ok=True)

    with browser_budget():
        with BrowserSession() as session:

            def _get_png(fixture_path: Path, theme: str) -> "Path | None":
                key = (fixture_path.stem, theme)
                if key in _cache:
                    return _cache[key]

                src = fixture_path.read_text()
                try:
                    fragment = _dispatch(src, None, 800)
                except ValueError:
                    _cache[key] = None
                    return None

                html = make_page(fragment, theme=theme)
                html_path = _PPT_OUT / f"{fixture_path.stem}-{theme}-snap.html"
                png_path = cache_dir / f"{fixture_path.stem}-{theme}.png"

                html_path.write_text(html, encoding="utf-8")
                try:
                    png_bytes = session.render_to_png(html_path, scale=1.0, fullpage=True)
                    png_path.write_bytes(png_bytes)
                    _cache[key] = png_path
                finally:
                    html_path.unlink(missing_ok=True)

                return _cache[key]

            yield _get_png


# ── comparison helpers ────────────────────────────────────────────────────────

def _measure_canvas(img: "Image.Image") -> dict:
    """Return canvas dimensions and the content bounding box.

    content_bbox is (x0, y0, x1, y1) of the smallest rectangle enclosing all
    pixels that differ from the top-left background pixel, or None if the image
    is entirely background.
    """
    import numpy as np
    arr = np.array(img.convert("RGB"))
    w, h = img.size
    bg   = arr[0, 0]
    mask = ~(arr == bg).all(axis=-1)
    if mask.any():
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        content_bbox = (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)
    else:
        content_bbox = None
    return {"width": w, "height": h, "content_bbox": content_bbox}


def _compare_or_capture(rendered: Path, baseline: Path, stem: str, capture: bool) -> None:
    """Smoke lane: resize-tolerant pixel diff.  Re-captures when --snapshot-capture."""
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


def _fidelity_compare(rendered: Path, baseline: Path, stem: str) -> None:
    """Fidelity lane: four separate metrics at original dimensions (no resize).

    Reports canvas size, content bounds, and pixel diff as distinct failures so
    that a size regression doesn't hide behind a resized diff passing at 0 %.
    """
    if not baseline.exists():
        pytest.skip(f"no baseline for {stem} — run with --snapshot-capture first")

    from PIL import Image, ImageChops
    import numpy as np

    img_new  = Image.open(rendered).convert("RGB")
    img_base = Image.open(baseline).convert("RGB")

    failures: list[str] = []

    m_new  = _measure_canvas(img_new)
    m_base = _measure_canvas(img_base)

    # 1. Canvas width
    if m_new["width"] != m_base["width"]:
        failures.append(
            f"canvas width:  was {m_base['width']}px, now {m_new['width']}px"
        )

    # 2. Canvas height
    if m_new["height"] != m_base["height"]:
        failures.append(
            f"canvas height: was {m_base['height']}px, now {m_new['height']}px"
        )

    # 3. Content bounds (±16 px tolerance per axis)
    if m_new["content_bbox"] and m_base["content_bbox"]:
        cw_new  = m_new["content_bbox"][2]  - m_new["content_bbox"][0]
        ch_new  = m_new["content_bbox"][3]  - m_new["content_bbox"][1]
        cw_base = m_base["content_bbox"][2] - m_base["content_bbox"][0]
        ch_base = m_base["content_bbox"][3] - m_base["content_bbox"][1]
        if abs(cw_new - cw_base) > 16 or abs(ch_new - ch_base) > 16:
            failures.append(
                f"content bounds: was {cw_base}×{ch_base}px, "
                f"now {cw_new}×{ch_new}px  (threshold ±16px)"
            )

    # 4. Pixel diff at original dimensions
    if img_new.size == img_base.size:
        diff    = ImageChops.difference(img_new, img_base)
        arr     = np.array(diff)
        nonzero = int((arr > 0).any(axis=-1).sum())
        total   = img_base.width * img_base.height
        pct     = nonzero / total
        if pct > 0.005:
            failures.append(
                f"pixel diff:    {pct:.1%} at original size (threshold 0.5%)"
            )
    else:
        failures.append(
            "pixel diff:    skipped — canvas size changed; fix canvas first"
        )

    assert not failures, (
        f"{stem} fidelity:\n" + "\n".join(f"  {f}" for f in failures)
    )


# ── smoke lane ────────────────────────────────────────────────────────────────

@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_snapshot_light(fixture: Path, request, _png_cache: Callable):
    capture = request.config.getoption("--snapshot-capture")
    baseline = SNAPSHOTS_LIGHT_DIR / (fixture.stem + ".png")
    rendered = _png_cache(fixture, "light")
    if rendered is None:
        pytest.skip(f"{fixture.stem}: unsupported diagram type")
    _compare_or_capture(rendered, baseline, fixture.stem + " [light]", capture)


@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_snapshot_dark(fixture: Path, request, _png_cache: Callable):
    capture = request.config.getoption("--snapshot-capture")
    baseline = SNAPSHOTS_DARK_DIR / (fixture.stem + ".png")
    rendered = _png_cache(fixture, "dark")
    if rendered is None:
        pytest.skip(f"{fixture.stem}: unsupported diagram type")
    _compare_or_capture(rendered, baseline, fixture.stem + " [dark]", capture)


# ── fidelity lane ─────────────────────────────────────────────────────────────
# Uses the same cached PNG as the smoke lane — no duplicate renders.

@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_fidelity_light(fixture: Path, _png_cache: Callable):
    """Fidelity lane (light theme): canvas size, content bounds, pixel diff at
    original dimensions. Reuses the same PNG as test_snapshot_light."""
    baseline = SNAPSHOTS_LIGHT_DIR / (fixture.stem + ".png")
    rendered = _png_cache(fixture, "light")
    if rendered is None:
        pytest.skip(f"{fixture.stem}: unsupported diagram type")
    _fidelity_compare(rendered, baseline, fixture.stem + " [light]")


@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_fidelity_dark(fixture: Path, _png_cache: Callable):
    """Fidelity lane (dark theme): canvas size, content bounds, pixel diff at
    original dimensions. Reuses the same PNG as test_snapshot_dark."""
    baseline = SNAPSHOTS_DARK_DIR / (fixture.stem + ".png")
    rendered = _png_cache(fixture, "dark")
    if rendered is None:
        pytest.skip(f"{fixture.stem}: unsupported diagram type")
    _fidelity_compare(rendered, baseline, fixture.stem + " [dark]")

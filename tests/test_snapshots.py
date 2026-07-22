"""Snapshot regression tests for the mermaid renderer.

Renders each fixture in tests/fixtures/*.mmd to PNG via Playwright/Chromium
and compares against a committed baseline in tests/snapshots/.

One SnapshotRasterSession handles all renders for the entire pytest session,
reusing a single BrowserContext and Page via page.set_content (no per-render
navigation overhead).

Each fixture is compiled via _dispatch exactly once regardless of theme.
make_page applies the theme CSS to the compiled fragment for light and dark.

Each (fixture, theme) pair is rendered at most once.  Subsequent calls for
the same key return the cached path.

In comparison mode, pairs without an existing baseline are skipped before
compilation or rendering (manifest pre-filter).

One fused test function test_snapshot_fused covers both resize-tolerant smoke
and original-dimension fidelity metrics.  Both rendered and baseline images
are opened at most once per (fixture, theme) pair; a SHA-256 fast path avoids
all image I/O for byte-identical results.

Run modes:
  pytest --run-snapshots tests/test_snapshots.py               # compare, all fixtures
  pytest --run-snapshots tests/test_snapshots.py --snapshot-capture  # re-capture baselines
  pytest --run-snapshots-quick tests/test_snapshots.py         # compare, representative set

Browser tier:
  All tests carry @pytest.mark.browser + @pytest.mark.snapshot.
  Do NOT combine with -n > 1 (xdist) — the session-scoped browser fixture is not
  xdist-safe.  The conftest xdist guard enforces this.

The entire module is skipped when playwright is not importable or when
SNAPSHOT_BASELINE_PLATFORM is set and does not match sys.platform.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_LIGHT_DIR = REPO_ROOT / "tests" / "snapshots" / "light"
SNAPSHOTS_DARK_DIR = REPO_ROOT / "tests" / "snapshots" / "dark"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Module-level pure helpers — importable without Playwright
# ---------------------------------------------------------------------------

def sha256_bytes_equal(b1: bytes, b2: bytes) -> bool:
    """Return True iff b1 and b2 are byte-identical (SHA-256 fast path).

    Importable from outside this module for testing without Playwright.
    """
    return hashlib.sha256(b1).digest() == hashlib.sha256(b2).digest()


def manifest_prefilter_applies(
    key: "tuple[str, str]",
    manifest: "frozenset[tuple[str, str]]",
    capture: bool,
) -> bool:
    """Return True iff this (stem, theme) pair should be skipped by the manifest pre-filter.

    A pair is skipped when we are in comparison mode (not capture) and the pair
    has no committed baseline in the manifest.
    Importable from outside this module for testing without Playwright.
    """
    return not capture and key not in manifest


# Skip the entire module when Playwright+Chromium is unavailable.
try:
    from playwright.sync_api import sync_playwright as _sp  # noqa: F401
    _playwright_importable = True
except ImportError:
    _playwright_importable = False

if not _playwright_importable:
    pytest.skip(
        "playwright not installed — snapshot tests require playwright + chromium",
        allow_module_level=True,
    )

# Skip when the baseline was captured on a different platform.
_baseline_platform = os.environ.get("SNAPSHOT_BASELINE_PLATFORM", "")
if _baseline_platform and _baseline_platform != sys.platform:
    pytest.skip(
        f"baseline captured on {_baseline_platform}, running on {sys.platform}",
        allow_module_level=True,
    )

_FIXTURES = sorted(FIXTURES_DIR.glob("*.mmd"))

# Representative subset: one fixture per diagram family (21 families).
# Used by --run-snapshots-quick to limit the PNG corpus for routine local runs.
_REPRESENTATIVE_STEMS: frozenset[str] = frozenset({
    "architecture-basic", "block-basic", "c4-basic",
    "class-basic", "er-basic", "flowchart-arrows-defs",
    "gantt-basic", "gitgraph-basic", "journey-basic",
    "kanban-basic", "mindmap-basic", "packet-basic",
    "pie-basic", "quadrant-basic", "requirement-basic",
    "sankey-basic", "sequence-basic", "statediagram-basic",
    "timeline-basic", "xychart-basic", "zenuml-basic",
})

# Precompute the baseline manifest at import time (before any rendering).
_BASELINE_MANIFEST: frozenset[tuple[str, str]] = frozenset(
    (p.stem, "light") for p in SNAPSHOTS_LIGHT_DIR.glob("*.png")
) | frozenset(
    (p.stem, "dark") for p in SNAPSHOTS_DARK_DIR.glob("*.png")
)


# ── session-scoped lazy renderer ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def _png_cache(tmp_path_factory, request):
    """One SnapshotRasterSession for the whole pytest session.

    Returns a callable ``get_png(fixture_path, theme) -> Path | None``.
    ``None`` means either the fixture type is unsupported or no baseline exists
    (comparison mode) — both cases skip rendering entirely.

    Performance invariants:
    - _dispatch called once per fixture (not per theme).
    - render_html called once per (fixture, theme) pair.
    - Pairs with no baseline skipped before compilation in comparison mode.
    - One BrowserContext + one Page reused for all renders via set_content.
    """
    from mermaid_layout import _dispatch, make_page
    from mermaid_render.browser import BrowserSession, SnapshotRasterSession
    from mermaid_render.browser_lock import browser_budget

    capture: bool = request.config.getoption("--snapshot-capture", default=False)
    cache_dir = tmp_path_factory.mktemp("snapshot_pngs", numbered=False)

    _cache: dict[tuple[str, str], "Path | None"] = {}
    _fragment_cache: dict[str, "str | None"] = {}

    with browser_budget():
        with BrowserSession() as bs:
            session = SnapshotRasterSession(bs._browser)
            try:

                def _get_png(fixture_path: Path, theme: str) -> "Path | None":
                    key = (fixture_path.stem, theme)
                    if key in _cache:
                        return _cache[key]

                    # Manifest pre-filter: in comparison mode, skip pairs with no baseline.
                    if manifest_prefilter_applies(key, _BASELINE_MANIFEST, capture):
                        _cache[key] = None
                        return None

                    # Compile once per fixture (theme-independent).
                    stem = fixture_path.stem
                    if stem not in _fragment_cache:
                        src = fixture_path.read_text()
                        try:
                            _fragment_cache[stem] = _dispatch(src, None, 800)
                        except ValueError:
                            _fragment_cache[stem] = None

                    fragment = _fragment_cache[stem]
                    if fragment is None:
                        _cache[key] = None
                        return None

                    html = make_page(fragment, theme=theme)
                    png_path = cache_dir / f"{stem}-{theme}.png"
                    png_bytes = session.render_html(html)
                    png_path.write_bytes(png_bytes)
                    _cache[key] = png_path
                    return png_path

                yield _get_png

            finally:
                session.close()


# ── comparison helper ──────────────────────────────────────────────────────────

def _collect_comparison_failures(
    img_new: "Image.Image",
    img_base: "Image.Image",
    label: str,
    failures: list[str],
) -> None:
    """Run all fidelity and smoke metrics against already-open images."""
    import numpy as np
    from PIL import Image, ImageChops

    arr_new = np.array(img_new)
    arr_base = np.array(img_base)
    w_new, h_new = img_new.size
    w_base, h_base = img_base.size

    # 1. Canvas dimensions
    if w_new != w_base:
        failures.append(f"{label}: canvas width was {w_base}px, now {w_new}px")
    if h_new != h_base:
        failures.append(f"{label}: canvas height was {h_base}px, now {h_new}px")

    # 2. Content bounding box (±16 px per axis)
    def _bbox(arr):
        bg = arr[0, 0]
        mask = ~(arr == bg).all(axis=-1)
        if not mask.any():
            return None
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)

    bb_new = _bbox(arr_new)
    bb_base = _bbox(arr_base)
    if bb_new and bb_base:
        cw_new  = bb_new[2]  - bb_new[0]
        ch_new  = bb_new[3]  - bb_new[1]
        cw_base = bb_base[2] - bb_base[0]
        ch_base = bb_base[3] - bb_base[1]
        if abs(cw_new - cw_base) > 16 or abs(ch_new - ch_base) > 16:
            failures.append(
                f"{label}: content bounds were {cw_base}×{ch_base}px, "
                f"now {cw_new}×{ch_new}px (threshold ±16px)"
            )

    # 3. Pixel diff at original dimensions
    if img_new.size == img_base.size:
        diff = ImageChops.difference(img_new, img_base)
        nonzero = int((np.array(diff) > 0).any(axis=-1).sum())
        total = w_base * h_base
        pct = nonzero / total
        if pct > 0.005:
            failures.append(
                f"{label}: pixel diff {pct:.1%} at original size (threshold 0.5%)"
            )
    else:
        failures.append(f"{label}: canvas size changed — fix canvas first")

    # 4. Smoke: resize-tolerant diff (catches content regressions past size changes)
    img_resized = img_new.resize(img_base.size, Image.LANCZOS) if img_new.size != img_base.size else img_new
    diff_smoke = ImageChops.difference(img_resized, img_base)
    nonzero_smoke = int((np.array(diff_smoke) > 0).any(axis=-1).sum())
    pct_smoke = nonzero_smoke / (w_base * h_base)
    if pct_smoke > 0.005:
        failures.append(
            f"{label}: smoke diff {pct_smoke:.1%} after resize (threshold 0.5%)"
        )


# ── fused snapshot test ───────────────────────────────────────────────────────

@pytest.mark.browser
@pytest.mark.snapshot
@pytest.mark.parametrize(
    "fixture,theme",
    [(f, t) for f in _FIXTURES for t in ("light", "dark")],
    ids=lambda x: x.stem if hasattr(x, "stem") else x,
)
def test_snapshot_fused(fixture: Path, theme: str, _png_cache: Callable, request):
    """Fused smoke + fidelity comparison for one (fixture, theme) pair.

    Opens rendered and baseline images at most once per pair.
    A SHA-256 byte-equality fast path exits before any PIL/NumPy work when
    the images are byte-identical.
    In capture mode, copies the baseline and returns immediately.
    """
    capture: bool = request.config.getoption("--snapshot-capture", default=False)
    baseline_dir = SNAPSHOTS_LIGHT_DIR if theme == "light" else SNAPSHOTS_DARK_DIR
    baseline = baseline_dir / (fixture.stem + ".png")

    rendered = _png_cache(fixture, theme)
    if rendered is None:
        pytest.skip(f"{fixture.stem}[{theme}]: unsupported type or no baseline")

    if capture:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rendered, baseline)
        return

    if not baseline.exists():
        pytest.skip(
            f"no baseline for {fixture.stem}[{theme}] — run with --snapshot-capture"
        )

    rendered_bytes = rendered.read_bytes()
    baseline_bytes = baseline.read_bytes()

    # SHA-256 fast path: identical bytes → no image decode needed.
    if sha256_bytes_equal(rendered_bytes, baseline_bytes):
        return

    from PIL import Image
    img_new = Image.open(rendered).convert("RGB")
    img_base = Image.open(baseline).convert("RGB")

    failures: list[str] = []
    label = f"{fixture.stem}[{theme}]"
    _collect_comparison_failures(img_new, img_base, label, failures)

    assert not failures, "\n".join(f"  {f}" for f in failures)

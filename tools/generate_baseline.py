#!/usr/bin/env python3
"""generate_baseline.py -- generate the provenance-locked Mermaid comparison baseline.

Usage:
    python3 tools/generate_baseline.py [--allow-dirty] [--mode {editorial,fidelity,both}]

Generates the comparison gallery for all 15 baseline fixtures against the current
HEAD commit. Enforces that:
  1. The working tree is clean (override with --allow-dirty).
  2. npm dependencies are installed (runs `npm ci` automatically).
  3. All 15 target fixtures are present in tests/fixtures/.

Writes output to ppt-output/compare/ with a provenance-locked metadata.json.
Exits nonzero if any hard-fail guard triggers or if any fixture fails to render.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Minimum commit: the baseline was defined at or after this SHA.
_MIN_COMMIT_SHA = "45055ac827f4a7e68a01090e4468338aaed6bd7f"

# The 15 target fixture names (without .mmd extension).
_TARGET_FIXTURES = [
    "architecture-complex",
    "class-relationships-all",
    "er-cardinality-all",
    "er-ecommerce",
    "flowchart-all-shapes",
    "flowchart-arrows-defs",
    "flowchart-diamond-branch",
    "flowchart-diamond-clipping",
    "flowchart-empty-subgraph",
    "flowchart-groups-complex",
    "flowchart-inner-direction",
    "flowchart-parallel-links",
    "requirement-basic",
    "statediagram-complex",
    "statediagram-nested",
]


def _abort(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _run_npm_ci() -> None:
    """Run npm ci --prefix scripts/mermaid_render/layout to pin elkjs."""
    layout_dir = ROOT / "scripts" / "mermaid_render" / "layout"
    print("Running npm ci to ensure pinned elkjs is installed...", flush=True)
    result = subprocess.run(
        ["npm", "ci", "--prefix", str(layout_dir)],
        cwd=ROOT,
    )
    if result.returncode != 0:
        _abort(f"npm ci failed with exit code {result.returncode}")
    print("npm ci complete.", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the provenance-locked Mermaid baseline gallery")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="Allow generation from a dirty working tree")
    ap.add_argument("--mode", choices=["editorial", "fidelity", "both"], default="both",
                    help="Rendering lane(s) to include (default: both)")
    ap.add_argument("--height-hint", dest="height_hint", type=int, default=0,
                    help="Renderer height hint in px (default: 0 = auto); recorded in per-fixture provenance")
    ap.add_argument("--output-dir", dest="output_dir", default=None,
                    help="Write gallery to this directory (default: ppt-output/compare/)")
    args = ap.parse_args()

    # Step 1: Check HEAD commit (informational; not a hard gate on ancestry).
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    if not head_sha:
        _abort("Could not determine HEAD commit via git rev-parse HEAD")

    print(f"HEAD: {head_sha}", flush=True)

    # Step 2: Run npm ci to ensure pinned elkjs is present.
    _run_npm_ci()

    # Step 3: Collect the 15 target fixture paths.
    fixtures_dir = ROOT / "tests" / "fixtures"
    mmd_files: list[Path] = []
    missing: list[str] = []
    for name in _TARGET_FIXTURES:
        p = fixtures_dir / f"{name}.mmd"
        if p.exists():
            mmd_files.append(p)
        else:
            missing.append(name)

    if missing:
        _abort(f"Missing {len(missing)} fixture(s): {missing}")

    # Step 4: Set up output directory and add scripts/ to sys.path.
    out_dir = Path(args.output_dir).resolve() if args.output_dir else ROOT / "ppt-output" / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "tools"))

    import importlib
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "compare_gallery", ROOT / "tools" / "compare_gallery.py"
    )
    gallery = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(gallery)  # type: ignore[union-attr]

    # Step 5: Write metadata.json (provenance lock).
    metadata = gallery._collect_metadata(mmd_files, out_dir, 0, sys.argv[1:])
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Metadata written: {meta_path}", flush=True)

    # Step 6: Build gallery.
    print(f"Building baseline gallery for {len(mmd_files)} fixture(s) [mode={args.mode}]...", flush=True)
    index_path, has_failures, fixture_results = gallery._build_gallery(
        mmd_files,
        out_dir,
        width_hint=0,
        height_hint=args.height_hint,
        strict=False,
        allow_dirty=args.allow_dirty,
        mode=args.mode,
    )
    metadata["fixture_results"] = fixture_results
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Step 7: Print summary.
    elk_available = any(r.get("actual_layout_backend") == "elk" for r in fixture_results)
    print(
        f"\nBaseline gallery: file://{index_path}",
        flush=True,
    )
    print(
        f"Fixtures: {len(fixture_results)}  |  HEAD: {head_sha}  |  ELK: {'available' if elk_available else 'not available'}",
        flush=True,
    )

    if has_failures:
        print("FAIL: one or more hard-fail guards triggered.", file=sys.stderr)
        sys.exit(1)

    print("OK: baseline gallery generated successfully.")


if __name__ == "__main__":
    main()

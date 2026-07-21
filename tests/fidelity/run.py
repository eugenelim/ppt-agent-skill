"""Repository entry point for the Mermaid fidelity harness.

Usage:
    python tests/fidelity/run.py [--oracle-id mermaid-11.15.0-neutral]
                                 [--report-dir tests/fidelity/reports/]
                                 [--case-filter GLOB]
                                 [--capture-reference]
                                 [--check-determinism]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_FIDELITY_DIR = Path(__file__).resolve().parent
_REPO = _FIDELITY_DIR.parents[1]

sys.path.insert(0, str(_REPO / "tools"))
sys.path.insert(0, str(_REPO / "scripts"))

_MANIFEST_PATH = _FIDELITY_DIR / "cases.toml"
_ORACLE_BASE = _FIDELITY_DIR / "oracle"
_PROFILES_DIR = _FIDELITY_DIR / "profiles"
_DEFAULT_ORACLE_ID = "mermaid-11.15.0-neutral"


def _load_profile():
    import json
    from mermaid_fidelity.models import RenderProfile

    cfg_path = _PROFILES_DIR / "mermaid-neutral.json"
    css_path = _PROFILES_DIR / "native-neutral.css"
    cfg = json.loads(cfg_path.read_text())
    vp = cfg.get("viewport", {})
    return RenderProfile(
        id="mermaid-neutral",
        viewport_width=vp.get("width", 1200),
        viewport_height=vp.get("height", 900),
        device_scale_factor=cfg.get("device_scale_factor", 1.0),
        locale=cfg.get("locale", "en-US"),
        timezone=cfg.get("timezone", "UTC"),
        reduced_motion=cfg.get("reduced_motion", True),
        css_path=css_path,
        mermaid_config=cfg.get("mermaid_init"),
    )


def _load_manifest():
    from mermaid_fidelity.manifest import parse_manifest
    return parse_manifest(_MANIFEST_PATH, load_sources=True)


def cmd_run(args) -> int:
    from mermaid_fidelity.manifest import parse_manifest
    from mermaid_fidelity.runner import FidelityRunner
    from mermaid_fidelity.report import generate_json_report, generate_md_report
    from adapters.native import NativeAdapter

    manifest = _load_manifest()
    profile = _load_profile()
    oracle_dir = _ORACLE_BASE / args.oracle_id

    cases = manifest.cases
    if args.case_filter:
        import fnmatch
        cases = [c for c in cases if fnmatch.fnmatch(c.id, args.case_filter)]

    runner = FidelityRunner(
        native_adapter=NativeAdapter(),
        oracle_dir=oracle_dir,
        tolerances=None,
    )
    summary = runner.run_all(cases, profile)

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "report.json"
    md_path = report_dir / "report.md"

    json_path.write_text(generate_json_report(summary), encoding="utf-8")
    md_path.write_text(generate_md_report(summary), encoding="utf-8")

    print(f"Report: {md_path}")
    print(f"Cases run: {len(summary.results)}")

    fail_statuses = {"SEMANTIC_MISMATCH", "PARSE_MISMATCH", "NONDETERMINISTIC", "INTERNAL_ERROR"}
    failures = [r for r in summary.results if r.status.value in fail_statuses]
    if failures:
        print(f"FAILED: {[r.case_id for r in failures]}", file=sys.stderr)
        return 1
    return 0


def cmd_capture_reference(args) -> int:
    """Capture oracle observations from mmdc for all 24 cases."""
    from adapters.reference import ReferenceAdapter
    from mermaid_fidelity.serialization import save_json

    manifest = _load_manifest()
    profile = _load_profile()
    oracle_dir = _ORACLE_BASE / args.oracle_id
    cases_dir = oracle_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    adapter = ReferenceAdapter()
    ok = 0
    failed = []
    for case in manifest.cases:
        print(f"  capturing {case.id}...", end=" ", flush=True)
        obs = adapter.observe(case, profile)
        out_path = cases_dir / f"{case.id}.json"
        save_json(obs, out_path)
        status = obs.status.value
        print(status)
        if status in ("REFERENCE_RENDER_FAILURE", "INTERNAL_ERROR"):
            failed.append(case.id)
        else:
            ok += 1

    print(f"\nCaptured {ok}/{len(manifest.cases)}")
    if failed:
        print(f"Failed: {failed}", file=sys.stderr)
        return 1
    return 0


def cmd_determinism(args) -> int:
    from adapters.native import NativeAdapter
    from mermaid_fidelity.runner import FidelityRunner

    manifest = _load_manifest()
    profile = _load_profile()
    runner = FidelityRunner(
        native_adapter=NativeAdapter(),
        oracle_dir=_ORACLE_BASE / args.oracle_id,
        tolerances=None,
    )
    results = runner.run_determinism(manifest.cases, profile, runs=3)
    nondeterministic = [r for r in results if r.status.value == "NONDETERMINISTIC"]
    if nondeterministic:
        print(f"NONDETERMINISTIC: {[r.case_id for r in nondeterministic]}", file=sys.stderr)
        return 1
    print(f"All {len(results)} cases deterministic")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Mermaid fidelity harness")
    parser.add_argument("--oracle-id", default=_DEFAULT_ORACLE_ID)
    parser.add_argument("--report-dir", default=str(_FIDELITY_DIR / "reports"))
    parser.add_argument("--case-filter", default=None)

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run fidelity comparisons against oracle")
    sub.add_parser("capture-reference", help="Capture reference oracle observations")
    sub.add_parser("determinism", help="Check native renderer determinism")
    sub.add_parser("validate", help="Validate cases.toml manifest")

    args = parser.parse_args()

    if args.command is None or args.command == "run":
        return cmd_run(args)
    elif args.command == "capture-reference":
        return cmd_capture_reference(args)
    elif args.command == "determinism":
        return cmd_determinism(args)
    elif args.command == "validate":
        _load_manifest()
        print("Manifest OK")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

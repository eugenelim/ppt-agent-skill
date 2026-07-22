"""Reusable CLI for the fidelity harness.

Repository adapters provide the wiring (adapters, manifest path, oracle dir).
This module provides argument parsing and command dispatch that can be used
independently of any specific repository layout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mermaid_fidelity",
        description="Mermaid rendering fidelity benchmark — Phase 1",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # validate
    val = sub.add_parser("validate", help="Validate the cases manifest")
    val.add_argument("--manifest", type=Path, required=True)

    # run
    run = sub.add_parser("run", help="Run fidelity checks against committed oracle")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--oracle-dir", type=Path, required=True)
    run.add_argument("--ref-id", type=str, required=True)
    run.add_argument("--report-dir", type=Path, required=True)
    run.add_argument("--case", type=str, dest="case_id", default=None)
    run.add_argument("--profile", type=str, default="native-production")

    # capture-reference
    cap = sub.add_parser("capture-reference", help="Capture oracle reference observations")
    cap.add_argument("--manifest", type=Path, required=True)
    cap.add_argument("--output", type=Path, required=True)
    cap.add_argument("--ref-id", type=str, required=True)
    cap.add_argument("--force", action="store_true",
                     help="Overwrite committed reference observations")

    # determinism
    det = sub.add_parser("determinism", help="Check rendering determinism")
    det.add_argument("--manifest", type=Path, required=True)
    det.add_argument("--oracle-dir", type=Path, required=True)
    det.add_argument("--ref-id", type=str, required=True)
    det.add_argument("--runs", type=int, default=3)
    det.add_argument("--report-dir", type=Path, required=True)

    return p


def cmd_validate(args: argparse.Namespace, *, manifest_loader: Any) -> int:
    """Validate the manifest; return 0 on success, 1 on error."""
    try:
        manifest = manifest_loader(args.manifest)
        print(f"✓ Manifest valid: {len(manifest.cases)} cases")
        for case in manifest.cases:
            print(f"  {case.id}")
        return 0
    except Exception as e:
        print(f"✗ Manifest validation failed: {e}", file=sys.stderr)
        return 1


def cmd_run(
    args: argparse.Namespace,
    *,
    manifest_loader: Any,
    runner_factory: Any,
    profile_loader: Any,
) -> int:
    """Run fidelity checks; return 0 on pass, 1 on failures."""
    from .report import generate_json_report, generate_md_report, generate_html_report
    from .models import ComparisonStatus

    try:
        manifest = manifest_loader(args.manifest)
    except Exception as e:
        print(f"✗ Manifest load failed: {e}", file=sys.stderr)
        return 1

    profile = profile_loader(args.profile)
    runner = runner_factory(profile)
    case_ids = [args.case_id] if args.case_id else None

    summary = runner.run_all(manifest, profile, args.ref_id, case_ids=case_ids)

    report_dir = args.report_dir
    json_path = generate_json_report(summary, report_dir, args.ref_id)
    md_path = generate_md_report(summary, report_dir, args.ref_id)
    html_path = generate_html_report(summary, report_dir, args.ref_id)

    print(f"\nFidelity report: {summary.passed}/{summary.total} passed")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")

    _print_failures(summary)

    # Hard-fail statuses — nonzero exit for any of these.
    # Scored metric differences alone do not gate CI (Phase 1).
    # NATIVE_UNSUPPORTED is excluded: stub diagram types are expected and acceptable.
    _HARD_FAIL_STATUSES = {
        ComparisonStatus.PARSE_MISMATCH,
        ComparisonStatus.SEMANTIC_MISMATCH,
        ComparisonStatus.RELATIVE_LAYOUT_MISMATCH,
        ComparisonStatus.QUALITY_FAILURE,
        ComparisonStatus.EXTRACTOR_GAP,
        ComparisonStatus.STALE_ORACLE,
        ComparisonStatus.INVALID_MANIFEST,
        ComparisonStatus.NONDETERMINISTIC,
        ComparisonStatus.INTERNAL_ERROR,
    }
    strict_failures = [
        r for r in summary.results
        if r.final_status in _HARD_FAIL_STATUSES
    ]
    if strict_failures:
        print(f"\n✗ {len(strict_failures)} strict failure(s)", file=sys.stderr)
        return 1
    return 0


def cmd_capture_reference(
    args: argparse.Namespace,
    *,
    manifest_loader: Any,
    ref_adapter_factory: Any,
    profile_loader: Any,
) -> int:
    """Capture reference observations into the oracle directory."""
    from .serialization import save_json
    from .models import ComparisonStatus
    import datetime

    try:
        manifest = manifest_loader(args.manifest)
    except Exception as e:
        print(f"✗ Manifest load failed: {e}", file=sys.stderr)
        return 1

    output_dir = args.output / args.ref_id
    cases_dir = output_dir / "cases"
    env_path = output_dir / "environment.json"

    # Check for existing committed observations
    if not args.force and cases_dir.exists():
        existing = list(cases_dir.glob("*.json"))
        if existing:
            print(
                f"✗ {len(existing)} committed reference observations exist at {cases_dir}.\n"
                f"  Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    profile = profile_loader("mermaid-neutral")
    ref_adapter = ref_adapter_factory()

    cases_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    for case in manifest.cases:
        print(f"  Capturing {case.id}…", end="", flush=True)
        obs = ref_adapter.observe(case, profile)
        obs.capture_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_json(obs, cases_dir / f"{case.id}.json")
        status = obs.status.value
        print(f" {status}")
        if obs.status not in (ComparisonStatus.PASS, ComparisonStatus.EXTRACTOR_GAP):
            errors += 1

    # Write environment.json
    identity = ref_adapter.identity()
    env_data = {
        "ref_id": args.ref_id,
        "adapter": {
            "name": identity.name,
            "version": identity.version,
            "adapter_version": identity.adapter_version,
        },
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    save_json(env_data, env_path)

    print(f"\n✓ Captured {len(manifest.cases)} cases to {output_dir}")
    if errors:
        print(f"  {errors} non-PASS/non-gap observation(s)")
    return 0


def cmd_determinism(
    args: argparse.Namespace,
    *,
    manifest_loader: Any,
    runner_factory: Any,
    profile_loader: Any,
) -> int:
    """Check rendering determinism; return 0 if stable."""
    from .serialization import save_json
    import json

    _DETERMINISM_CASES = {
        "flowchart.groups.complex",
        "flowchart.parallel.links",
        "flowchart.shapes.new",
        "sequence.complex",
        "architecture.groups.complex",
        "er.ecommerce",
    }

    try:
        manifest = manifest_loader(args.manifest)
    except Exception as e:
        print(f"✗ Manifest load failed: {e}", file=sys.stderr)
        return 1

    cases = [c for c in manifest.cases if c.id in _DETERMINISM_CASES]
    if not cases:
        print("✗ No determinism-subset cases found in manifest", file=sys.stderr)
        return 1

    profile = profile_loader("native-production")
    runner = runner_factory(profile)
    report = runner.run_determinism(cases, profile, runs=args.runs)

    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    out = report_dir / "determinism.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    if not report["stable"]:
        unstable = [cid for cid, cr in report["cases"].items() if not cr["stable"]]
        print(f"✗ Nondeterministic cases: {unstable}")
        for cid in unstable:
            cr = report["cases"][cid]
            for diff in cr.get("diffs", [])[:5]:
                print(f"  {diff}")
        return 1

    print(f"✓ All {len(cases)} determinism cases stable over {args.runs} runs")
    return 0


def _print_failures(summary: Any) -> None:
    from .models import ComparisonStatus
    for r in summary.results:
        if r.final_status != ComparisonStatus.PASS:
            print(f"  {r.final_status.value:<30} {r.case_id}")
            if r.reason:
                print(f"    → {r.reason[:100]}")

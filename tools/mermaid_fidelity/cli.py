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

    # Validate --case ID before running
    if args.case_id:
        known_ids = {c.id for c in manifest.cases}
        if args.case_id not in known_ids:
            print(
                f"✗ Unknown case ID: {args.case_id!r}. "
                f"Known cases: {sorted(known_ids)}",
                file=sys.stderr,
            )
            return 1

    profile = profile_loader(args.profile)
    runner = runner_factory(profile)
    case_ids = [args.case_id] if args.case_id else None

    try:
        summary = runner.run_all(manifest, profile, args.ref_id, case_ids=case_ids)
    except ValueError as e:
        print(f"✗ Run error: {e}", file=sys.stderr)
        return 1

    report_dir = args.report_dir
    json_path = generate_json_report(summary, report_dir, args.ref_id)
    md_path = generate_md_report(summary, report_dir, args.ref_id)
    html_path = generate_html_report(summary, report_dir, args.ref_id)

    # Print lifecycle-aware summary
    print(f"\nActive compatibility: {summary.active_passed}/{summary.active_total} passed")
    if summary.active_failed:
        print(f"  {summary.active_failed} active case(s) failed")
    print(
        f"Planned coverage: {summary.planned_unsupported}/{summary.planned_total} unsupported "
        f"(expected — native support not yet implemented)"
    )
    print(f"\nFidelity report: {summary.passed}/{summary.total} total passed")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"  HTML: {html_path}")

    _print_failures(summary, manifest)

    # Hard-fail statuses — nonzero exit for any of these.
    # Scored metric differences alone do not gate CI (Phase 1).
    # NATIVE_UNSUPPORTED is only acceptable for planned cases.
    _HARD_FAIL_STATUSES = {
        ComparisonStatus.PARSE_MISMATCH,
        ComparisonStatus.SEMANTIC_MISMATCH,
        ComparisonStatus.RELATIVE_LAYOUT_MISMATCH,
        ComparisonStatus.QUALITY_FAILURE,
        ComparisonStatus.EXTRACTOR_GAP,
        ComparisonStatus.REFERENCE_RENDER_FAILURE,
        ComparisonStatus.STALE_ORACLE,
        ComparisonStatus.INVALID_MANIFEST,
        ComparisonStatus.NONDETERMINISTIC,
        ComparisonStatus.INTERNAL_ERROR,
    }
    lifecycle_by_id = {c.id: getattr(c, "lifecycle", "active") for c in manifest.cases}
    strict_failures = [
        r for r in summary.results
        if r.final_status in _HARD_FAIL_STATUSES
        or (
            # Belt-and-suspenders: runner.run_all() already escalates active
            # NATIVE_UNSUPPORTED to INTERNAL_ERROR, so this branch is normally
            # unreachable — but kept here as a safety net.
            r.final_status == ComparisonStatus.NATIVE_UNSUPPORTED
            and lifecycle_by_id.get(r.case_id, "active") == "active"
        )
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

    import shutil
    import os

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

    # Transactional capture: write to a sibling temp dir (same filesystem → rename-atomic),
    # gate on zero hard errors, then replace.
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_cases = output_dir / f".cases_tmp_{os.getpid()}"
    tmp_env = output_dir / f".env_tmp_{os.getpid()}.json"
    try:
        tmp_cases.mkdir()

        errors = 0
        for case in manifest.cases:
            print(f"  Capturing {case.id}…", end="", flush=True)
            obs = ref_adapter.observe(case, profile)
            obs.capture_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save_json(obs, tmp_cases / f"{case.id}.json")
            status = obs.status.value
            print(f" {status}")
            if obs.status not in (ComparisonStatus.PASS, ComparisonStatus.EXTRACTOR_GAP):
                errors += 1

        if errors > 0:
            shutil.rmtree(tmp_cases, ignore_errors=True)
            print(
                f"\n✗ {errors} observation(s) failed — oracle NOT updated; "
                f"fix failures and retry.",
                file=sys.stderr,
            )
            return 1

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
        save_json(env_data, tmp_env)

        # Near-atomic replace: rename sibling temp dirs over the targets.
        # If cases_dir already exists, rename it aside first.
        old_cases = output_dir / f".cases_old_{os.getpid()}"
        if cases_dir.exists():
            cases_dir.rename(old_cases)
        try:
            tmp_cases.rename(cases_dir)
        except Exception:
            if old_cases.exists():
                old_cases.rename(cases_dir)  # restore original
            raise
        if old_cases.exists():
            shutil.rmtree(old_cases, ignore_errors=True)

        tmp_env.rename(env_path)

    except Exception:
        if tmp_cases.exists():
            shutil.rmtree(tmp_cases, ignore_errors=True)
        if tmp_env.exists():
            tmp_env.unlink(missing_ok=True)
        raise

    print(f"\n✓ Captured {len(manifest.cases)} cases to {output_dir}")
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

    # Only active-lifecycle cases test determinism: sequence/er are planned and
    # their NATIVE_UNSUPPORTED result is trivially stable — not a useful signal.
    _DETERMINISM_CASES = {
        "flowchart.groups.complex",
        "flowchart.parallel.links",
        "flowchart.shapes.new",
        "architecture.groups.complex",
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


def _print_failures(summary: Any, manifest: Any = None) -> None:
    from .models import ComparisonStatus
    lifecycle_by_id: dict[str, str] = {}
    if manifest is not None:
        lifecycle_by_id = {c.id: getattr(c, "lifecycle", "active") for c in manifest.cases}
    for r in summary.results:
        if r.final_status != ComparisonStatus.PASS:
            lifecycle = lifecycle_by_id.get(r.case_id, "active")
            tag = f"[{lifecycle}]"
            print(f"  {r.final_status.value:<30} {r.case_id} {tag}")
            if r.reason:
                print(f"    → {r.reason[:100]}")

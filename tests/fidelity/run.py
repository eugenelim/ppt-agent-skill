"""Repository entry point for the Mermaid fidelity harness.

Thin wrapper: provides repository-specific paths and adapter wiring,
then delegates all command logic to tools/mermaid_fidelity/cli.py.

Usage:
    python tests/fidelity/run.py validate
    python tests/fidelity/run.py run [--case CASE_ID] --report-dir DIR
    python tests/fidelity/run.py capture-reference --output DIR [--force]
    python tests/fidelity/run.py determinism [--runs N] --report-dir DIR
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


# ── callback factories ────────────────────────────────────────────────────────

def _manifest_loader(path: Path):
    from mermaid_fidelity.manifest import parse_manifest
    return parse_manifest(path, load_sources=True)


def _profile_loader(profile_id: str):
    import json
    from mermaid_fidelity.models import RenderProfile

    cfg_path = _PROFILES_DIR / "mermaid-neutral.json"
    css_path = _PROFILES_DIR / "native-neutral.css"
    cfg = json.loads(cfg_path.read_text())
    vp = cfg.get("viewport", {})
    return RenderProfile(
        id=profile_id,
        viewport_width=vp.get("width", 1200),
        viewport_height=vp.get("height", 900),
        device_scale_factor=cfg.get("device_scale_factor", 1.0),
        locale=cfg.get("locale", "en-US"),
        timezone=cfg.get("timezone", "UTC"),
        reduced_motion=cfg.get("reduced_motion", True),
        css_path=css_path,
        mermaid_config=cfg.get("mermaid_init"),
    )


def _runner_factory(oracle_base: Path):
    """Return a runner factory that pre-bakes the oracle base directory.

    FidelityRunner.run_case builds the full path as:
        oracle_dir / ref_id / "cases" / "{case_id}.json"
    so oracle_dir must be the base (e.g. tests/fidelity/oracle), not
    oracle_base / ref_id.
    """
    from mermaid_fidelity.runner import FidelityRunner
    from adapters.native_svg import NativeSvgAdapter

    def factory(profile):
        return FidelityRunner(
            native_adapter=NativeSvgAdapter(),
            oracle_dir=oracle_base,
            tolerances=None,
        )
    return factory


def _ref_adapter_factory():
    from adapters.reference import ReferenceAdapter
    return ReferenceAdapter()


# ── argument parsing ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Mermaid fidelity harness — repository entry point",
    )
    p.add_argument(
        "--oracle-id", default=_DEFAULT_ORACLE_ID,
        help=f"Reference oracle identifier (default: {_DEFAULT_ORACLE_ID})",
    )

    sub = p.add_subparsers(dest="command")

    # validate
    sub.add_parser("validate", help="Validate cases.toml manifest + oracle integrity")

    # run
    run_p = sub.add_parser("run", help="Run fidelity comparisons against oracle")
    run_p.add_argument("--case", dest="case_id", default=None,
                       help="Run a single case by exact ID")
    run_p.add_argument("--report-dir", type=Path,
                       default=_FIDELITY_DIR / "reports",
                       help="Directory to write report.json and report.md")

    # capture-reference
    cap_p = sub.add_parser("capture-reference",
                            help="Capture oracle reference observations via mmdc")
    cap_p.add_argument("--output", type=Path, default=_ORACLE_BASE,
                       help="Oracle base directory (case JSONs go under <output>/<oracle-id>/cases/)")
    cap_p.add_argument("--force", action="store_true",
                       help="Overwrite existing oracle files")

    # determinism
    det_p = sub.add_parser("determinism", help="Check rendering determinism")
    det_p.add_argument("--runs", type=int, default=3,
                       help="Number of render passes per case (default: 3)")
    det_p.add_argument("--report-dir", type=Path,
                       default=_FIDELITY_DIR / "reports" / "determinism",
                       help="Directory to write determinism.json")

    return p


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    from mermaid_fidelity import cli

    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "validate":
        ns = argparse.Namespace(
            manifest=_MANIFEST_PATH,
            oracle_dir=_ORACLE_BASE,
            ref_id=args.oracle_id,
        )
        return cli.cmd_validate(ns, manifest_loader=_manifest_loader)

    elif args.command == "run":
        ns = argparse.Namespace(
            manifest=_MANIFEST_PATH,
            oracle_dir=_ORACLE_BASE,
            ref_id=args.oracle_id,
            report_dir=args.report_dir,
            case_id=args.case_id,
            profile="native-production",
        )
        return cli.cmd_run(
            ns,
            manifest_loader=_manifest_loader,
            runner_factory=_runner_factory(_ORACLE_BASE),
            profile_loader=_profile_loader,
        )

    elif args.command == "capture-reference":
        ns = argparse.Namespace(
            manifest=_MANIFEST_PATH,
            output=args.output,
            ref_id=args.oracle_id,
            force=args.force,
            profile="mermaid-neutral",
        )
        return cli.cmd_capture_reference(
            ns,
            manifest_loader=_manifest_loader,
            ref_adapter_factory=_ref_adapter_factory,
            profile_loader=_profile_loader,
        )

    elif args.command == "determinism":
        ns = argparse.Namespace(
            manifest=_MANIFEST_PATH,
            oracle_dir=_ORACLE_BASE,
            ref_id=args.oracle_id,
            runs=args.runs,
            report_dir=args.report_dir,
            profile="native-production",
        )
        return cli.cmd_determinism(
            ns,
            manifest_loader=_manifest_loader,
            runner_factory=_runner_factory(_ORACLE_BASE),
            profile_loader=_profile_loader,
        )

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

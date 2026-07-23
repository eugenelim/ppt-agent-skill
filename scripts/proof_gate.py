#!/usr/bin/env python3
"""proof_gate.py -- the Step-4.5 Review/Render decision gate (writer + checker).

The Step 4.5 gate ([slide-intent-review]) is prose-only, and a model with the
hardened STOP instruction in-context has slid Step 4 -> Step 5 without ever
presenting the Review/Render choice. This script turns that soft "ask first"
instruction into a concrete, verifiable precondition:

- ``--decision review|render-direct`` records the user's choice to
  ``OUTPUT_DIR/runtime/proof/gate.json`` (idempotent-overwrite -- last decision
  wins; a user may change their mind).
- ``--check`` exits non-zero when that marker is absent or invalid, with an
  actionable message naming Step 4.5 and the exact ``--decision`` command.

SKILL.md Step 5c runs ``--check`` before writing any slide HTML; a non-zero exit
is a hard STOP meaning Step 4.5 was skipped.

Known limit: this is still prose-invoked, and ``render-direct`` is a zero-evidence
self-attested bypass (option B legitimately renders without a worksheet). The
marker proves *a decision was recorded*, not that a review happened. A truly
unskippable gate needs a harness PreToolUse hook (user settings, not this skill).

Deterministic: no system-clock or network read; ``gate.json`` is a fixed
two-key shape so two identical decisions produce byte-identical files.

Usage:
    python3 scripts/proof_gate.py <output_dir> --decision review|render-direct
    python3 scripts/proof_gate.py <output_dir> --check
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Local literal -- intentionally NOT sourced from workflow_versions.py: the gate
# marker is workflow scratch, not a schema on the version bus, and coupling it
# there would break the byte-identity contract on every version bump.
SCHEMA_VERSION = "1"

# Path to this script's directory (scripts/), used by check_deliverable_gate.
SCRIPTS_DIR = Path(__file__).resolve().parent

DECISIONS = ("review", "render-direct")
PROOF_DIR_REL = Path("runtime") / "proof"
GATE_REL = PROOF_DIR_REL / "gate.json"


class ProofGateError(Exception):
    """Raised for an operator-actionable failure (missing worksheet, etc.)."""


def _proof_dir(output_dir: Path) -> Path:
    return output_dir / PROOF_DIR_REL


def _gate_file(output_dir: Path) -> Path:
    return output_dir / GATE_REL


def _worksheet_file(output_dir: Path) -> Path:
    # proof_worksheet.py writes runtime/proof/<deck-slug>-intent.html where the
    # deck-slug is the OUTPUT_DIR directory name. Slug-scoped on purpose: a stale
    # worksheet from a different deck must not satisfy this deck's review gate.
    return _proof_dir(output_dir) / f"{output_dir.name}-intent.html"


def record_decision(output_dir: Path, decision: str) -> Path:
    """Write the decision marker. For ``review``, require the deck's worksheet to
    exist first (you cannot confirm a review that was never rendered)."""
    if decision not in DECISIONS:
        raise ProofGateError(f"unknown decision {decision!r}; expected one of {DECISIONS}")
    if decision == "review":
        ws = _worksheet_file(output_dir)
        if not ws.exists():
            raise ProofGateError(
                f"cannot record 'review': worksheet not found at {ws.name} (under "
                f"{PROOF_DIR_REL}/). Render it first:\n"
                f"    python3 SKILL_DIR/scripts/proof_worksheet.py {output_dir} [--as-of DATE]\n"
                f"or record --decision render-direct to skip the worksheet."
            )
    proof_dir = _proof_dir(output_dir)
    proof_dir.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "decision": decision}
    # Idempotent-overwrite: last decision wins. sort_keys + no clock => deterministic.
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    gate = _gate_file(output_dir)
    gate.write_text(text, encoding="utf-8")
    return gate


def _remediation(output_dir: Path) -> str:
    return (
        "Step 4.5 gate not recorded: you must present the user the Review/Render "
        "choice, then record it:\n"
        f"    python3 SKILL_DIR/scripts/proof_gate.py {output_dir} "
        "--decision review|render-direct"
    )


def gate_status(output_dir: Path) -> tuple[bool, str]:
    """Return (ok, message). ok is True iff gate.json exists and parses to a valid
    decision. The failure message is operator-actionable (names Step 4.5 + the
    exact --decision command)."""
    gate = _gate_file(output_dir)
    if not gate.exists():
        return False, _remediation(output_dir)
    try:
        data = json.loads(gate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"gate marker unreadable ({gate}): {exc}\n{_remediation(output_dir)}"
    if not isinstance(data, dict) or data.get("decision") not in DECISIONS:
        return False, (
            f"gate marker invalid ({gate}): decision must be one of {DECISIONS}\n"
            f"{_remediation(output_dir)}"
        )
    if data.get("schema_version") != SCHEMA_VERSION:
        return False, (
            f"gate marker schema_version {data.get('schema_version')!r} != "
            f"{SCHEMA_VERSION!r} ({gate}); regenerate it:\n{_remediation(output_dir)}"
        )
    return True, f"Step 4.5 gate OK (decision={data['decision']})"


def check_deliverable_gate(
    deck_dir: Path, *, deck_required: bool = False
) -> tuple[bool, str]:
    """Check planning_validator + proof gate before producing a deliverable.

    Returns (ok, message). ok=True means the deck may proceed to export.

    When deck_required=True (deck-only scripts like html_packager / svg2pptx),
    an absent planning/ dir is a hard failure — those scripts have no
    legitimate non-deck use, so a missing planning/ means Step 4 was skipped.

    When deck_required=False (default), an absent planning/ dir silently skips
    both checks — for standalone uses like html2svg converting a mermaid diagram
    without a full PPT deck context.
    """
    planning_dir = deck_dir / "planning"
    if not planning_dir.is_dir():
        if deck_required:
            return False, (
                f"no planning/ directory under {deck_dir}; "
                "run Step 4 (planning) before producing deliverables"
            )
        return True, "skipped (no planning/ dir — non-deck context)"

    if not any(planning_dir.glob("*.json")):
        return False, (
            f"no planning JSON in {planning_dir}; "
            "run Step 4 (planning) before producing deliverables"
        )

    refs_dir = SCRIPTS_DIR.parent / "references"
    cmd = [sys.executable, str(SCRIPTS_DIR / "planning_validator.py"), str(planning_dir)]
    if refs_dir.is_dir():
        cmd += ["--refs", str(refs_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "(no output)"
        return False, (
            "planning validation failed — fix Step 4 JSON before producing deliverables:\n"
            + details
        )

    return gate_status(deck_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record or check the Step-4.5 Review/Render decision gate"
    )
    parser.add_argument("output_dir", help="Deck OUTPUT_DIR (contains runtime/proof/)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--decision",
        choices=DECISIONS,
        help="Record the user's Review/Render choice (idempotent-overwrite)",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if no valid decision marker exists (Step-5c precondition)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)

    if args.check:
        ok, message = gate_status(output_dir)
        if ok:
            print(f"proof_gate: {message}")
            return 0
        print(f"proof_gate: {message}", file=sys.stderr)
        return 1

    try:
        gate = record_decision(output_dir, args.decision)
    except ProofGateError as exc:
        print(f"proof_gate: {exc}", file=sys.stderr)
        return 1
    print(f"proof_gate: recorded decision={args.decision} -> {gate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

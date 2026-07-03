#!/usr/bin/env python3
"""test_proof_gate.py -- the Step-4.5 proof-gate marker (writer + checker).

Covers spec proof-gate-enforcement AC1-AC4: record a Review/Render decision to
runtime/proof/gate.json (--decision), the slug-scoped worksheet requirement for
the `review` branch, the --check exit contract + actionable remediation message,
idempotent-overwrite (last decision wins), and deterministic byte-identical
output.

No pytest in this repo; run directly or via smoke_test.py. Exit 0 = pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SCRIPT = str(ROOT / "scripts" / "proof_gate.py")

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  [{'OK' if cond else 'XX'}] {name}")
    if not cond:
        FAILS.append(name)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, *args], capture_output=True, text=True
    )


def gate_path(deck: Path) -> Path:
    return deck / "runtime" / "proof" / "gate.json"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        # --- AC1: render-direct writes marker on an empty deck dir ---
        deck1 = Path(td) / "oss-onboarding"
        deck1.mkdir(parents=True)
        r1 = run(str(deck1), "--decision", "render-direct")
        gp1 = gate_path(deck1)
        check("AC1 render-direct -> exit 0", r1.returncode == 0)
        check("AC1 render-direct -> gate.json created", gp1.exists())
        if gp1.exists():
            data1 = json.loads(gp1.read_text())
            check("AC1 decision == render-direct", data1.get("decision") == "render-direct")
            check("AC1 schema_version present", "schema_version" in data1)

        # --- AC2a: review with no worksheet for this deck -> non-zero ---
        deck2 = Path(td) / "deck-review"
        deck2.mkdir(parents=True)
        r2a = run(str(deck2), "--decision", "review")
        check("AC2a review w/o worksheet -> exit != 0", r2a.returncode != 0)
        check("AC2a review w/o worksheet -> stderr names worksheet, no traceback",
              "intent.html" in r2a.stderr and "Traceback" not in r2a.stderr)
        check("AC2a review w/o worksheet -> no marker written", not gate_path(deck2).exists())

        # --- AC2b: review with the deck's slug-scoped worksheet present -> ok ---
        ws = deck2 / "runtime" / "proof"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / f"{deck2.name}-intent.html").write_text("<html></html>", encoding="utf-8")
        r2b = run(str(deck2), "--decision", "review")
        check("AC2b review w/ worksheet -> exit 0", r2b.returncode == 0)
        check("AC2b review w/ worksheet -> decision == review",
              gate_path(deck2).exists()
              and json.loads(gate_path(deck2).read_text()).get("decision") == "review")

        # --- AC2 slug-scoping: a stale OTHER-slug worksheet does NOT satisfy review ---
        deck2s = Path(td) / "current-deck"
        stale = deck2s / "runtime" / "proof"
        stale.mkdir(parents=True)
        (stale / "old-slug-intent.html").write_text("<html></html>", encoding="utf-8")
        r2s = run(str(deck2s), "--decision", "review")
        check("AC2 slug-scoped: stale other-slug worksheet -> exit != 0", r2s.returncode != 0)

        # --- AC3a: --check with no marker -> non-zero + actionable remediation ---
        deck3 = Path(td) / "deck-nocheck"
        deck3.mkdir(parents=True)
        r3a = run(str(deck3), "--check")
        check("AC3a check w/o marker -> exit != 0", r3a.returncode != 0)
        check("AC3a check w/o marker -> stderr pins proof_gate.py + --decision + Step 4.5",
              all(s in r3a.stderr for s in ("proof_gate.py", "--decision", "Step 4.5"))
              and "Traceback" not in r3a.stderr)

        # --- AC3b: --check after a decision recorded -> exit 0 ---
        r3b = run(str(deck1), "--check")
        check("AC3b check after decision -> exit 0", r3b.returncode == 0)

        # --- AC3c: --check with malformed gate.json -> non-zero ---
        deck3c = Path(td) / "deck-malformed"
        (deck3c / "runtime" / "proof").mkdir(parents=True)
        gate_path(deck3c).write_text("{ not valid json", encoding="utf-8")
        r3c1 = run(str(deck3c), "--check")
        check("AC3c check w/ bad JSON -> exit != 0",
              r3c1.returncode != 0 and "Traceback" not in r3c1.stderr)
        gate_path(deck3c).write_text(json.dumps({"schema_version": "1", "decision": "nope"}),
                                     encoding="utf-8")
        r3c2 = run(str(deck3c), "--check")
        check("AC3c check w/ invalid decision -> exit != 0", r3c2.returncode != 0)
        gate_path(deck3c).write_text(json.dumps({"schema_version": "999", "decision": "review"}),
                                     encoding="utf-8")
        r3c3 = run(str(deck3c), "--check")
        check("AC3c check w/ unknown schema_version -> exit != 0", r3c3.returncode != 0)

        # AC3c OSError branch: gate.json is a directory (unreadable) -> fail, no traceback
        deck3d = Path(td) / "deck-gatedir"
        (deck3d / "runtime" / "proof" / "gate.json").mkdir(parents=True)
        r3d = run(str(deck3d), "--check")
        check("AC3c check w/ gate.json as dir -> exit != 0, no traceback",
              r3d.returncode != 0 and "Traceback" not in r3d.stderr)

        # --- AC4: determinism (byte-identical) + idempotent overwrite ---
        deck4 = Path(td) / "deck-det"
        deck4.mkdir(parents=True)
        run(str(deck4), "--decision", "render-direct")
        first = gate_path(deck4).read_bytes()
        run(str(deck4), "--decision", "render-direct")
        second = gate_path(deck4).read_bytes()
        check("AC4 two render-direct runs -> byte-identical", first == second)
        # re-decision overwrites (last wins). First: review w/o worksheet must fail
        # AND leave the existing render-direct marker untouched.
        r_noop = run(str(deck4), "--decision", "review")
        check("AC4 review w/o worksheet -> fails and keeps prior render-direct",
              r_noop.returncode != 0
              and json.loads(gate_path(deck4).read_text()).get("decision") == "render-direct")
        # give it a worksheet so review can succeed, then confirm overwrite
        wp = deck4 / "runtime" / "proof"
        (wp / f"{deck4.name}-intent.html").write_text("<html></html>", encoding="utf-8")
        run(str(deck4), "--decision", "review")
        check("AC4 re-decision overwrites (last wins)",
              json.loads(gate_path(deck4).read_text()).get("decision") == "review")

    if FAILS:
        print(f"\n{len(FAILS)} failure(s): {FAILS}")
        return 1
    print("\nall proof_gate checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

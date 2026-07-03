#!/usr/bin/env python3
"""test_resolve_output_dir.py — regression tests for resolve_output_dir.py.

Covers slug normalization (case/punctuation/length<=40), atomic claim on a fresh
root, and collision -> next suffix. There is no resume path in the script (resume
stays an agent/prose judgment), so no resume test.
See docs/specs/skill-effectiveness-hardening/. No pytest harness — run directly.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import resolve_output_dir as R  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"ok   - {name}")
    else:
        print(f"FAIL - {name}")
        FAILS.append(name)


# normalize: case + punctuation collapse to single dash, trimmed
check("normalize punctuation/case", R.normalize_slug("Dify Enterprise Intro!") == "dify-enterprise-intro")
check("normalize collapses runs & trims", R.normalize_slug("  AI  安全 // report  ") == "ai-report")
# exact expected value for an over-length input (pins the boundary to a value, not a range)
check("normalize length capped at 40 (exact)",
      R.normalize_slug("a" * 30 + " " + "b" * 30) == "a" * 30 + "-" + "b" * 9)
check("normalize empty for all-punctuation", R.normalize_slug("###") == "")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    # fresh claim creates <slug>
    d1 = R.claim_output_dir(root, "deck")
    check("fresh claim creates <slug>", d1 == (root / "deck").resolve() and d1.is_dir())
    # collision -> <slug>-2
    d2 = R.claim_output_dir(root, "deck")
    check("collision claims <slug>-2", d2 == (root / "deck-2").resolve() and d2.is_dir())
    # third -> <slug>-3
    d3 = R.claim_output_dir(root, "deck")
    check("second collision claims <slug>-3", d3 == (root / "deck-3").resolve())
    # root is auto-created when absent
    nested = root / "does" / "not" / "exist"
    d4 = R.claim_output_dir(nested, "deck")
    check("root auto-created when absent", d4 == (nested / "deck").resolve() and d4.is_dir())

# exhaustion: with MAX_SUFFIX temporarily lowered, all candidates taken -> RuntimeError
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    saved = R.MAX_SUFFIX
    R.MAX_SUFFIX = 2  # candidates = [ex, ex-2]
    try:
        R.claim_output_dir(root, "ex")   # -> ex
        R.claim_output_dir(root, "ex")   # -> ex-2
        raised = False
        try:
            R.claim_output_dir(root, "ex")  # both taken -> raise
        except RuntimeError:
            raised = True
        check("exhaustion raises RuntimeError", raised)
    finally:
        R.MAX_SUFFIX = saved

# main() error path: all-punctuation slug normalizes empty -> exit code 1
with tempfile.TemporaryDirectory() as tmp:
    saved_argv = sys.argv
    sys.argv = ["resolve_output_dir.py", "--root", tmp, "--slug", "###"]
    try:
        rc = R.main()
    finally:
        sys.argv = saved_argv
    check("main() returns 1 on empty-normalized slug", rc == 1)

if FAILS:
    print(f"\n{len(FAILS)} failure(s)")
    raise SystemExit(1)
print("\nall resolve_output_dir tests passed")

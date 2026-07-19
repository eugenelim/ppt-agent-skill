#!/usr/bin/env python3
"""test_check_skill_refs.py — regression tests for the SKILL.md reference-existence guard.

Guards `check_skill.find_broken_skill_refs`: every literal references/…md path in
SKILL.md must resolve, brace forms expand, placeholder/glob forms are skipped, and
a dead concrete path co-located with a `<placeholder>` on the same row is still
caught (the exact drift shape that hid the stale charts/radar.md example).
See docs/specs/skill-effectiveness-hardening/. No pytest harness in this repo —
run directly. Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import check_skill as C  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        if cond:
            print(f"ok   - {name}")
        else:
            print(f"FAIL - {name}")
            FAILS.append(name)


    # (a) a dead literal ref is reported
    missing = C.find_broken_skill_refs("`references/charts/radar.md`", lambda p: False)
    check("(a) dead literal path is reported", missing == ["references/charts/radar.md"])

    # (b) brace form is expanded; only the missing member is reported
    have = {"references/charts/basic.md", "references/charts/advanced.md"}
    missing = C.find_broken_skill_refs(
        "`references/charts/{basic,advanced,complex}.md`", lambda p: p in have
    )
    check("(b) brace expands, only missing member reported", missing == ["references/charts/complex.md"])

    # (b2) multi-group brace cross-product expands fully
    have2 = {"references/a/c.md", "references/a/d.md", "references/b/c.md"}
    missing = C.find_broken_skill_refs("`references/{a,b}/{c,d}.md`", lambda p: p in have2)
    check("(b2) two brace groups expand to full cross-product", missing == ["references/b/d.md"])

    # (b3) the same dead path twice is reported once (dedup)
    missing = C.find_broken_skill_refs("`references/x/y.md` `references/x/y.md`", lambda p: False)
    check("(b3) duplicate dead path is deduplicated", missing == ["references/x/y.md"])

    # (c) placeholder and glob forms are skipped (never reported)
    missing = C.find_broken_skill_refs(
        "`references/layouts/<name>.md` and `references/blocks/*.md`", lambda p: False
    )
    check("(c) <placeholder> and * forms are skipped", missing == [])

    # (d) the real SKILL.md resolves clean against the real tree
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    missing = C.find_broken_skill_refs(skill_text, lambda p: (ROOT / p).exists())
    check("(d) real SKILL.md has no broken references", missing == [], )
    if missing:
        print(f"       broken: {missing}")

    # (e) a dead concrete path co-located with a placeholder on the SAME row is still
    #     caught — pins per-span (not per-line) tokenization.
    row = "| `chart_type` | radar | `references/charts/<name>.md` | 雷达 → `references/charts/radar.md` |"
    missing = C.find_broken_skill_refs(row, lambda p: False)
    check("(e) dead path co-located with <placeholder> on one row is reported",
          missing == ["references/charts/radar.md"])

    if FAILS:
        print(f"\n{len(FAILS)} failure(s)")
        raise SystemExit(1)
    print("\nall reference-guard tests passed")

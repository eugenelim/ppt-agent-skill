#!/usr/bin/env python3
"""test_icon_search.py — search ranking + pipeline-safety validation for the
SVG icon library (scripts/icon_search.py).

No pytest harness in this repo; run directly (`python3 scripts/test_icon_search.py`)
or via smoke_test.py. Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import icon_search as I  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(cond: bool, msg: str) -> None:
        if not cond:
            FAILS.append(msg)


    def validate_one(svg_text: str, *, file_name: str = "x.svg", write_file: bool = True,
                     view_box: str = "0 0 24 24") -> list[str]:
        """Run validate() against a throwaway single-icon library in a tmp dir."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            orig = I.ICONS_DIR
            I.ICONS_DIR = tmp
            try:
                if write_file:
                    (tmp / file_name).write_text(svg_text, encoding="utf-8")
                catalog = {"version": 1, "icons": [{
                    "id": "x", "name": "X", "category": "generic",
                    "tags": ["t"], "keywords": ["k"], "viewBox": view_box, "file": file_name,
                }]}
                return I.validate(catalog)
            finally:
                I.ICONS_DIR = orig


    CLEAN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="1.5"><rect x="3" y="6" width="18" height="12" rx="2"/></svg>')

    # --- search ---
    cat = I.load_catalog()
    check(any(i["id"] == "arrow-right" for i in I.search("direction", cat)),
          "search('direction') should find arrow-right")
    check(any(i["id"] == "arrow-right" for i in I.search("DIRECTION", cat)),
          "search should be case-insensitive")
    check(any(i["id"] == "node" for i in I.search("block", cat)),
          "search('block') should find node via tags")
    check(I.search("zzznotanicon", cat) == [], "search for nonsense returns nothing")

    # ranking: id/name match outranks keyword-only match
    rank_cat = {"icons": [
        {"id": "alpha", "name": "Alpha", "tags": [], "keywords": ["beacon"]},   # keyword-only for 'beacon'
        {"id": "beacon", "name": "Beacon", "tags": [], "keywords": []},          # id match for 'beacon'
    ]}
    ranked = I.search("beacon", rank_cat)
    check(ranked and ranked[0]["id"] == "beacon", "id match must rank above keyword-only match")

    # --- validate: clean committed library ---
    check(I.validate(I.load_catalog()) == [], "committed icon library must validate clean")

    # --- validate: clean tmp icon ---
    check(validate_one(CLEAN) == [], "a clean currentColor monoline SVG must pass")

    # --- validate: each failure mode flagged ---
    check(any("not found" in p for p in validate_one("", write_file=False)),
          "missing SVG file must be flagged")
    check(any("viewBox" in p for p in validate_one(CLEAN.replace(' viewBox="0 0 24 24"', ""))),
          "missing viewBox must be flagged")
    check(any("<text>" in p for p in validate_one(
            '<svg viewBox="0 0 24 24"><text x="0" y="0">hi</text></svg>')),
          "SVG <text> must be flagged")
    check(any("mask-image" in p for p in validate_one(
            '<svg viewBox="0 0 24 24" style="mask-image:url(#m)"><rect/></svg>')),
          "mask-image must be flagged")
    check(any("conic-gradient" in p for p in validate_one(
            '<svg viewBox="0 0 24 24"><rect style="fill:conic-gradient(red,blue)"/></svg>')),
          "conic-gradient must be flagged")
    check(any("background-image" in p for p in validate_one(
            '<svg viewBox="0 0 24 24" style="background-image:url(x.png)"><rect/></svg>')),
          "background-image:url() must be flagged")
    check(any("hardcoded paint" in p for p in validate_one(
            '<svg viewBox="0 0 24 24" fill="none" stroke="#a100ff"><rect/></svg>')),
          "hardcoded hex stroke must be flagged (should bind to currentColor/var)")
    check(validate_one('<svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-1)"><rect/></svg>') == [],
          "var(--…) paint must pass")

    # --- list ---
    ids = {i["id"] for i in I.load_catalog().get("icons", [])}
    check("arrow-right" in ids and "node" in ids, "catalog must list the seed icons")

    # --- report ---
    if FAILS:
        print(f"✗ test_icon_search: {len(FAILS)} failure(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✓ test_icon_search: all checks pass")
    sys.exit(0)

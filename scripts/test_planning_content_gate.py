#!/usr/bin/env python3
"""test_planning_content_gate.py — the Step-4 planning gate must reject skeleton
cards (headline only, no real content) and recognize `items` as content.

No pytest harness in this repo; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import planning_validator as P  # noqa: E402
import smoke_skill as S  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  [{'OK' if cond else 'XX'}] {name}")
    if not cond:
        FAILS.append(name)


def skeleton_errors(result) -> list[str]:
    return [e for e in result.errors if "skeleton" in e]


def find_text_card_index(page: dict) -> int:
    for i, c in enumerate(page["cards"]):
        if c.get("card_type") == "text":
            return i
    raise AssertionError("fixture has no 'text' card — test target missing")


def main() -> int:
    # refs_dir=None isolates the substance rule from resource-ref existence checks.
    page = S.build_content_page_fixture(density_label="medium")["page"]

    base = P.validate_page(page, None)
    check("baseline fixture validates clean (no skeleton false-positive)", base.ok)

    idx = find_text_card_index(page)

    # 1. Strip a text card to a bare headline -> skeleton.
    skel = copy.deepcopy(page)
    c = skel["cards"][idx]
    for k in ("body", "items", "data_points", "chart"):
        c.pop(k, None)
    c["headline"] = "只有标题没有内容"
    r_skel = P.validate_page(skel, None)
    check("headline-only card is flagged as skeleton", bool(skeleton_errors(r_skel)))

    # 2. Content lives ONLY in `items`, with NO headline — proves `items` alone
    #    (not the headline) is what the check now recognizes as content. This is
    #    the exact regression the old check missed (it never inspected `items`).
    with_items = copy.deepcopy(skel)
    ic = with_items["cards"][idx]
    ic.pop("headline", None)
    ic["items"] = ["一条真实内容要点", "第二条要点"]
    r_items = P.validate_page(with_items, None)
    check(
        "items-only card (no headline) is neither skeleton nor empty-payload",
        not skeleton_errors(r_items)
        and not any("empty card payload" in e for e in r_items.errors),
    )

    # 3. Content carried by a needed image -> not a skeleton. Use VALID enum
    #    values so the card is otherwise well-formed (else other errors mask it).
    #    The 'medium' fixture is image_policy=support_only, which permits a
    #    needed inline-illustration (only hero-background is forbidden there).
    with_img = copy.deepcopy(skel)
    with_img["cards"][idx]["image"] = {
        "needed": True,
        "usage": "inline-illustration",
        "placement": "inline",
        "content_description": "示意配图",
        "source_hint": "generate",
    }
    r_img = P.validate_page(with_img, None)
    check("image-driven card is NOT a skeleton", not skeleton_errors(r_img))
    check("image-driven card has no unrelated image-enum errors", r_img.ok)

    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed")
        return 1
    print("all pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

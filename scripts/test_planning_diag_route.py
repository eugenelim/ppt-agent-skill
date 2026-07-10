#!/usr/bin/env python3
"""test_planning_diag_route.py — DIAG-ROUTE-01: planning must route a diagram
recipe for diagram-shaped cards.

The diagram-consistency-system recipes only reach the render agent when planning
tags `card_type: diagram` + a `diagram_type` and routes the matching family file
into `resources.block_refs`. This check (WARN, never ERROR) surfaces the routing
gap that let ad-hoc diagrams ship in the field.

No pytest harness in this repo; run directly or via smoke_test.py.
Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import copy
import re
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


def diag_route_warns(result) -> list[str]:
    return [w for w in result.warnings if "DIAG-ROUTE-01" in w]


def first_card_index(page: dict, card_type: str) -> int:
    for i, c in enumerate(page["cards"]):
        if c.get("card_type") == card_type:
            return i
    return 0


def with_block_refs(page: dict, refs: list[str]) -> dict:
    p = copy.deepcopy(page)
    p.setdefault("resources", {})["block_refs"] = list(refs)
    return p


def main() -> int:
    base_page = S.build_content_page_fixture(density_label="medium")["page"]

    # refs_dir=None isolates the routing rule from resource-ref existence checks.
    base = P.validate_page(with_block_refs(base_page, []), None)
    check("baseline fixture has no DIAG-ROUTE-01 false-positive", not diag_route_warns(base))

    # 1. card_type=diagram, no diagram_type -> WARN.
    p1 = with_block_refs(base_page, [])
    idx = first_card_index(p1, "list") or 0
    c = p1["cards"][idx]
    c["card_type"] = "diagram"
    c.pop("diagram_type", None)
    r1 = P.validate_page(p1, None)
    check("diagram card without diagram_type -> DIAG-ROUTE-01 WARN", bool(diag_route_warns(r1)))

    # 2. diagram_type set, family file NOT routed in block_refs -> WARN.
    p2 = with_block_refs(base_page, [])
    c = p2["cards"][idx]
    c["card_type"] = "diagram"
    c["diagram_type"] = "architecture-component"  # -> diagram-architecture family
    r2 = P.validate_page(p2, None)
    check("diagram card w/ diagram_type but unrouted family -> DIAG-ROUTE-01 WARN", bool(diag_route_warns(r2)))

    # 3. diagram_type set AND matching family routed -> no WARN.
    fam = P.DIAGRAM_FAMILY_BY_TYPE["architecture-component"]
    p3 = with_block_refs(base_page, [fam])
    c = p3["cards"][idx]
    c["card_type"] = "diagram"
    c["diagram_type"] = "architecture-component"
    r3 = P.validate_page(p3, None)
    check("diagram card correctly tagged + routed -> no DIAG-ROUTE-01", not diag_route_warns(r3))

    # 4. list card whose headline is diagram-shaped, no diagram family -> WARN.
    p4 = with_block_refs(base_page, [])
    c = p4["cards"][idx]
    c["card_type"] = "list"
    c["headline"] = "Interview-to-retrieval pipeline"
    r4 = P.validate_page(p4, None)
    check("diagram-shaped list card without routed recipe -> DIAG-ROUTE-01 WARN", bool(diag_route_warns(r4)))

    # 5. plain text card -> no WARN (no false positive).
    p5 = with_block_refs(base_page, [])
    c = p5["cards"][idx]
    c["card_type"] = "text"
    c["headline"] = "Key recommendations"
    c["body"] = ["We recommend proceeding with the pilot in Q3."]
    r5 = P.validate_page(p5, None)
    check("plain text card -> no DIAG-ROUTE-01 false positive", not diag_route_warns(r5))

    # 6. lockstep: the validator map matches the blocks/diagram.md selector table.
    diagram_md = (ROOT / "references" / "blocks" / "diagram.md").read_text(encoding="utf-8")
    # selector rows look like: `| `type-a` `type-b` ... | ... | `diagram-family` |`
    md_pairs: dict[str, str] = {}
    for line in diagram_md.splitlines():
        if not line.strip().startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 3:
            continue
        family = cols[-1].strip("` ")
        if not family.startswith("diagram-"):
            continue
        types = re.findall(r"`([a-z0-9-]+)`", cols[0])
        for t in types:
            md_pairs[t] = family
    # guard against a vacuous pass if the table format ever changes so the regex
    # extracts nothing.
    check(f"selector parse is non-empty (got {len(md_pairs)} types)", len(md_pairs) >= 20)
    # the validator constant and the selector must be identical BOTH ways: a type
    # dropped from diagram.md must not leave a stale entry in the constant, and vice
    # versa. (single source of truth = blocks/diagram.md)
    md_wrong = {t: (md_pairs[t], P.DIAGRAM_FAMILY_BY_TYPE.get(t))
                for t in md_pairs if P.DIAGRAM_FAMILY_BY_TYPE.get(t) != md_pairs[t]}
    only_in_constant = set(P.DIAGRAM_FAMILY_BY_TYPE) - set(md_pairs)
    only_in_md = set(md_pairs) - set(P.DIAGRAM_FAMILY_BY_TYPE)
    check(f"validator map == blocks/diagram.md selector both ways "
          f"(wrong={md_wrong}, constant-only={only_in_constant}, md-only={only_in_md})",
          not md_wrong and not only_in_constant and not only_in_md)
    # every family file the constant references exists on disk.
    missing = [f for f in set(P.DIAGRAM_FAMILY_BY_TYPE.values())
               if not (ROOT / "references" / "blocks" / f"{f}.md").exists()]
    check(f"every routed diagram family file exists (missing={missing})", not missing)

    # 7. the routing check is WARN-only — never emits errors (guards a future
    #    .fail()/.error() from creeping in and changing the planning gate's exit).
    r = P.ValidationResult()
    P.validate_diagram_routing(
        {"resources": {"block_refs": []}},
        [{"card_id": "c1", "card_type": "diagram"},
         {"card_id": "c2", "card_type": "list", "headline": "System architecture"}],
        "slide 1", r,
    )
    check("validate_diagram_routing emits only WARN, never ERROR",
          r.errors == [] and len(r.warnings) >= 2)

    if FAILS:
        print(f"\nFAILED: {len(FAILS)} check(s): {FAILS}")
        return 1
    print("\nAll DIAG-ROUTE-01 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

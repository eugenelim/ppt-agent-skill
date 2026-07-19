#!/usr/bin/env python3
"""test_reference_page_types.py — regression tests for the reference-runbook page types.

Guards the `section-marker` (inline divider) and `reference` (back-matter) page
types across both Python validators (planning_validator + contract_validator).
See docs/specs/reference-runbook-page-types/. No pytest harness in this repo —
run directly or via smoke_test. Exit 0 = all pass, 1 = a failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import planning_validator as P  # noqa: E402
import contract_validator as C  # noqa: E402


if __name__ == "__main__":
    FAILS: list[str] = []


    def check(name: str, cond: bool) -> None:
        if cond:
            print(f"  ok  {name}")
        else:
            print(f"FAIL  {name}")
            FAILS.append(name)


    def make_page(page_type: str, narrative_role: str) -> dict:
        """A complete, warning-clean non-content page so structural rules don't mask
        the page_type/narrative_role checks (density matches DENSITY_DEFAULTS[mid_low])."""
        return {
            "slide_number": 5,
            "page_type": page_type,
            "narrative_role": narrative_role,
            "title": "T",
            "page_goal": "goal",
            "visual_weight": 3,
            "density_label": "mid_low",
            "density_reason": "reference page keeps a restrained density",
            "density_contract": {
                "deck_bias": "balanced",
                "page_lower_bound": "low",
                "page_upper_bound": "medium",
                "max_cards": 3,
                "max_charts": 1,
                "min_body_font_px": 20,
                "max_lines_per_card": 4,
                "image_policy": "flexible",
                "decoration_budget": "medium",
                "overflow_strategy": "rebalance_layout",
            },
            "director_command": {"mood": "reference"},
            "decoration_hints": {"background": {}},
            "resources": {
                "page_template": None,
                "layout_refs": [],
                "block_refs": [],
                "chart_refs": [],
                "principle_refs": [],
            },
            "cards": [
                {
                    "card_id": "s5-anchor-1",
                    "role": "anchor",
                    "card_type": "list",
                    "card_style": "transparent",
                    "headline": "H",
                    "body": ["b"],
                    "content_budget": {"body_max_lines": 3},
                    "image": {
                        "needed": False,
                        "usage": None,
                        "placement": None,
                        "content_description": None,
                        "source_hint": None,
                    },
                }
            ],
        }


    def errors_for(page: dict) -> list[str]:
        return P.validate_page(page, None).errors


    def warnings_for(page: dict) -> list[str]:
        return P.validate_page(page, None).warnings


    def test_planning_validator() -> None:
        for pt in ("section-marker", "reference"):
            errs = errors_for(make_page(pt, pt))
            check(
                f"planning_validator accepts page_type={pt!r} (no 'invalid page_type')",
                not any("invalid page_type" in e for e in errs),
            )
            warns = warnings_for(make_page(pt, pt))
            check(
                f"planning_validator accepts narrative_role={pt!r} (no 'unknown narrative_role')",
                not any("unknown narrative_role" in w for w in warns),
            )

        # Negative: an unknown value must still be rejected — the enum did not widen
        # to "anything goes".
        errs = errors_for(make_page("bogus", "cover"))
        check(
            "planning_validator still rejects page_type='bogus' ('invalid page_type')",
            any("invalid page_type" in e for e in errs),
        )

        # Negative: near-miss spellings of the new hyphenated values must still be
        # rejected — pins the exact hyphenated contract so an accidental underscore
        # or plural variant can't slip into the enum unnoticed.
        for near_miss in ("section_marker", "references"):
            errs = errors_for(make_page(near_miss, "cover"))
            check(
                f"planning_validator still rejects near-miss page_type={near_miss!r}",
                any("invalid page_type" in e for e in errs),
            )


    def _validate_html(body: str, page_type: str):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "slide.html"
            path.write_text(body, encoding="utf-8")
            return C.validate_html(path, page_type)


    CHROME = (
        '<header class="slide-header">masthead</header>'
        "<main>body</main>"
        '<footer class="slide-footer">footer</footer>'
    )
    NO_CHROME = "<main>body</main>"


    def test_contract_validator() -> None:
        for pt in ("section-marker", "reference"):
            result, _ = _validate_html(CHROME, pt)
            check(
                f"contract_validator.validate_html: no 'unrecognized page_type' for {pt!r}",
                not any("unrecognized page_type" in w for w in result.warnings),
            )
            check(
                f"contract_validator.validate_html: chrome-bearing {pt!r} page passes",
                not result.errors,
            )
            # Proves the type joined the chrome-required branch (not the cover/end
            # no-chrome branch): omit the header and the requirement must fire.
            result_bare, _ = _validate_html(NO_CHROME, pt)
            check(
                f"contract_validator.validate_html: {pt!r} without chrome errors on header/footer",
                any("slide-header" in e for e in result_bare.errors),
            )


    def main() -> int:
        test_planning_validator()
        test_contract_validator()
        if FAILS:
            print(f"\n{len(FAILS)} failure(s): {FAILS}")
            return 1
        print("\nall reference-runbook page-type checks passed")
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())

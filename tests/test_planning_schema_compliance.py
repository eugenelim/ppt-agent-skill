#!/usr/bin/env python3
"""Regression harness for planning.json schema compliance.

The validator (`scripts/planning_validator.py`) is the single source of truth
for what "compliant" means. This harness locks three things in place so the
Step 4 planning playbook stays aligned with it:

1. **Failure surface** — one triggering fixture per validator ERROR *class*,
   asserting the validator actually fires (AC1). A coverage tripwire asserts we
   enumerated exactly as many sites as the validator has `result.error(` calls,
   so adding an unguarded error to the validator fails this suite.
2. **Golden compliance** — a multi-page deck (cover + content + dashboard +
   reference) that validates with zero ERRORs (AC2).
3. **Skill awareness** — every ERROR class maps to an anchor string that must
   be present in the planning playbook (AC3). Deleting the guidance fails here.

Run: `pytest tests/test_planning_schema_compliance.py -q`
or standalone: `python3 tests/test_planning_schema_compliance.py`
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
REFS = REPO_ROOT / "references"
PLAYBOOK = REFS / "playbooks" / "step4" / "page-planning-playbook.md"
PROMPT = REFS / "prompts" / "step4" / "tpl-page-planning.md"
VALIDATOR_SRC = SCRIPTS / "planning_validator.py"

sys.path.insert(0, str(SCRIPTS))

import planning_validator as pv  # noqa: E402
from planning_validator import (  # noqa: E402
    validate_cross_page,
    validate_page,
)


# --------------------------------------------------------------------------
# Fixture builders — start from a known-valid page, mutate one thing per class.
# --------------------------------------------------------------------------

def _card(card_id: str, role: str = "support", style: str = "outline", **over):
    card = {
        "card_id": card_id,
        "role": role,
        "card_type": "text",
        "card_style": style,
        "argument_role": "evidence",
        "headline": "H",
        "body": ["a body sentence"],
        "data_points": [],
        "chart": None,
        "content_budget": {"body_max_lines": 3},
        "image": {
            "needed": False,
            "usage": None,
            "placement": None,
            "content_description": None,
            "source_hint": None,
        },
    }
    card.update(over)
    return card


def base_content_page(**over):
    """A valid medium-density content page (validates with zero ERRORs)."""
    page = {
        "slide_number": 3,
        "page_type": "content",
        "narrative_role": "evidence",
        "narrative_archetype": "persuasive",
        "title": "T",
        "page_goal": "one clear point",
        "audience_takeaway": "x",
        "visual_weight": 5,
        "density_label": "medium",
        "density_reason": "four related metrics on one page",
        "density_contract": {
            "deck_bias": "balanced",
            "page_lower_bound": "mid_low",
            "page_upper_bound": "high",
            "max_cards": 4,
            "max_charts": 2,
            "min_body_font_px": 18,
            "max_lines_per_card": 5,
            "image_policy": "support_only",
            "decoration_budget": "medium",
            "overflow_strategy": "tighten_budget",
        },
        "layout_hint": "mixed-grid",
        "director_command": {"mood": "m"},
        "decoration_hints": {"background": {}},
        "source_guidance": {"strictness": "s"},
        "resources": {
            "page_template": None,
            "layout_refs": ["mixed-grid"],
            "block_refs": [],
            "chart_refs": ["basic"],
            "principle_refs": ["visual-hierarchy"],
        },
        "cards": [
            _card("s3-anchor-1", role="anchor", style="elevated"),
            _card("s3-support-1", role="support", style="outline",
                  card_type="data", data_points=[{"label": "x", "value": "1"}]),
        ],
        "workflow_metadata": {"stage": "planning"},
    }
    page.update(over)
    return page


def dashboard_page(slide_number=4, deck_bias="balanced", **over):
    page = base_content_page(
        slide_number=slide_number,
        density_label="dashboard",
        density_reason="dense operational dashboard layout",
        visual_weight=8,
    )
    page["density_contract"] = {
        "deck_bias": deck_bias,
        "page_lower_bound": "high",
        "page_upper_bound": "dashboard",
        "max_cards": 8,
        "max_charts": 4,
        "min_body_font_px": 14,
        "max_lines_per_card": 3,
        "image_policy": "decorate_only",
        "decoration_budget": "minimal",
        "overflow_strategy": "rollback_planning",
    }
    page["layout_hint"] = "mixed-grid"
    page.update(over)
    return page


def _mini(slide_number, density_label, page_type="content",
          archetype="persuasive"):
    """Minimal page for cross-page checks (only cross-page fields matter)."""
    return {
        "slide_number": slide_number,
        "page_type": page_type,
        "layout_hint": "mixed-grid",
        "density_label": density_label,
        "narrative_archetype": archetype,
    }


# --------------------------------------------------------------------------
# The error-class table. Each entry proves one validator ERROR class fires and
# is documented. `scope` selects validate_page vs validate_cross_page.
# --------------------------------------------------------------------------

def _del(page, key):
    p = copy.deepcopy(page)
    p.pop(key, None)
    return p


def _set(page, key, value):
    p = copy.deepcopy(page)
    p[key] = value
    return p


def _card_only(**over):
    """A content page whose single card is mutated to the given override."""
    p = base_content_page()
    card = _card("s3-anchor-1", role="anchor", style="elevated")
    card.update(over)
    p["cards"] = [card]
    return p


# id, category, scope, builder, expected error substring, [doc anchors]
ERROR_CLASSES: list[tuple] = [
    # --- category 4: content sufficiency / structural card fields ---
    ("card_missing_id", 1, "page",
     lambda: _card_only(card_id=""), "missing card_id", ["card_id"]),
    ("card_bad_role", 2, "page",
     lambda: _card_only(role="boss"), "invalid role", ["`anchor` / `support` / `context`"]),
    ("card_bad_type", 2, "page",
     lambda: _card_only(card_type="bogus"), "invalid card_type", ["matrix_chart"]),
    ("card_bad_style", 2, "page",
     lambda: _card_only(card_style="neon"), "invalid card_style", ["elevated"]),
    ("skeleton_card", 4, "page",
     lambda: _card_only(body=[], data_points=[], headline="only headline"),
     "skeleton card", ["skeleton", "必须是数组"]),
    ("empty_card", 4, "page",
     lambda: _card_only(body=[], data_points=[], headline=""),
     "empty card payload", ["skeleton"]),
    ("bad_chart_type", 2, "page",
     lambda: _card_only(chart={"chart_type": "pie"}), "invalid chart_type",
     ["treemap", "waffle"]),
    ("missing_content_budget", 1, "page",
     lambda: _del_card_key("content_budget"),
     "missing content_budget", ["content_budget"]),
    ("body_lines_exceed", 5, "page",
     lambda: _card_only(content_budget={"body_max_lines": 99}),
     "exceeds density_contract.max_lines_per_card", ["body_max_lines"]),
    ("missing_image", 1, "page",
     lambda: _del_card_key("image"), "missing image contract", ["image"]),
    ("image_needed_empty", 8, "page",
     lambda: _card_only(image={"needed": True, "usage": "", "placement": "",
                               "content_description": "", "source_hint": ""}),
     "image.needed=true but", ["content_description"]),
    ("image_bad_usage", 2, "page",
     lambda: _card_only(image={"needed": True, "usage": "photo",
                               "placement": "inline",
                               "content_description": "d", "source_hint": "s"}),
     "invalid image.usage", ["inline-illustration", "icon-accent"]),
    ("image_bad_placement", 2, "page",
     lambda: _card_only(image={"needed": True, "usage": "inline-illustration",
                               "placement": "middle",
                               "content_description": "d", "source_hint": "s"}),
     "invalid image.placement", ["full-bleed"]),
    ("support_only_hero_bg", 8, "page",
     lambda: _card_only(image={"needed": True, "usage": "hero-background",
                               "placement": "full-bleed",
                               "content_description": "d", "source_hint": "s"}),
     "forbids hero-background", ["support_only"]),
    ("support_only_image_hero", 8, "page",
     lambda: _card_only(card_type="image_hero"),
     "forbids image_hero", ["support_only"]),
    ("decorate_only_needed", 8, "page",
     lambda: _set_dashboard_card(image={"needed": True, "usage": "icon-accent",
                                        "placement": "inline",
                                        "content_description": "d",
                                        "source_hint": "s"}),
     "decorate_only forbids image.needed=true", ["decorate_only"]),
    ("decorate_only_image_hero", 8, "page",
     lambda: _set_dashboard_card(card_type="image_hero"),
     "decorate_only forbids image_hero", ["decorate_only"]),
    ("resource_ref_missing", 7, "page",
     lambda: _card_only(resource_ref={"block": "does-not-exist"}),
     "resource_ref.block not found", ["stem"]),

    # --- category 5: density contract ---
    ("bad_density_label", 2, "page",
     lambda: _set(base_content_page(), "density_label", "huge"),
     "invalid density_label", ["`low` / `mid_low` / `medium` / `high` / `dashboard`"]),
    ("missing_density_reason", 1, "page",
     lambda: _set(base_content_page(), "density_reason", ""),
     "missing meaningful density_reason", ["density_reason"]),
    ("missing_density_contract", 1, "page",
     lambda: _del(base_content_page(), "density_contract"),
     "missing density_contract", ["density_contract"]),
    ("bad_deck_bias", 2, "page",
     lambda: _dc(deck_bias="wild"), "deck_bias must be one of", ["deck_bias"]),
    ("bad_lower_bound", 2, "page",
     lambda: _dc(page_lower_bound="xxx"), "page_lower_bound is invalid",
     ["page_lower_bound"]),
    ("bad_upper_bound", 2, "page",
     lambda: _dc(page_upper_bound="xxx"), "page_upper_bound is invalid",
     ["page_upper_bound"]),
    ("lower_gt_upper", 5, "page",
     lambda: _dc(page_lower_bound="high", page_upper_bound="low"),
     "cannot be greater than", ["page_lower_bound"]),
    ("label_outside_bounds", 5, "page",
     lambda: _dc(page_lower_bound="high", page_upper_bound="dashboard"),
     "must stay within density_contract page bounds", ["page_lower_bound"]),
    ("bad_numeric_field", 3, "page",
     lambda: _dc(max_cards=0), "must be a positive integer", ["max_cards"]),
    ("bad_image_policy", 2, "page",
     lambda: _dc(image_policy="any"), "image_policy must be one of",
     ["flexible", "support_only", "decorate_only"]),
    ("bad_decoration_budget", 2, "page",
     lambda: _dc(decoration_budget="lots"), "decoration_budget must be one of",
     ["generous"]),
    ("bad_overflow_strategy", 2, "page",
     lambda: _dc(overflow_strategy="panic"), "overflow_strategy must be one of",
     ["rebalance_layout"]),
    ("pagetype_no_dashboard", 5, "page",
     lambda: _section_dashboard(), "cannot use density_label 'dashboard'",
     ["dashboard"]),
    ("dashboard_only_content", 5, "page",
     lambda: _toc_dashboard(), "dashboard density_label is only allowed on content",
     ["dashboard"]),
    ("dashboard_bad_layout", 5, "page",
     lambda: _set(dashboard_page(slide_number=3), "layout_hint", "single-focus"),
     "must use layout_hint 'mixed-grid' or 't-shape'", ["mixed-grid", "t-shape"]),
    ("dashboard_bad_image_policy", 5, "page",
     lambda: _dashboard_dc(image_policy="support_only"),
     "must use image_policy=decorate_only", ["decorate_only"]),
    ("relaxed_forbids_dashboard", 5, "page",
     lambda: dashboard_page(slide_number=3, deck_bias="relaxed"),
     "relaxed deck_bias forbids dashboard", ["relaxed"]),
    ("balanced_below_mid_low", 5, "page",
     lambda: _low_balanced(), "balanced deck_bias content pages cannot be below mid_low",
     ["deck_bias"]),
    ("ultra_dense_below_medium", 5, "page",
     lambda: _midlow_ultra(), "ultra_dense deck_bias content pages cannot be below medium",
     ["deck_bias"]),

    # --- category 1/2/3: page-level required fields, enums, types ---
    ("missing_required_field", 1, "page",
     lambda: _del(base_content_page(), "title"), "missing required field 'title'",
     ["title"]),
    ("slide_number_not_int", 3, "page",
     lambda: _set(base_content_page(), "slide_number", "3"),
     "slide_number must be an integer", ["整数"]),
    ("bad_page_type", 2, "page",
     lambda: _set(base_content_page(), "page_type", "splash"), "invalid page_type",
     ["section-marker"]),
    ("bad_archetype", 2, "page",
     lambda: _set(base_content_page(), "narrative_archetype", "story"),
     "invalid narrative_archetype", ["persuasive", "reference_runbook"]),
    ("visual_weight_range", 3, "page",
     lambda: _set(base_content_page(), "visual_weight", 10),
     "visual_weight must be an integer in [1, 9]", ["1..9"]),
    ("content_needs_layout", 1, "page",
     lambda: _del(base_content_page(), "layout_hint"), "content page requires layout_hint",
     ["layout_hint"]),
    ("cards_empty", 4, "page",
     lambda: _set(base_content_page(), "cards", []), "cards[] is empty", ["cards"]),
    ("cards_exceed_max", 5, "page",
     lambda: _many_cards(), "exceeds density_contract.max_cards", ["max_cards"]),
    ("charts_exceed_max", 5, "page",
     lambda: _many_charts(), "exceeds density_contract.max_charts", ["max_charts"]),
    ("missing_anchor", 6, "page",
     lambda: _no_anchor(), "missing anchor card", ["恰好 1 张"]),
    ("multiple_anchor", 6, "page",
     lambda: _two_anchors(), "multiple anchor cards", ["恰好 1 张"]),
    ("needs_two_styles", 6, "page",
     lambda: _same_styles(), "needs at least 2 card styles",
     ["2 种不同的 `card_style`"]),
    ("missing_director_command", 1, "page",
     lambda: _del(base_content_page(), "director_command"), "missing director_command",
     ["director_command"]),
    ("missing_decoration_hints", 1, "page",
     lambda: _del(base_content_page(), "decoration_hints"), "missing decoration_hints",
     ["decoration_hints"]),
    ("content_missing_source_guidance", 1, "page",
     lambda: _del(base_content_page(), "source_guidance"), "missing source_guidance",
     ["source_guidance"]),
    ("missing_resources", 1, "page",
     lambda: _del(base_content_page(), "resources"), "missing resources", ["resources"]),
    ("page_template_missing", 7, "page",
     lambda: _res(page_template="nope"), "resources.page_template not found", ["stem"]),
    ("block_ref_missing", 7, "page",
     lambda: _res(block_refs=["nope"]), "resources.block_refs not found", ["stem"]),

    # --- category 9: cross-page ---
    ("duplicate_slide_number", 9, "cross",
     lambda: [_mini(1, "medium"), _mini(1, "medium")], "duplicate slide_number",
     # per-page agents can't see siblings; the actionable guidance is "this
     # artifact belongs to page N" in the injected prompt (ASI03 scope gate).
     ["归属第"]),
    ("three_consecutive_high", 9, "cross",
     lambda: [_mini(1, "high"), _mini(2, "high"), _mini(3, "high")],
     "3 consecutive slides", ["连续 3 页"]),
    ("dashboard_no_transition", 9, "cross",
     lambda: [_mini(1, "dashboard"), _mini(2, "medium")],
     "过渡", ["过渡"]),
]


# --- builders that need more than a single override -----------------------

def _del_card_key(key):
    p = _card_only()
    p["cards"][0].pop(key, None)
    return p


def _set_dashboard_card(**over):
    p = dashboard_page(slide_number=3)
    card = _card("s3-anchor-1", role="anchor", style="elevated")
    card.update(over)
    p["cards"] = [card]
    return p


def _dc(**over):
    p = base_content_page()
    p["density_contract"].update(over)
    return p


def _dashboard_dc(**over):
    p = dashboard_page(slide_number=3)
    p["density_contract"].update(over)
    return p


def _section_dashboard():
    p = base_content_page()
    p["page_type"] = "section"
    p["density_label"] = "dashboard"
    return p


def _toc_dashboard():
    p = base_content_page()
    p["page_type"] = "toc"
    p["density_label"] = "dashboard"
    return p


def _low_balanced():
    p = base_content_page()
    p["density_label"] = "low"
    p["density_reason"] = "sparse page"
    p["density_contract"].update(page_lower_bound="low", max_cards=2, max_charts=1,
                                 min_body_font_px=24, max_lines_per_card=3,
                                 image_policy="flexible", decoration_budget="generous",
                                 overflow_strategy="rebalance_layout")
    return p


def _midlow_ultra():
    p = base_content_page()
    p["density_label"] = "mid_low"
    p["density_reason"] = "moderate page"
    p["density_contract"].update(deck_bias="ultra_dense", page_lower_bound="mid_low",
                                 max_cards=3, max_charts=1, min_body_font_px=20,
                                 max_lines_per_card=4, image_policy="flexible",
                                 decoration_budget="medium",
                                 overflow_strategy="rebalance_layout")
    return p


def _many_cards():
    p = base_content_page()
    p["cards"] = [_card("s3-anchor-1", role="anchor", style="elevated")] + [
        _card(f"s3-support-{i}", role="support",
              style="outline" if i % 2 else "filled") for i in range(1, 6)
    ]
    return p


def _many_charts():
    p = base_content_page()
    p["cards"] = [
        _card("s3-anchor-1", role="anchor", style="elevated",
              chart={"chart_type": "kpi"}),
        _card("s3-support-1", role="support", style="outline",
              chart={"chart_type": "ring"}),
        _card("s3-support-2", role="context", style="filled",
              chart={"chart_type": "funnel"}),
    ]
    return p


def _no_anchor():
    p = base_content_page()
    p["cards"] = [
        _card("s3-support-1", role="support", style="elevated"),
        _card("s3-support-2", role="support", style="outline"),
    ]
    return p


def _two_anchors():
    p = base_content_page()
    p["cards"] = [
        _card("s3-anchor-1", role="anchor", style="elevated"),
        _card("s3-anchor-2", role="anchor", style="outline"),
    ]
    return p


def _same_styles():
    p = base_content_page()
    p["cards"] = [
        _card("s3-anchor-1", role="anchor", style="elevated"),
        _card("s3-support-1", role="support", style="elevated"),
    ]
    return p


def _res(**over):
    p = base_content_page()
    p["resources"].update(over)
    return p


# --------------------------------------------------------------------------
# Golden deck — must validate with ZERO errors (AC2).
# --------------------------------------------------------------------------

def golden_deck() -> list[dict]:
    cover = base_content_page(
        slide_number=1, page_type="cover", narrative_role="cover",
        density_label="low", density_reason="calm opening cover", visual_weight=2,
    )
    cover.pop("layout_hint")
    cover.pop("source_guidance")
    cover["density_contract"].update(
        page_lower_bound="low", page_upper_bound="mid_low", max_cards=2,
        max_charts=1, min_body_font_px=24, max_lines_per_card=3,
        image_policy="flexible", decoration_budget="generous",
        overflow_strategy="rebalance_layout")
    cover["cards"] = [_card("s1-anchor-1", role="anchor", style="transparent")]

    content = base_content_page(slide_number=2)
    dash = dashboard_page(slide_number=3)
    high = base_content_page(
        slide_number=4, density_label="high", density_reason="dense evidence page",
        visual_weight=7)
    high["density_contract"].update(
        page_lower_bound="medium", page_upper_bound="dashboard", max_cards=6,
        max_charts=2, min_body_font_px=16, max_lines_per_card=4,
        image_policy="support_only", decoration_budget="low",
        overflow_strategy="table_or_microchart")

    ref = base_content_page(
        slide_number=5, page_type="reference", narrative_role="reference",
        narrative_archetype="reference_runbook", density_label="low",
        density_reason="back-matter reference artifact", visual_weight=3)
    ref.pop("layout_hint")
    ref.pop("source_guidance")
    ref["density_contract"].update(
        page_lower_bound="low", page_upper_bound="mid_low", max_cards=2,
        max_charts=1, min_body_font_px=24, max_lines_per_card=3,
        image_policy="flexible", decoration_budget="generous",
        overflow_strategy="rebalance_layout")
    ref["cards"] = [_card("s5-anchor-1", role="anchor", style="filled")]
    return [cover, content, dash, high, ref]


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

# "The skill's awareness" = the playbook the planning subagent reads PLUS the
# prompt template that injects it (tpl-page-planning.md carries the per-page
# slide_number / scope-gate contract). AC3 anchors are searched across both.
PLAYBOOK_TEXT = PLAYBOOK.read_text(encoding="utf-8") + PROMPT.read_text(encoding="utf-8")


@pytest.mark.parametrize("entry", ERROR_CLASSES, ids=[e[0] for e in ERROR_CLASSES])
def test_error_class_fires(entry):
    """Each documented ERROR class actually makes the validator fire (AC1)."""
    _id, _cat, scope, build, expected, _docs = entry
    built = build()
    if scope == "page":
        result = validate_page(built, REFS)
        errors = result.errors
    else:
        result = validate_cross_page(built)
        errors = result.errors
    assert any(expected in e for e in errors), (
        f"[{_id}] expected an error containing {expected!r}; got: {errors}")


@pytest.mark.parametrize("entry", ERROR_CLASSES, ids=[e[0] for e in ERROR_CLASSES])
def test_error_class_documented(entry):
    """Every ERROR class is anchored in the planning playbook (AC3)."""
    _id, _cat, _scope, _build, _expected, docs = entry
    missing = [d for d in docs if d not in PLAYBOOK_TEXT]
    assert not missing, f"[{_id}] playbook is missing anchor(s): {missing}"


def test_golden_deck_zero_errors():
    """A representative valid deck validates with zero ERRORs (AC2)."""
    pages = golden_deck()
    errors: list[str] = []
    for page in pages:
        errors += validate_page(page, REFS).errors
    errors += validate_cross_page(pages).errors
    assert errors == [], f"golden deck should be ERROR-free; got: {errors}"


def test_error_site_coverage_tripwire():
    """We enumerated exactly as many ERROR classes as the validator has sites.

    Guards the failure surface: adding a `result.error(` to the validator
    without a matching fixture here fails this test (AC1 completeness).
    """
    src = VALIDATOR_SRC.read_text(encoding="utf-8")
    site_count = len(re.findall(r"result\.error\(", src))
    assert len(ERROR_CLASSES) == site_count, (
        f"validator has {site_count} result.error() sites but the harness "
        f"enumerates {len(ERROR_CLASSES)} classes — add/remove a fixture to match.")


def test_every_error_site_is_exercised():
    """Bijective coverage: every distinct validator ERROR site fires (AC1).

    Stronger than the count tripwire — monkeypatches ValidationResult.error to
    record which validator *source line* emits, runs every fixture, and asserts
    the number of distinct emitting sites equals the number of `result.error(`
    calls. This catches the collision the count tripwire can't: two fixtures
    landing on one site while another site is left unguarded.
    """
    import inspect

    src = VALIDATOR_SRC.read_text(encoding="utf-8")
    site_count = len(re.findall(r"result\.error\(", src))
    fired: set[int] = set()
    original = pv.ValidationResult.error

    def traced(self, message):
        caller = inspect.currentframe().f_back
        if caller.f_code.co_filename == pv.__file__:
            fired.add(caller.f_lineno)
        return original(self, message)

    pv.ValidationResult.error = traced
    try:
        for _id, _cat, scope, build, _expected, _docs in ERROR_CLASSES:
            built = build()
            if scope == "page":
                validate_page(built, REFS)
            else:
                validate_cross_page(built)
    finally:
        pv.ValidationResult.error = original

    assert len(fired) == site_count, (
        f"suite exercised {len(fired)} distinct validator error sites but the "
        f"validator has {site_count}; at least one site has no triggering "
        f"fixture. fired lines: {sorted(fired)}")


def test_all_nine_categories_present():
    """Every invariant category from the spec is exercised."""
    cats = {e[1] for e in ERROR_CLASSES}
    assert cats == set(range(1, 10)), f"missing categories: {set(range(1, 10)) - cats}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

#!/usr/bin/env python3
"""Deterministically assemble a schema-valid planning.json from a minimal payload.

Motivation
----------
The Step 4 planning subagent used to hand-author the full planning JSON, which
exposes it to all 55 per-page `planning_validator.py` ERROR sites (of 58 total;
the other 3 are cross-page and out of a per-page agent's scope) — most of them
mechanical boilerplate (the 9-field density_contract, workflow_metadata, the
per-card image contract, content_budget, card_ids). That boilerplate is the
"structured output" a hand-writing model reliably gets wrong.

This assembler moves the structure OUT of the LLM. The model supplies only the
*judgment* fields it is actually good at (layout choice, body prose, density
label, chart/image intent); the assembler fills everything mechanical from the
validator's own constants. Whole error categories become impossible by
construction:

- structural presence  — density_contract / workflow_metadata / image contract /
  content_budget / director_command / decoration_hints / source_guidance /
  card_id are always emitted.
- types                — `body` is coerced to list[str]; slide_number to int.
- budget/density       — density_contract is copied from DENSITY_DEFAULTS by
  label; body_max_lines is auto-capped to max_lines_per_card.
- resource resolvability — refs that don't resolve on disk are dropped (reported).
- image coherence      — needed=false pages get a fully-null image object;
  needed=true gets the 4 required fields.

Anything the assembler *cannot* safely infer is a genuine judgment error and is
raised as `AssemblyError` immediately, naming the exact field — instead of
surfacing as one of 100+ opaque validator lines after the fact. The assembler
imports every enum/budget from `planning_validator`, so it can never drift from
the oracle, and it self-validates the assembled page before returning:
**an AssemblyError-free payload can never yield a per-page validator ERROR.**
Cross-page ERRORs (duplicate slide_number, 3-consecutive-high, dashboard
neighbours) are deck-level and NOT checked here — a per-page agent can't see its
siblings; those stay the outline/orchestrator's responsibility.

Input payload (one page)
------------------------
See `MINIMAL_PAYLOAD_EXAMPLE` at the bottom of this file for a complete example.

CLI
---
    python3 assemble_planning.py INPUT.json --refs REFS_DIR --out planningN.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from planning_validator import (  # noqa: E402
    DENSITY_DEFAULTS,
    VALID_CARD_ROLES,
    VALID_CARD_STYLES,
    VALID_CARD_TYPES,
    VALID_CHART_TYPES,
    VALID_DENSITY_BIASES,
    VALID_DENSITY_LABELS,
    VALID_IMAGE_PLACEMENTS,
    VALID_IMAGE_USAGES,
    VALID_LAYOUT_HINTS,
    VALID_NARRATIVE_ARCHETYPES,
    VALID_PAGE_TYPES,
    resource_exists,
    validate_page,
)
from workflow_versions import build_workflow_metadata  # noqa: E402


class AssemblyError(ValueError):
    """A judgment-level error in the input payload the assembler won't paper over."""


def _require(payload: dict, key: str, where: str = "page") -> Any:
    if key not in payload or payload[key] in (None, ""):
        raise AssemblyError(f"{where}: missing required field '{key}'")
    return payload[key]


def _check_enum(value: Any, valid: set[str], field: str, where: str) -> str:
    if value not in valid:
        raise AssemblyError(
            f"{where}: {field}={value!r} is not one of {sorted(valid)}")
    return value


def _as_body_list(value: Any, card_label: str) -> list[str]:
    """Coerce body to list[str] — the #1 hand-authoring bug, fixed by construction."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise AssemblyError(f"{card_label}: body must be a string or list of strings")


def _assemble_image(spec: Any, card_label: str) -> dict[str, Any]:
    """Return a full image contract. None/false → fully-null needed=false object."""
    if not spec:
        return {
            "mode": "decorate", "needed": False, "usage": None, "placement": None,
            "content_description": None, "source_hint": None, "decorate_brief": "",
        }
    if not isinstance(spec, dict):
        raise AssemblyError(f"{card_label}: image must be an object or null")
    usage = _check_enum(spec.get("usage"), VALID_IMAGE_USAGES, "image.usage", card_label)
    placement = _check_enum(
        spec.get("placement"), VALID_IMAGE_PLACEMENTS, "image.placement", card_label)
    for req in ("content_description", "source_hint"):
        if not spec.get(req):
            raise AssemblyError(f"{card_label}: image.{req} is required when an image is requested")
    return {
        "mode": spec.get("mode", "generate"),
        "needed": True,
        "usage": usage,
        "placement": placement,
        "content_description": spec["content_description"],
        "source_hint": spec["source_hint"],
        "decorate_brief": spec.get("decorate_brief", ""),
    }


def _clean_resource_ref(spec: Any, refs_dir: Path | None, dropped: list[str]) -> dict:
    """Drop per-card resource_ref entries that don't resolve on disk.

    The validator resolves resource_ref.block/chart/principle against references/;
    scrubbing here keeps category-7 unreachable for cards too, not just resources.
    """
    ref = dict(spec) if isinstance(spec, dict) else {}
    groups = {"block": "block_refs", "chart": "chart_refs", "principle": "principle_refs"}
    out: dict[str, Any] = {}
    for key, group in groups.items():
        value = ref.get(key)
        if isinstance(value, str) and value.strip():
            if refs_dir and not resource_exists(refs_dir, group, value):
                dropped.append(f"resource_ref.{key}:{value}")
                out[key] = None
            else:
                out[key] = value
        else:
            out[key] = None
    return out


def _assemble_card(spec: dict, slide_number: int, index: int, max_lines: int,
                   refs_dir: Path | None, dropped: list[str]) -> dict:
    role = _check_enum(spec.get("role"), VALID_CARD_ROLES, "role", f"card[{index}]")
    card_label = f"card[{index}]({role})"
    card_type = _check_enum(spec.get("card_type"), VALID_CARD_TYPES, "card_type", card_label)
    card_style = _check_enum(spec.get("card_style"), VALID_CARD_STYLES, "card_style", card_label)

    body = _as_body_list(spec.get("body"), card_label)
    data_points = spec.get("data_points") or []
    if not isinstance(data_points, list):
        raise AssemblyError(f"{card_label}: data_points must be a list of objects")

    chart = None
    if spec.get("chart_type"):
        chart_type = _check_enum(
            spec["chart_type"], VALID_CHART_TYPES, "chart_type", card_label)
        chart = {"chart_type": chart_type}

    image = _assemble_image(spec.get("image"), card_label)

    # Content sufficiency — a skeleton card is a judgment error, surfaced here.
    has_content = bool(body or data_points or chart or image["needed"])
    if not has_content:
        raise AssemblyError(
            f"{card_label}: no content signal — supply body, data_points, chart_type, "
            f"or an image (a headline alone is a skeleton card)")

    # body_max_lines can never exceed the density cap: auto-cap it.
    requested_lines = spec.get("body_max_lines", max_lines)
    body_max_lines = min(int(requested_lines), max_lines) if requested_lines else max_lines

    card_id = spec.get("card_id") or f"s{slide_number}-{role}-{index}"
    card: dict[str, Any] = {
        "card_id": card_id,
        "role": role,
        "card_type": card_type,
        "card_style": card_style,
        "headline": spec.get("headline", ""),
        "body": body,
        "data_points": data_points,
        "chart": chart,
        "content_budget": {
            "headline_max_chars": spec.get("headline_max_chars", 12),
            "body_max_bullets": spec.get("body_max_bullets", 3),
            "body_max_lines": body_max_lines,
        },
        "image": image,
        "resource_ref": _clean_resource_ref(spec.get("resource_ref"), refs_dir, dropped),
    }
    if spec.get("argument_role"):
        card["argument_role"] = spec["argument_role"]
    if card_type == "diagram" and spec.get("diagram_source"):
        card["diagram_source"] = spec["diagram_source"]
    return card


def _clean_refs(resources: dict, refs_dir: Path | None, dropped: list[str]) -> dict:
    """Drop any *_ref that doesn't resolve on disk so category-7 ERRORs can't happen."""
    out = dict(resources or {})
    for group in ("layout_refs", "block_refs", "chart_refs", "principle_refs"):
        vals = out.get(group) or []
        if not isinstance(vals, list):
            vals = [vals]
        kept = []
        for v in vals:
            if not isinstance(v, str) or not v.strip():
                continue
            if refs_dir and not resource_exists(refs_dir, group, v):
                dropped.append(f"{group}:{v}")
                continue
            kept.append(v)
        out[group] = kept
    pt = out.get("page_template")
    if pt and refs_dir and not resource_exists(refs_dir, "page_template", pt):
        dropped.append(f"page_template:{pt}")
        out["page_template"] = None
    out.setdefault("page_template", None)
    return out


def assemble_page(payload: dict, refs_dir: Path | None = None) -> tuple[dict, list[str]]:
    """Assemble a full, schema-valid page dict from a minimal payload.

    Returns (page, dropped_refs). Raises AssemblyError on judgment-level problems
    and RuntimeError if the self-validation still finds a validator ERROR.
    """
    slide_number = int(_require(payload, "slide_number"))
    page_type = _check_enum(_require(payload, "page_type"), VALID_PAGE_TYPES, "page_type", "page")

    density_label = _check_enum(
        _require(payload, "density_label"), VALID_DENSITY_LABELS, "density_label", "page")
    deck_bias = _check_enum(
        _require(payload, "deck_bias"), VALID_DENSITY_BIASES, "deck_bias", "page")
    lower = _check_enum(
        _require(payload, "page_lower_bound"), VALID_DENSITY_LABELS, "page_lower_bound", "page")
    upper = _check_enum(
        _require(payload, "page_upper_bound"), VALID_DENSITY_LABELS, "page_upper_bound", "page")

    # The 7 mechanical density fields come straight from the validator's table.
    defaults = DENSITY_DEFAULTS[density_label]
    density_contract = {
        "deck_bias": deck_bias,
        "page_lower_bound": lower,
        "page_upper_bound": upper,
        **defaults,
    }

    archetype = payload.get("narrative_archetype", "persuasive")
    _check_enum(archetype, VALID_NARRATIVE_ARCHETYPES, "narrative_archetype", "page")

    visual_weight = int(payload.get("visual_weight", 5))
    if not 1 <= visual_weight <= 9:
        raise AssemblyError(f"page: visual_weight={visual_weight} must be in [1, 9]")

    dropped: list[str] = []
    cards_in = payload.get("cards") or []
    if not cards_in:
        raise AssemblyError("page: at least one card is required")
    cards = [
        _assemble_card(c, slide_number, i, density_contract["max_lines_per_card"],
                       refs_dir, dropped)
        for i, c in enumerate(cards_in, start=1)
    ]

    # Composition invariants the assembler can check but not safely auto-fix.
    anchors = [c for c in cards if c["role"] == "anchor"]
    if len(anchors) != 1:
        raise AssemblyError(
            f"page: exactly one anchor card required, got {len(anchors)}")
    if page_type == "content" and len(cards) >= 2:
        if len({c["card_style"] for c in cards}) < 2:
            raise AssemblyError(
                "page: a content page with >=2 cards needs >=2 distinct card_styles")

    resources = _clean_refs(payload.get("resources", {}), refs_dir, dropped)

    page: dict[str, Any] = {
        "slide_number": slide_number,
        "page_type": page_type,
        "narrative_role": payload.get("narrative_role", ""),
        "narrative_archetype": archetype,
        "title": _require(payload, "title"),
        "page_goal": _require(payload, "page_goal"),
        "visual_weight": visual_weight,
        "density_label": density_label,
        "density_reason": _require(payload, "density_reason"),
        "density_contract": density_contract,
        "director_command": payload.get("director_command") or {"mood": "", "prose": ""},
        "decoration_hints": payload.get("decoration_hints") or {"background": {}},
        "resources": resources,
        "cards": cards,
        "workflow_metadata": build_workflow_metadata("planning"),
    }
    if page_type == "content":
        page["layout_hint"] = _check_enum(
            _require(payload, "layout_hint"), VALID_LAYOUT_HINTS, "layout_hint", "page")
        page["source_guidance"] = payload.get("source_guidance") or {"strictness": "grounded"}
    for optional in ("audience_takeaway", "focus_zone", "must_avoid", "rhythm_action",
                     "layout_variation_note", "persistent_chrome", "deck_chrome"):
        if optional in payload:
            page[optional] = payload[optional]

    # Final gate: never emit a page the oracle would reject. Because every
    # mechanical field is filled from the validator's own constants, a residual
    # error here is a cross-field JUDGMENT combination the payload chose (e.g.
    # density_label vs page_type, deck_bias floors, image_policy vs card image)
    # — surface it as a fail-fast judgment error, not an "assembler bug".
    result = validate_page(page, refs_dir)
    if result.errors:
        raise AssemblyError(
            "assembled page failed schema validation — fix the payload per these "
            "validator errors (each names its field):\n  " + "\n  ".join(result.errors))
    return page, dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Minimal page payload JSON")
    parser.add_argument("--refs", help="references directory (for ref resolution)")
    parser.add_argument("--out", help="output planning JSON path (default: stdout)")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "page" in payload and isinstance(payload["page"], dict):
        payload = payload["page"]
    refs_dir = Path(args.refs).resolve() if args.refs else None

    try:
        page, dropped = assemble_page(payload, refs_dir)
    except AssemblyError as exc:
        print(f"ASSEMBLY ERROR: {exc}", file=sys.stderr)
        return 2

    for d in dropped:
        print(f"WARN: dropped unresolvable ref {d}", file=sys.stderr)

    out_text = json.dumps({"page": page}, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"OK: wrote validated planning to {args.out}")
    else:
        print(out_text)
    return 0


# A minimal payload — note `body` is a bare string, there is no density_contract,
# no workflow_metadata, no card_id, no image contract, no content_budget.
MINIMAL_PAYLOAD_EXAMPLE = {
    "slide_number": 3,
    "page_type": "content",
    "title": "Adoption is accelerating",
    "page_goal": "usage doubled after the redesign",
    "narrative_role": "evidence",
    "density_label": "medium",
    "density_reason": "one headline metric plus a supporting breakdown",
    "deck_bias": "balanced",
    "page_lower_bound": "mid_low",
    "page_upper_bound": "high",
    "layout_hint": "mixed-grid",
    "resources": {"layout_refs": ["mixed-grid"], "chart_refs": ["basic"],
                  "principle_refs": ["visual-hierarchy"], "block_refs": []},
    "cards": [
        {"role": "anchor", "card_type": "data", "card_style": "elevated",
         "argument_role": "claim", "headline": "2x usage",
         "body": "Weekly active users doubled in the quarter after launch.",
         "chart_type": "metric_row"},
        {"role": "support", "card_type": "text", "card_style": "outline",
         "headline": "What changed", "body": ["Simpler onboarding.", "Faster load."]},
    ],
}


if __name__ == "__main__":
    raise SystemExit(main())

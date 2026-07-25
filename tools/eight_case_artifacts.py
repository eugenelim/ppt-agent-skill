"""Structured artifact publisher for the eight-case parity CI gate.

`publish_fixture_artifact` renders one scoped fixture on one lane and writes a
JSON record to ``<out_dir>/<fixture>/<lane>.json`` capturing the fields the
spec (``eight-case-parity-ci-and-cleanup`` AC7) requires:

  fixture source hash · implementation git SHA · compiler metadata · layout
  metadata · normalized nodes/groups/boxes/fragments · normalized
  routes/messages · labels/markers · gates · validation result · assertion
  count · reference-extraction result · fresh HTML/SVG comparison artifact.

Determinism (AC9)
-----------------
The record is split into two subtrees:

  ``normalized``  — semantic + geometry records. Floats are rounded to
                    ``_FLOAT_NDIGITS`` places and keys are emitted sorted, so
                    two clean runs on the same commit produce byte-identical
                    ``normalized`` subtrees regardless of dict ordering.
  ``provenance``  — volatile fields (impl git SHA, node/elkjs versions). Stable
                    within a commit but excluded from the AC9 byte-equality
                    contract, which is asserted on ``normalized`` only.

The publisher NEVER reads a pre-existing generated artifact as a source of
truth (spec Never-rule): every field is derived fresh from a live compile.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# ── import surface: put scripts/ on sys.path ──────────────────────────────────
# This module lives at tools/eight_case_artifacts.py (deliberately OUTSIDE the
# renderer-free tools/mermaid_fidelity/ core boundary): it depends on the live
# mermaid_render pipeline, which that core forbids.
_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mermaid_render as mr  # noqa: E402
from mermaid_render.layout._layout_validation import (  # noqa: E402
    all_violations,
    translate_layout_to_positive,
)
from mermaid_render.layout._sequence_compile import compile_sequence  # noqa: E402
from mermaid_render.layout._strategies import (  # noqa: E402
    RenderOptions,
    _compile_flowchart,
)
from mermaid_render.layout.architecture import (  # noqa: E402
    arch_to_finalized,
    compile_architecture,
)

_FLOAT_NDIGITS = 2

FLOWCHART_FIXTURES = (
    "flowchart-arrows-defs",
    "flowchart-cross-scope-edge",
    "flowchart-empty-subgraph",
    "flowchart-groups-complex",
    "flowchart-inner-direction",
)
ARCHITECTURE_FIXTURES = ("architecture-complex",)
SEQUENCE_FIXTURES = ("sequence-box-unsupported", "sequence-nested-fragments")
ALL_FIXTURES = FLOWCHART_FIXTURES + ARCHITECTURE_FIXTURES + SEQUENCE_FIXTURES

_FIXTURE_DIR = _REPO / "tests" / "fixtures"


# ── helpers ────────────────────────────────────────────────────────────────

def _r(v: Any) -> Any:
    """Round floats for deterministic serialization; recurse into containers."""
    if isinstance(v, float):
        return round(v, _FLOAT_NDIGITS)
    if isinstance(v, (list, tuple)):
        return [_r(x) for x in v]
    if isinstance(v, dict):
        return {k: _r(x) for k, x in v.items()}
    return v


def _rect(rect: Any) -> Optional[list[float]]:
    if rect is None:
        return None
    return [round(rect.x, _FLOAT_NDIGITS), round(rect.y, _FLOAT_NDIGITS),
            round(rect.w, _FLOAT_NDIGITS), round(rect.h, _FLOAT_NDIGITS)]


def _pt(p: Any) -> list[float]:
    return [round(p.x, _FLOAT_NDIGITS), round(p.y, _FLOAT_NDIGITS)]


def _bounds(b: Any) -> Optional[list[float]]:
    """Normalize a sequence ``Bounds`` (left/top/right/bottom) to [x, y, w, h]."""
    if b is None:
        return None
    return [round(b.left, _FLOAT_NDIGITS), round(b.top, _FLOAT_NDIGITS),
            round(b.right - b.left, _FLOAT_NDIGITS),
            round(b.bottom - b.top, _FLOAT_NDIGITS)]


def _impl_git_sha() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_REPO),
        )
        return out.stdout.strip() or None
    except Exception:  # pragma: no cover - defensive
        return None


def _source_hash(src: str) -> str:
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


# ── per-type normalization ───────────────────────────────────────────────────

def _normalize_flowchart(src: str, *, force_python: bool) -> dict[str, Any]:
    opts = RenderOptions()
    import os
    prev = os.environ.get("MERMAID_LAYOUT_ENGINE")
    if force_python:
        os.environ["MERMAID_LAYOUT_ENGINE"] = "python"
    try:
        compiled = _compile_flowchart(src, None, opts)
    finally:
        if force_python:
            if prev is None:
                os.environ.pop("MERMAID_LAYOUT_ENGINE", None)
            else:
                os.environ["MERMAID_LAYOUT_ENGINE"] = prev
    layout = compiled.layout
    md = compiled.metadata
    positive = translate_layout_to_positive(layout)
    violations = all_violations(positive)

    nodes = [
        {"id": nid, "bounds": _rect(nl.outer_bounds),
         "parent_group": nl.parent_group_id}
        for nid, nl in sorted(layout.node_layouts.items())
        if not getattr(nl, "is_dummy", False)
    ]
    groups = [
        {"id": gid, "bounds": _rect(gl.boundary_bounds),
         "members": sorted(gl.member_ids), "direction": gl.local_direction,
         "empty": len(gl.member_ids) == 0}
        for gid, gl in sorted(layout.group_layouts.items())
    ]
    routes = [
        {"id": re_obj.edge_id, "src": re_obj.src_node_id, "dst": re_obj.dst_node_id,
         "style": re_obj.edge_style, "waypoints": [_pt(w) for w in re_obj.waypoints],
         "marker_end": re_obj.has_marker_end, "marker_start": re_obj.has_marker_start}
        for re_obj in layout.routed_edges
    ]
    gates = [
        {"id": g.gate_id, "group": g.group_id, "edge": g.edge_id,
         "side": g.side.value, "kind": g.kind.value, "point": _pt(g.point)}
        for g in layout.boundary_gates
    ]
    return {
        "semantic_compiler": "flowchart",
        "layout_metadata": {
            "backend": md.backend, "algorithm": md.algorithm,
            "direction": md.direction, "node_count": md.node_count,
            "group_count": md.group_count, "edge_count": md.edge_count,
            "fallback_reason": md.fallback_reason,
        },
        "nodes": nodes, "groups": groups, "boxes": [], "fragments": [],
        "routes": routes, "messages": [], "gates": gates,
        "canvas": _rect(layout.canvas_bounds),
        "validation": {"violations": violations, "clean": violations == []},
        "assertion_count": len(nodes) + len(groups) + len(routes) + len(gates),
    }


def _normalize_architecture(src: str) -> dict[str, Any]:
    arch = compile_architecture(src)
    fl = arch_to_finalized(arch)
    positive = translate_layout_to_positive(fl)
    violations = all_violations(positive)
    services = [
        {"id": s.node_id, "label": s.label, "bounds": _rect(s.outer_bounds),
         "group": s.group_id}
        for s in sorted(arch.services, key=lambda s: s.node_id)
    ]
    groups = [
        {"id": g.group_id, "label": g.label, "bounds": _rect(g.boundary_bounds),
         "members": sorted(g.member_ids)}
        for g in sorted(arch.groups, key=lambda g: g.group_id)
    ]
    edges = [
        {"id": e.edge_id, "src": e.src_id, "dst": e.dst_id, "label": e.label,
         "waypoints": [_pt(w) for w in e.waypoints],
         "src_side": e.src_port.side.value, "dst_side": e.dst_port.side.value,
         "marker_end": e.has_marker_end, "marker_start": e.has_marker_start}
        for e in arch.edges
    ]
    return {
        "semantic_compiler": "architecture",
        "layout_metadata": {"backend": arch.backend, "direction": arch.direction},
        "nodes": services, "groups": groups, "boxes": [], "fragments": [],
        "routes": edges, "messages": [], "gates": [],
        "canvas": _rect(arch.canvas_bounds),
        "validation": {"violations": violations, "clean": violations == []},
        "assertion_count": len(services) + len(groups) + len(edges) * 2,
    }


def _normalize_sequence(src: str) -> dict[str, Any]:
    geom = compile_sequence(src).geometry
    participants = [
        {"id": p.participant_id, "label": p.label,
         "center_x": round(p.center_x, _FLOAT_NDIGITS)}
        for p in geom.participants
    ]
    boxes = [
        {"label": b.label, "members": sorted(b.participant_ids),
         "color": b.color}
        for b in sorted(geom.boxes, key=lambda b: b.label)
    ]
    fragments = [
        {"id": f.fragment_id, "kind": f.kind, "parent": f.parent_fragment_id,
         "participants": sorted(f.participant_ids), "bounds": _bounds(f.bounds),
         "depth": f.depth}
        for f in geom.fragments
    ]
    branches = [
        {"id": br.branch_id, "parent": br.parent_fragment_id, "label": br.label}
        for br in geom.branches
    ]
    messages = [
        {"id": m.event_id, "src": m.source_id, "dst": m.destination_id,
         "arrow": m.arrow_token, "baseline_y": round(m.baseline_y, _FLOAT_NDIGITS)}
        for m in geom.messages
    ]
    # Derived (not hardcoded) integrity checks for the sequence model: every box
    # member and every fragment/branch parent must resolve. Sequence uses its own
    # geometry model (not FinalizedLayout), so the geometric segment/canvas
    # validators do not apply here — these reference-integrity checks are what a
    # sequence lane can meaningfully assert.
    _pids = {p.participant_id for p in geom.participants}
    _frag_ids = {f.fragment_id for f in geom.fragments}
    seq_violations: list[str] = []
    for b in geom.boxes:
        for m in b.participant_ids:
            if m not in _pids:
                seq_violations.append(f"box {b.label!r} member {m!r} not a participant")
    for f in geom.fragments:
        if f.parent_fragment_id and f.parent_fragment_id not in _frag_ids:
            seq_violations.append(
                f"fragment {f.fragment_id!r} parent {f.parent_fragment_id!r} unresolved"
            )
    for br in geom.branches:
        if br.parent_fragment_id not in _frag_ids:
            seq_violations.append(
                f"branch {br.branch_id!r} parent {br.parent_fragment_id!r} unresolved"
            )
    return {
        "semantic_compiler": "sequence",
        "layout_metadata": {"backend": "sequence-geometry"},
        "nodes": participants, "groups": [], "boxes": boxes, "fragments": fragments,
        "branches": branches, "routes": [], "messages": messages, "gates": [],
        # SequenceGeometry.canvas is a (w, h) tuple, not a Rect.
        "canvas": [round(geom.canvas[0], _FLOAT_NDIGITS),
                   round(geom.canvas[1], _FLOAT_NDIGITS)],
        "validation": {"violations": seq_violations, "clean": seq_violations == [],
                       "kind": "sequence-reference-integrity"},
        "assertion_count": (len(participants) + len(boxes) + len(fragments)
                            + len(branches) + len(messages)),
    }


def _normalize(stem: str, src: str, *, force_python: bool) -> dict[str, Any]:
    if stem in FLOWCHART_FIXTURES:
        return _normalize_flowchart(src, force_python=force_python)
    if stem in ARCHITECTURE_FIXTURES:
        return _normalize_architecture(src)
    if stem in SEQUENCE_FIXTURES:
        return _normalize_sequence(src)
    raise ValueError(f"unknown fixture: {stem!r}")


# ── render / comparison artifact ──────────────────────────────────────────────

def _render_comparison(stem: str, faithful: bool, out_dir: Path) -> dict[str, Any]:
    """Render fresh HTML + SVG and record a structural comparison artifact.

    ``comparable`` is the AND of a fixed set of structural checks; ``check_count``
    records how many ran so a downstream reader can enforce the "zero-check
    comparison pass is vacuous" hard condition (a comparison with ``check_count``
    of 0 must never be read as a pass). This is a structural (root-tag / non-empty)
    comparison; the deeper HTML↔SVG *semantic* agreement is asserted on real
    fixtures by ``test_real_html_svg_semantic_agreement`` in the CI gate suite.
    """
    html = mr.to_html(src=_read(stem), faithful=faithful)
    if stem in SEQUENCE_FIXTURES or stem in ARCHITECTURE_FIXTURES:
        svg = mr.to_svg(src=_read(stem), faithful=faithful, experimental=True)
    else:
        svg = mr.to_svg(src=_read(stem), faithful=faithful)
    html_path = out_dir / f"{stem}.html"
    svg_path = out_dir / f"{stem}.svg"
    html_path.write_text(html)
    svg_path.write_text(svg)
    checks = {
        "html_has_root": "<html" in html.lower(),
        "svg_has_root": "<svg" in svg.lower(),
        "html_nonempty": bool(html.strip()),
        "svg_nonempty": bool(svg.strip()),
    }
    return {
        "html_artifact": html_path.name,
        "svg_artifact": svg_path.name,
        "checks": checks,
        "check_count": len(checks),
        "comparable": len(checks) > 0 and all(checks.values()),
    }


def _read(stem: str) -> str:
    return (_FIXTURE_DIR / f"{stem}.mmd").read_text()


# ── public entry point ─────────────────────────────────────────────────────

def publish_fixture_artifact(
    stem: str,
    out_dir: Path | str,
    *,
    faithful: bool = False,
    force_python: bool = False,
    impl_sha: Optional[str] = None,
    node_version: Optional[str] = None,
    elkjs_version: Optional[str] = None,
) -> dict[str, Any]:
    """Compile + render ``stem`` on one lane and write its JSON artifact.

    Returns the record dict. ``normalized`` is deterministic on a fixed commit;
    ``provenance`` carries the volatile fields excluded from the AC9 contract.
    """
    src = _read(stem)
    lane = ("faithful" if faithful else "editorial") + (
        "-python" if force_python else ""
    )
    fixture_dir = Path(out_dir) / stem
    fixture_dir.mkdir(parents=True, exist_ok=True)

    normalized = _normalize(stem, src, force_python=force_python)
    normalized["source_hash"] = _source_hash(src)
    comparison = _render_comparison(stem, faithful, fixture_dir)

    record = {
        "fixture": stem,
        "lane": lane,
        "normalized": normalized,
        "comparison": comparison,
        # Reference extraction is derived fresh (never a stored artifact): the
        # eight-case gate does not invoke mmdc, so it is explicitly not-run
        # rather than read from a pre-existing file (spec Never-rule).
        "reference_extraction": {"status": "not-run",
                                 "reason": "eight-case gate is self-consistent; "
                                           "differential mmdc lane is separate"},
        "provenance": {
            "impl_git_sha": impl_sha if impl_sha is not None else _impl_git_sha(),
            "node_version": node_version,
            "elkjs_version": elkjs_version,
        },
    }

    out_path = fixture_dir / f"{lane}.json"
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def publish_all(out_dir: Path | str) -> int:
    """Publish faithful + editorial artifacts for every scoped fixture.

    Flowchart fixtures publish on the deterministic Python backend; architecture
    and sequence use their default backend. Returns the number of lanes written.
    Invoked as a dedicated CI step (see the ``eight-case-parity`` job) so artifact
    generation is a build action, not a test side effect.
    """
    count = 0
    for stem in ALL_FIXTURES:
        force_python = stem in FLOWCHART_FIXTURES
        for faithful in (True, False):
            publish_fixture_artifact(
                stem, out_dir, faithful=faithful, force_python=force_python
            )
            count += 1
    return count


if __name__ == "__main__":  # pragma: no cover - CI entry point
    import argparse

    parser = argparse.ArgumentParser(description="Publish eight-case CI artifacts.")
    parser.add_argument(
        "--out-dir", default=str(_REPO / "test-artifacts"),
        help="output directory (default: <repo>/test-artifacts)",
    )
    args = parser.parse_args()
    n = publish_all(args.out_dir)
    print(f"published {n} eight-case artifact lanes to {args.out_dir}")

"""mermaid_render.layout.gitgraph — Native gitGraph scene builder.

Parses ``gitGraph [LR|TB|BT|RL]:`` source and renders commit circles on
branch lanes with merge arrows.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..scene import (
    AccessibilityMetadata,
    FillStyle,
    LAYER_BACKGROUND,
    LAYER_EDGES,
    LAYER_LABELS,
    LAYER_NODES,
    LAYER_ORDER,
    MarkerDefinition,
    PaintStyle,
    SceneCircle,
    SceneLine,
    ScenePath,
    SceneRect,
    SceneText,
    SceneTextLine,
    StrokeStyle,
    SvgScene,
    make_scene_id,
)


# ── Color tokens ──────────────────────────────────────────────────────────────

_BG_FILL = "#f8fafc"
_BRANCH_COLORS = (
    "#60a5fa",  # main/master
    "#34d399",
    "#f59e0b",
    "#f87171",
    "#a78bfa",
    "#2dd4bf",
    "#fb923c",
    "#e879f9",
)
_COMMIT_STROKE = "#ffffff"
_TAG_FILL = "#fef3c7"
_TAG_STROKE = "#d97706"
_TAG_TEXT = "#92400e"
_LABEL_COLOR = "#374151"
_TITLE_COLOR = "#111827"

# ── Layout constants ──────────────────────────────────────────────────────────

_LANE_H = 48         # height per branch lane (LR mode: vertical spacing)
_COMMIT_STEP = 80    # horizontal distance between commits (LR mode)
_COMMIT_R = 10
_PAD_H = 40
_PAD_V = 32
_LABEL_FONT = 11
_TAG_FONT = 9
_TITLE_FONT = 16


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_gitgraph_source(src: str) -> tuple[str, list[dict]]:
    """Return (direction, commands).

    commands: list of {type, id, tag, branch_name, from_branch, commit_type}
    """
    direction = "LR"
    commands: list[dict] = []

    for line in src.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue

        # Directive line
        m = re.match(r'^gitGraph\s*(LR|TB|BT|RL)?', stripped, re.IGNORECASE)
        if m:
            if m.group(1):
                direction = m.group(1).upper()
            continue

        # commit id: "name" tag: "tag" type: HIGHLIGHT|REVERSE|NORMAL
        if stripped.lower().startswith("commit"):
            rest = stripped[6:].strip()
            commit_id = ""
            tag = ""
            commit_type = "normal"

            mid = re.search(r'id:\s*"([^"]*)"', rest)
            if mid:
                commit_id = mid.group(1)
            mtag = re.search(r'tag:\s*"([^"]*)"', rest)
            if mtag:
                tag = mtag.group(1)
            mtype = re.search(r'type:\s*(HIGHLIGHT|REVERSE|NORMAL)', rest, re.IGNORECASE)
            if mtype:
                commit_type = mtype.group(1).lower()

            commands.append({"type": "commit", "id": commit_id, "tag": tag, "commit_type": commit_type})
            continue

        # branch name
        m = re.match(r'^branch\s+(.+)', stripped, re.IGNORECASE)
        if m:
            branch_name = m.group(1).strip()
            commands.append({"type": "branch", "branch_name": branch_name})
            continue

        # checkout name
        m = re.match(r'^checkout\s+(.+)', stripped, re.IGNORECASE)
        if m:
            branch_name = m.group(1).strip()
            commands.append({"type": "checkout", "branch_name": branch_name})
            continue

        # merge name [id: "..."] [tag: "..."]
        m = re.match(r'^merge\s+(\S+)(.*)', stripped, re.IGNORECASE)
        if m:
            target = m.group(1).strip()
            rest = m.group(2).strip()
            merge_id = ""
            merge_tag = ""
            mid2 = re.search(r'id:\s*"([^"]*)"', rest)
            if mid2:
                merge_id = mid2.group(1)
            mtag2 = re.search(r'tag:\s*"([^"]*)"', rest)
            if mtag2:
                merge_tag = mtag2.group(1)
            commands.append({"type": "merge", "branch_name": target, "id": merge_id, "tag": merge_tag})
            continue

        # cherry-pick
        m = re.match(r'^cherry-pick\s+id:\s*"([^"]*)"', stripped, re.IGNORECASE)
        if m:
            commands.append({"type": "cherry-pick", "id": m.group(1)})

    return direction, commands


# ── Scene builder ─────────────────────────────────────────────────────────────

def layout_gitgraph_scene(src: str, *, width_hint: int = 0) -> SvgScene:
    """Parse gitGraph source and return an SvgScene with commit/branch layout."""
    direction, commands = _parse_gitgraph_source(src)

    content_hash = int(hashlib.sha1(src.encode()).hexdigest(), 16)
    scene_id = make_scene_id("gitgraph", content_hash)

    # Simulate the git graph to determine layout
    branches: dict[str, dict] = {"main": {"lane": 0, "commits": [], "color": _BRANCH_COLORS[0]}}
    current_branch = "main"
    next_lane = 1
    commits: list[dict] = []   # {id, branch, lane, col, tag, commit_type, parent_commit}
    col = 0
    last_commit_on: dict[str, int | None] = {"main": None}  # branch → last commit index
    markers: list[tuple] = []   # (from_commit_idx, to_commit_idx) for edges

    for cmd in commands:
        ctype = cmd["type"]

        if ctype == "branch":
            bname = cmd["branch_name"]
            if bname not in branches:
                color = _BRANCH_COLORS[next_lane % len(_BRANCH_COLORS)]
                branches[bname] = {"lane": next_lane, "commits": [], "color": color}
                last_commit_on[bname] = last_commit_on.get(current_branch)
                next_lane += 1

        elif ctype == "checkout":
            bname = cmd["branch_name"]
            if bname not in branches:
                color = _BRANCH_COLORS[next_lane % len(_BRANCH_COLORS)]
                branches[bname] = {"lane": next_lane, "commits": [], "color": color}
                last_commit_on[bname] = None
                next_lane += 1
            current_branch = bname

        elif ctype == "commit":
            lane = branches[current_branch]["lane"]
            parent_idx = last_commit_on.get(current_branch)
            commit_rec = {
                "id": cmd["id"],
                "tag": cmd["tag"],
                "branch": current_branch,
                "lane": lane,
                "col": col,
                "commit_type": cmd["commit_type"],
                "parent_idx": parent_idx,
                "color": branches[current_branch]["color"],
            }
            commits.append(commit_rec)
            commit_idx = len(commits) - 1
            last_commit_on[current_branch] = commit_idx
            if parent_idx is not None:
                markers.append((parent_idx, commit_idx))
            col += 1

        elif ctype == "merge":
            target = cmd["branch_name"]
            if target not in branches:
                continue
            lane = branches[current_branch]["lane"]
            parent_idx = last_commit_on.get(current_branch)
            merge_parent_idx = last_commit_on.get(target)
            commit_rec = {
                "id": cmd["id"],
                "tag": cmd["tag"],
                "branch": current_branch,
                "lane": lane,
                "col": col,
                "commit_type": "merge",
                "parent_idx": parent_idx,
                "color": branches[current_branch]["color"],
            }
            commits.append(commit_rec)
            commit_idx = len(commits) - 1
            last_commit_on[current_branch] = commit_idx
            if parent_idx is not None:
                markers.append((parent_idx, commit_idx))
            if merge_parent_idx is not None:
                markers.append((merge_parent_idx, commit_idx))
            col += 1

    if not commits:
        w = max(width_hint or 400, 400)
        h = 160
        return SvgScene(
            scene_id=scene_id,
            diagram_type="gitgraph",
            width=float(w),
            height=float(h),
            view_box=(0.0, 0.0, float(w), float(h)),
            accessibility=AccessibilityMetadata(title="Git graph"),
            layers=tuple((name, ()) for name in LAYER_ORDER),
        )

    n_lanes = max(c["lane"] for c in commits) + 1
    n_cols = max(c["col"] for c in commits) + 1

    # LR layout: x = col position, y = lane position
    canvas_w = float(_PAD_H * 2 + n_cols * _COMMIT_STEP)
    canvas_h = float(_PAD_V * 2 + n_lanes * _LANE_H)

    def _commit_pos(commit: dict) -> tuple[float, float]:
        if direction == "LR":
            x = float(_PAD_H + commit["col"] * _COMMIT_STEP)
            y = float(_PAD_V + commit["lane"] * _LANE_H)
        else:
            # TB: flip x/y axes
            x = float(_PAD_H + commit["lane"] * _LANE_H)
            y = float(_PAD_V + commit["col"] * _COMMIT_STEP)
        return x, y

    if direction != "LR":
        canvas_w, canvas_h = (
            float(_PAD_H * 2 + n_lanes * _LANE_H),
            float(_PAD_V * 2 + n_cols * _COMMIT_STEP),
        )

    bg_elements: list = []
    edge_elements: list = []
    node_elements: list = []
    label_elements: list = []

    bg_elements.append(SceneRect(
        element_id=f"{scene_id}-bg",
        x=0.0, y=0.0, w=canvas_w, h=canvas_h,
        paint=PaintStyle(fill=FillStyle(color=_BG_FILL)),
    ))

    # Branch lane lines (horizontal for LR)
    for bname, binfo in branches.items():
        lane = binfo["lane"]
        color = binfo["color"]
        lane_commits = [c for c in commits if c["lane"] == lane]
        if not lane_commits:
            continue
        start_x, start_y = _commit_pos(lane_commits[0])
        end_x, end_y = _commit_pos(lane_commits[-1])

        edge_elements.append(SceneLine(
            element_id=f"{scene_id}-lane-{lane}",
            x1=start_x, y1=start_y,
            x2=end_x, y2=end_y,
            paint=PaintStyle(stroke=StrokeStyle(color=color, width=2.0)),
            semantic_role="branch-lane",
            data_attrs=(("data-branch", bname),),
        ))

        # Branch label
        label_elements.append(SceneText(
            element_id=f"{scene_id}-branch-lbl-{lane}",
            lines=(SceneTextLine(
                text=bname,
                x=start_x - _COMMIT_R - 4,
                y=start_y + _LABEL_FONT * 0.35,
                font_size=float(_LABEL_FONT),
                fill_color=color,
                font_weight=600,
            ),),
            text_anchor="end",
        ))

    # Merge/parent edges
    for from_idx, to_idx in markers:
        fx, fy = _commit_pos(commits[from_idx])
        tx, ty = _commit_pos(commits[to_idx])
        if fx == tx and fy == ty:
            continue
        if fy == ty:
            # Same lane — straight line
            edge_elements.append(SceneLine(
                element_id=f"{scene_id}-edge-{from_idx}-{to_idx}",
                x1=fx, y1=fy, x2=tx, y2=ty,
                paint=PaintStyle(stroke=StrokeStyle(color="#94a3b8", width=1.5)),
            ))
        else:
            # Cross-lane — elbow path
            mid_x = (fx + tx) / 2
            edge_elements.append(ScenePath(
                element_id=f"{scene_id}-edge-{from_idx}-{to_idx}",
                commands=(
                    ("M", fx, fy),
                    ("L", mid_x, fy),
                    ("L", mid_x, ty),
                    ("L", tx, ty),
                ),
                paint=PaintStyle(
                    fill=FillStyle(color="none"),
                    stroke=StrokeStyle(color="#94a3b8", width=1.5),
                ),
            ))

    # Commit circles
    for idx, commit in enumerate(commits):
        cx_, cy_ = _commit_pos(commit)
        color = commit["color"]

        # Special shapes for commit types
        r = float(_COMMIT_R)
        if commit["commit_type"] == "milestone":
            r = float(_COMMIT_R * 0.7)

        fill_color = color
        if commit["commit_type"] == "reverse":
            fill_color = "#f87171"
        elif commit["commit_type"] == "highlight":
            fill_color = "#fbbf24"

        node_elements.append(SceneCircle(
            element_id=f"{scene_id}-commit-{idx}",
            cx=cx_, cy=cy_, r=r,
            paint=PaintStyle(
                fill=FillStyle(color=fill_color),
                stroke=StrokeStyle(color=_COMMIT_STROKE, width=2.0),
            ),
            semantic_role="commit",
            data_attrs=(
                ("data-id", commit["id"] or str(idx)),
                ("data-branch", commit["branch"]),
            ),
        ))

        # Commit id label (short)
        if commit["id"]:
            short_id = commit["id"][:7]
            label_elements.append(SceneText(
                element_id=f"{scene_id}-commit-lbl-{idx}",
                lines=(SceneTextLine(
                    text=short_id,
                    x=cx_,
                    y=cy_ + r + _LABEL_FONT + 2,
                    font_size=float(_LABEL_FONT),
                    fill_color=_LABEL_COLOR,
                ),),
                text_anchor="middle",
            ))

        # Tag
        if commit["tag"]:
            tag_x = cx_ + r + 4
            tag_y = cy_ - r - 4
            tag_w = len(commit["tag"]) * _TAG_FONT * 0.65 + 8
            node_elements.append(SceneRect(
                element_id=f"{scene_id}-tag-bg-{idx}",
                x=tag_x, y=tag_y - _TAG_FONT - 2,
                w=tag_w, h=float(_TAG_FONT + 4),
                paint=PaintStyle(
                    fill=FillStyle(color=_TAG_FILL),
                    stroke=StrokeStyle(color=_TAG_STROKE, width=0.5),
                ),
            ))
            label_elements.append(SceneText(
                element_id=f"{scene_id}-tag-{idx}",
                lines=(SceneTextLine(
                    text=commit["tag"],
                    x=tag_x + 4, y=tag_y - 3,
                    font_size=float(_TAG_FONT),
                    fill_color=_TAG_TEXT,
                ),),
                text_anchor="start",
            ))

    layers = tuple([
        (LAYER_BACKGROUND, tuple(bg_elements)),
        *[
            (name, ())
            for name in LAYER_ORDER
            if name not in (LAYER_BACKGROUND, LAYER_EDGES, LAYER_NODES, LAYER_LABELS)
        ],
        (LAYER_EDGES, tuple(edge_elements)),
        (LAYER_NODES, tuple(node_elements)),
        (LAYER_LABELS, tuple(label_elements)),
    ])

    return SvgScene(
        scene_id=scene_id,
        diagram_type="gitgraph",
        width=canvas_w,
        height=canvas_h,
        view_box=(0.0, 0.0, canvas_w, canvas_h),
        accessibility=AccessibilityMetadata(
            title="Git graph",
            description=f"Git graph with {len(commits)} commits across {n_lanes} branches",
        ),
        layers=layers,
    )

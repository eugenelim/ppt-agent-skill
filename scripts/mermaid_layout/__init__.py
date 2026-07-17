"""mermaid_layout package — deterministic Mermaid-to-HTML/CSS layout engine.

All public symbols are re-exported here for backward compatibility with
tests/test_mermaid_layout.py and scripts/test_diagram_qa.py.
"""
from ._constants import (
    NODE_CAP,
    EDGE_CAP,
    NODE_W,
    NODE_H,
    COL_GAP,
    RANK_GAP,
    CANVAS_PAD,
    GROUP_PAD_X,
    GROUP_PAD_Y_TOP,
    GROUP_PAD_Y_BOT,
    _Node,
    _Edge,
    _Group,
    _load_icon,
    _wrap_label,
    _node_render_h,
)
from ._parser import (
    _strip_frontmatter,
    _detect_directive,
    _parse_spec,
    _parse_spec_and_class,
    _parse_graph_source,
)
from ._layout import (
    _break_cycles,
    _assign_ranks,
    _minimize_crossings,
    _assign_coordinates,
    _compact_group_columns,
)
from ._routing import (
    _arrowhead,
    _smooth_orthogonal_path,
    _fan_offset,
    _route_edges,
)
from ._renderer import (
    _render_graph_fragment,
    _extract_diagram_title,
    _render_metadata_chip,
    _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
    _compute_group_bboxes,
)
from ._strategies import _dispatch

__all__ = [
    "NODE_CAP", "EDGE_CAP", "NODE_W", "NODE_H", "COL_GAP", "RANK_GAP", "CANVAS_PAD",
    "GROUP_PAD_X", "GROUP_PAD_Y_TOP", "GROUP_PAD_Y_BOT",
    "_Node", "_Edge", "_Group",
    "_load_icon", "_wrap_label", "_node_render_h",
    "_strip_frontmatter", "_detect_directive", "_parse_spec",
    "_parse_spec_and_class", "_parse_graph_source",
    "_break_cycles", "_assign_ranks", "_minimize_crossings", "_assign_coordinates",
    "_compact_group_columns",
    "_arrowhead", "_smooth_orthogonal_path", "_fan_offset", "_route_edges",
    "_render_graph_fragment", "_extract_diagram_title", "_render_metadata_chip",
    "_render_legend", "_separate_groups_lr", "_separate_groups_tb", "_compute_group_bboxes",
    "_dispatch",
]

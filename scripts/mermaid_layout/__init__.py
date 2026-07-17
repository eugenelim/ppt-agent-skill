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
    ICON_COL_WIDTH,
    _Node,
    _Edge,
    _Group,
    _load_icon,
    _measure_text_width,
    _wrap_label,
    _split_sub_label,
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
    _group_coherent_cols,
)
from ._routing import (
    _arrowhead,
    _smooth_orthogonal_path,
    _fan_offset,
    _route_edges,
    _clip_to_diamond,
)
from ._renderer import (
    _render_graph_fragment,
    _render_label_html,
    _extract_diagram_title,
    _render_metadata_chip,
    _render_legend,
    _separate_groups_lr,
    _separate_groups_tb,
    _compute_group_bboxes,
    _push_nonmembers_out_of_groups_lr,
    STYLE_COMPACT,
    STYLE_LARGE,
    THEME_DARK,
    THEME_LIGHT,
    make_page,
)
from ._strategies import _dispatch

__all__ = [
    "NODE_CAP", "EDGE_CAP", "NODE_W", "NODE_H", "COL_GAP", "RANK_GAP", "CANVAS_PAD",
    "GROUP_PAD_X", "GROUP_PAD_Y_TOP", "GROUP_PAD_Y_BOT", "ICON_COL_WIDTH",
    "_Node", "_Edge", "_Group",
    "_load_icon", "_measure_text_width", "_wrap_label", "_split_sub_label", "_node_render_h",
    "_strip_frontmatter", "_detect_directive", "_parse_spec",
    "_parse_spec_and_class", "_parse_graph_source",
    "_break_cycles", "_assign_ranks", "_minimize_crossings", "_assign_coordinates",
    "_compact_group_columns",
    "_arrowhead", "_smooth_orthogonal_path", "_fan_offset", "_route_edges", "_clip_to_diamond",
    "_render_graph_fragment", "_render_label_html", "_extract_diagram_title", "_render_metadata_chip",
    "_render_legend", "_separate_groups_lr", "_separate_groups_tb", "_compute_group_bboxes",
    "_push_nonmembers_out_of_groups_lr",
    "STYLE_COMPACT", "STYLE_LARGE",
    "THEME_DARK", "THEME_LIGHT", "make_page",
    "_dispatch",
]

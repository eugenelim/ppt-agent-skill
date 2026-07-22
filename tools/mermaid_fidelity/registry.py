"""Check capability registry — single source of truth for check name → implementation mapping.

Every manifest check name must appear in this registry.  Manifest validation and runner
execution resolve check names exclusively through get_capability(); there is no second
disconnected list of known names.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckCapability:
    name: str
    policy_kind: str                        # "strict" | "scored" | "ignored"
    supported_diagram_families: frozenset[str]  # empty = all families
    description: str = ""

    def supports_family(self, family: str) -> bool:
        return not self.supported_diagram_families or family in self.supported_diagram_families


_ALL_FAMILIES: frozenset[str] = frozenset()
_FLOWCHART = frozenset({"flowchart"})
_ARCHITECTURE = frozenset({"architecture"})
_SEQUENCE = frozenset({"sequence"})
_ER = frozenset({"er"})
_FLOWCHART_ARCH = frozenset({"flowchart", "architecture"})
_FLOWCHART_ARCH_ER = frozenset({"flowchart", "architecture", "er"})


_REGISTRY: dict[str, CheckCapability] = {
    # ── strict checks ─────────────────────────────────────────────────────────
    "parse": CheckCapability(
        name="parse",
        policy_kind="strict",
        supported_diagram_families=_ALL_FAMILIES,
        description="Parse accepted/rejected state and diagram family must agree",
    ),
    "diagram-type": CheckCapability(
        name="diagram-type",
        policy_kind="strict",
        supported_diagram_families=_ALL_FAMILIES,
        description="Detected diagram type must match",
    ),
    "entities": CheckCapability(
        name="entities",
        policy_kind="strict",
        supported_diagram_families=_ALL_FAMILIES,
        description="Entity set (IDs, kinds, shapes) must match",
    ),
    "labels": CheckCapability(
        name="labels",
        policy_kind="strict",
        supported_diagram_families=_ALL_FAMILIES,
        description="Entity labels (normalized) must match",
    ),
    "relations": CheckCapability(
        name="relations",
        policy_kind="strict",
        supported_diagram_families=_ALL_FAMILIES,
        description="Relation multiset (with multiplicity) must match",
    ),
    "direction": CheckCapability(
        name="direction",
        policy_kind="strict",
        supported_diagram_families=_FLOWCHART,
        description="Flowchart direction (TB/LR/BT/RL) must match",
    ),
    "containment": CheckCapability(
        name="containment",
        policy_kind="strict",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Group containment and membership must match",
    ),
    "edge-endpoints": CheckCapability(
        name="edge-endpoints",
        policy_kind="strict",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Relation source/target entity pairs must match",
    ),
    "actor-order": CheckCapability(
        name="actor-order",
        policy_kind="strict",
        supported_diagram_families=_SEQUENCE,
        description="Sequence actor declaration order must match",
    ),
    "message-order": CheckCapability(
        name="message-order",
        policy_kind="strict",
        supported_diagram_families=_SEQUENCE,
        description="Sequence message order must match",
    ),
    "cardinality": CheckCapability(
        name="cardinality",
        policy_kind="strict",
        supported_diagram_families=_ER,
        description="ER cardinality markers must match",
    ),
    "identifying": CheckCapability(
        name="identifying",
        policy_kind="strict",
        supported_diagram_families=_ER,
        description="ER identifying relationship flag must match",
    ),
    # ── scored checks ─────────────────────────────────────────────────────────
    "entity-centers": CheckCapability(
        name="entity-centers",
        policy_kind="scored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Normalized entity-center error (continuous; informational in Phase 1)",
    ),
    "entity-sizes": CheckCapability(
        name="entity-sizes",
        policy_kind="scored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Median entity width/height error (continuous; informational)",
    ),
    "canvas-aspect": CheckCapability(
        name="canvas-aspect",
        policy_kind="scored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Canvas aspect-ratio delta (informational)",
    ),
    "connector-paths": CheckCapability(
        name="connector-paths",
        policy_kind="scored",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Sampled connector-path distance (informational)",
    ),
    "text-lines": CheckCapability(
        name="text-lines",
        policy_kind="scored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Text line-count agreement fraction (informational)",
    ),
    "group-padding": CheckCapability(
        name="group-padding",
        policy_kind="scored",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Group-padding delta (informational)",
    ),
    "crossing-count": CheckCapability(
        name="crossing-count",
        policy_kind="scored",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Edge crossing count delta (informational)",
    ),
    "bend-count": CheckCapability(
        name="bend-count",
        policy_kind="scored",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Mean absolute relation bend-count delta (informational)",
    ),
    "whitespace-density": CheckCapability(
        name="whitespace-density",
        policy_kind="scored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Whitespace / density delta (informational)",
    ),
    "endpoint-side": CheckCapability(
        name="endpoint-side",
        policy_kind="scored",
        supported_diagram_families=_FLOWCHART_ARCH,
        description="Relation endpoint attachment-side agreement (informational)",
    ),
    # ── ignored checks ─────────────────────────────────────────────────────────
    "palette": CheckCapability(
        name="palette",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Color palette differences — ignored",
    ),
    "shadow": CheckCapability(
        name="shadow",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Drop shadows — ignored",
    ),
    "corner-radius": CheckCapability(
        name="corner-radius",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Corner rounding — ignored",
    ),
    "raw-dom-structure": CheckCapability(
        name="raw-dom-structure",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Raw SVG/DOM structure — ignored",
    ),
    "raw-pixels": CheckCapability(
        name="raw-pixels",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Pixel-exact rendering — ignored",
    ),
    "font-glyph": CheckCapability(
        name="font-glyph",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="Font glyph rendering — ignored",
    ),
    "animation": CheckCapability(
        name="animation",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="CSS animations — ignored",
    ),
    "transition": CheckCapability(
        name="transition",
        policy_kind="ignored",
        supported_diagram_families=_ALL_FAMILIES,
        description="CSS transitions — ignored",
    ),
}


def get_capability(name: str) -> CheckCapability:
    """Return the CheckCapability for the given check name.

    Raises ValueError when the name is unknown.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown check name {name!r}. "
            f"Known checks: {sorted(_REGISTRY)}"
        )


def all_check_names() -> frozenset[str]:
    """Return all registered check names."""
    return frozenset(_REGISTRY)


def strict_check_names() -> frozenset[str]:
    return frozenset(n for n, c in _REGISTRY.items() if c.policy_kind == "strict")


def scored_check_names() -> frozenset[str]:
    return frozenset(n for n, c in _REGISTRY.items() if c.policy_kind == "scored")


def ignored_check_names() -> frozenset[str]:
    return frozenset(n for n, c in _REGISTRY.items() if c.policy_kind == "ignored")

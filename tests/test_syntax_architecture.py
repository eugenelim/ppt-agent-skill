#!/usr/bin/env python3
"""Architecture-beta diagram syntax coverage tests.

Covers documented architecture-beta syntax via to_html(src) -> HTML assertions.

The architecture-beta directive IS supported by the pure-Python renderer
(_strategies._layout_architecture, dispatched at _dispatch line ~1893).

Key behaviours probed:
  - Basic service layout (services become nodes; labels appear in HTML output)
  - data-node-id attributes on service nodes
  - group containment (group labels appear, services in group render)
  - Directional edge syntax: src:SIDE --> SIDE:dst for all four sides (T/B/L/R)
  - Bidirectional edge <-->
  - Undirected edge --
  - Reverse edge <-- (regex does not match; edge dropped silently, no error)
  - Built-in icon names: cloud, database, disk, internet, server — do not crash
  - junction id — creates a group, does not crash when services are present
  - No services raises ValueError

Import note: `to_html` lives on `mermaid_render`, not `mermaid_layout`
(the latter is a backward-compat shim that does not re-export `to_html`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── TestArchitectureBasic ─────────────────────────────────────────────────────


class TestArchitectureBasic:
    def test_single_service_renders(self):
        """A single service declaration renders without error."""
        src = "architecture-beta\n  service db(database)[Database]\n"
        html = to_html(src)
        assert html
        assert "mermaid-layout" in html

    def test_service_label_in_output(self):
        """Service label text appears somewhere in the rendered HTML."""
        src = "architecture-beta\n  service db(database)[Database]\n"
        html = to_html(src)
        assert "Database" in html

    def test_multiple_service_labels_all_in_output(self):
        """All service labels from a multi-service declaration appear in output."""
        src = (
            "architecture-beta\n"
            "  service db(database)[Database]\n"
            "  service api(server)[API Server]\n"
            "  service user(internet)[User]\n"
        )
        html = to_html(src)
        assert "Database" in html
        assert "API Server" in html
        assert "User" in html

    def test_service_data_node_id_attributes(self):
        """Services produce node divs with data-node-id attributes."""
        src = (
            "architecture-beta\n"
            "  service db(database)[Database]\n"
            "  service api(server)[API Server]\n"
        )
        html = to_html(src)
        assert 'data-node-id="db"' in html
        assert 'data-node-id="api"' in html

    def test_full_documented_example_renders(self):
        """Full documented example (group + services + edges) renders without error."""
        src = (
            "architecture-beta\n"
            "  group vpc(cloud)[VPC]\n"
            "\n"
            "  service db(database)[Database] in vpc\n"
            "  service api(server)[API Server] in vpc\n"
            "  service user(internet)[User]\n"
            "\n"
            "  user:R --> L:api\n"
            "  api:R --> L:db\n"
        )
        html = to_html(src)
        assert "Database" in html
        assert "API Server" in html
        assert "User" in html

    def test_no_services_raises_value_error(self):
        """An architecture-beta with only a group and no service lines raises ValueError."""
        src = "architecture-beta\n  group vpc(cloud)[VPC]\n"
        with pytest.raises(ValueError, match="No services"):
            to_html(src)


# ── TestArchitectureGroupContainment ──────────────────────────────────────────


class TestArchitectureGroupContainment:
    def test_group_label_in_output(self):
        """Group label appears in the rendered HTML."""
        src = (
            "architecture-beta\n"
            "  group vpc(cloud)[VPC]\n"
            "  service db(database)[Database] in vpc\n"
        )
        html = to_html(src)
        assert "VPC" in html
        assert "Database" in html

    def test_multiple_groups_all_labels_present(self):
        """Multiple groups each contribute their label to the output."""
        src = (
            "architecture-beta\n"
            "  group frontend(internet)[Frontend Zone]\n"
            "  group backend(server)[Backend Zone]\n"
            "  service ui(internet)[UI] in frontend\n"
            "  service svc(server)[Service] in backend\n"
        )
        html = to_html(src)
        assert "Frontend Zone" in html
        assert "Backend Zone" in html

    def test_service_in_group_renders(self):
        """A service declared 'in <group>' renders and its label appears."""
        src = (
            "architecture-beta\n"
            "  group cloud(cloud)[Cloud Boundary]\n"
            "  service db(database)[Database] in cloud\n"
            "  service api(server)[API] in cloud\n"
        )
        html = to_html(src)
        assert "Database" in html
        assert "API" in html
        assert "Cloud Boundary" in html

    def test_service_outside_group_renders(self):
        """A service without 'in <group>' renders alongside a grouped service."""
        src = (
            "architecture-beta\n"
            "  group internal(server)[Internal]\n"
            "  service db(database)[Database] in internal\n"
            "  service user(internet)[User]\n"
        )
        html = to_html(src)
        assert "Database" in html
        assert "User" in html


# ── TestArchitectureEdges ─────────────────────────────────────────────────────


class TestArchitectureEdges:
    def test_right_to_left_edge_renders(self):
        """R --> L directional edge (user:R --> L:api) renders without error."""
        src = (
            "architecture-beta\n"
            "  service user(internet)[User]\n"
            "  service api(server)[API]\n"
            "  user:R --> L:api\n"
        )
        html = to_html(src)
        assert "User" in html
        assert "API" in html

    def test_left_to_right_edge_renders(self):
        """L --> R directional edge renders without error."""
        src = (
            "architecture-beta\n"
            "  service api(server)[API]\n"
            "  service db(database)[DB]\n"
            "  api:L --> R:db\n"
        )
        html = to_html(src)
        assert "API" in html
        assert "DB" in html

    def test_top_to_bottom_edge_renders(self):
        """T --> B directional edge renders without error."""
        src = (
            "architecture-beta\n"
            "  service a(server)[Server A]\n"
            "  service b(database)[Database B]\n"
            "  a:T --> B:b\n"
        )
        html = to_html(src)
        assert "Server A" in html
        assert "Database B" in html

    def test_bottom_to_top_edge_renders(self):
        """B --> T directional edge renders without error."""
        src = (
            "architecture-beta\n"
            "  service a(server)[Server A]\n"
            "  service b(server)[Server B]\n"
            "  a:B --> T:b\n"
        )
        html = to_html(src)
        assert "Server A" in html
        assert "Server B" in html

    def test_bidirectional_edge_renders(self):
        """<--> bidirectional edge renders without error."""
        src = (
            "architecture-beta\n"
            "  service a(server)[Service A]\n"
            "  service b(server)[Service B]\n"
            "  a:R <--> L:b\n"
        )
        html = to_html(src)
        assert "Service A" in html
        assert "Service B" in html

    def test_undirected_edge_renders(self):
        """-- undirected edge renders without error."""
        src = (
            "architecture-beta\n"
            "  service a(server)[Service A]\n"
            "  service b(server)[Service B]\n"
            "  a -- b\n"
        )
        html = to_html(src)
        assert "Service A" in html
        assert "Service B" in html

    def test_reverse_edge_does_not_raise(self):
        """<-- reverse edge: diagram renders without error (edge dropped silently).

        The _ARCH_EDGE_RE regex matches -->, <-->, and -- but not <-- alone.
        The reverse arrow line is silently ignored; nodes still render.
        """
        src = (
            "architecture-beta\n"
            "  service a(server)[Service A]\n"
            "  service b(server)[Service B]\n"
            "  a:R <-- L:b\n"
        )
        html = to_html(src)
        assert "Service A" in html
        assert "Service B" in html

    def test_chained_edges_all_nodes_present(self):
        """Chain user->api->db produces all three node labels in output."""
        src = (
            "architecture-beta\n"
            "  service user(internet)[User]\n"
            "  service api(server)[API Server]\n"
            "  service db(database)[Database]\n"
            "  user:R --> L:api\n"
            "  api:R --> L:db\n"
        )
        html = to_html(src)
        assert "User" in html
        assert "API Server" in html
        assert "Database" in html


# ── TestArchitectureBuiltinIcons ──────────────────────────────────────────────


class TestArchitectureBuiltinIcons:
    @pytest.mark.parametrize("icon_name,label", [
        ("cloud",    "Cloud Service"),
        ("database", "Database Node"),
        ("disk",     "Disk Storage"),
        ("internet", "Internet Gateway"),
        ("server",   "App Server"),
    ])
    def test_builtin_icon_does_not_raise(self, icon_name, label):
        """Each documented built-in icon name can be used in a service declaration."""
        src = (
            "architecture-beta\n"
            f"  service svc({icon_name})[{label}]\n"
        )
        html = to_html(src)
        assert label in html, f"label {label!r} missing for icon {icon_name!r}"


# ── TestArchitectureJunction ──────────────────────────────────────────────────


class TestArchitectureJunction:
    def test_junction_with_services_renders_without_error(self):
        """junction creates an invisible routing group; diagram renders with services present."""
        src = (
            "architecture-beta\n"
            "  service a(server)[Server A]\n"
            "  service b(server)[Server B]\n"
            "  junction junc1\n"
        )
        html = to_html(src)
        assert "Server A" in html
        assert "Server B" in html

    def test_junction_only_raises_value_error(self):
        """A diagram with only a junction (no services) raises ValueError."""
        src = "architecture-beta\n  junction junc1\n"
        with pytest.raises(ValueError, match="No services"):
            to_html(src)

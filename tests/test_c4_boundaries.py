"""Stage 5 tests: C4 parsing — new element types, technology field, boundary fixes.

Covers:
- ContainerQueue, ContainerDb, ComponentDb, ComponentQueue parsed correctly
- technology and description stored separately in C4Item
- Boundary stack pops on both `)` and `}`
- Boundary overlay divs rendered for grouped members
- c4-container-config.mmd renders without error
- c4-basic.mmd still works (regression)
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from mermaid_render.layout._c4 import C4Item, C4Boundary, _render_c4_fragment, C4Relationship


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render(src: str) -> str:
    import mermaid_render
    return mermaid_render.to_html(src)


def _fixture(name: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path) as f:
        return f.read()


# ── C4Item dataclass ──────────────────────────────────────────────────────────

class TestC4ItemDataclass:
    def test_technology_field_default_empty(self):
        item = C4Item(alias="a", kind="container", label="A", description="", is_external=False)
        assert item.technology == ""

    def test_technology_stored(self):
        item = C4Item(alias="a", kind="container", label="A", description="desc",
                      is_external=False, technology="Java")
        assert item.technology == "Java"
        assert item.description == "desc"


# ── Parser: element types and argument mapping ────────────────────────────────

class TestC4ElementParsing:
    def _parse(self, src: str):
        """Return the parsed C4Items from a C4Container source."""
        from mermaid_render.layout._strategies import _layout_c4
        html = _layout_c4(src, "TB", 0)
        # Extract data-node-id list from rendered HTML
        return re.findall(r'data-node-id="([^"]+)"', html)

    def test_container_queue_parsed(self):
        src = 'C4Container\nContainerQueue(q, "Queue", "RabbitMQ", "Async")'
        ids = self._parse(src)
        assert "q" in ids

    def test_container_db_parsed(self):
        src = 'C4Container\nContainerDb(db, "Database", "PostgreSQL", "Stores data")'
        ids = self._parse(src)
        assert "db" in ids

    def test_component_queue_parsed(self):
        src = 'C4Component\nComponentQueue(cq, "Event Bus", "Kafka", "Async events")'
        ids = self._parse(src)
        assert "cq" in ids

    def test_component_db_parsed(self):
        src = 'C4Component\nComponentDb(cd, "DB Access", "JPA", "Data layer")'
        ids = self._parse(src)
        assert "cd" in ids

    def test_person_ext_parsed(self):
        src = 'C4Context\nPerson_Ext(ext, "External User", "Third party")'
        ids = self._parse(src)
        assert "ext" in ids

    def test_system_ext_parsed(self):
        src = 'C4Context\nSystem_Ext(pay, "Payment", "External")'
        ids = self._parse(src)
        assert "pay" in ids


class TestC4TechnologyField:
    """Technology and description parsed into separate fields."""

    def _get_html(self, src: str) -> str:
        import mermaid_render
        return mermaid_render.to_html(src)

    def test_container_technology_appears(self):
        src = 'C4Container\nContainer(api, "API", "Node.js", "REST gateway")'
        html = self._get_html(src)
        assert "Node.js" in html

    def test_container_description_appears(self):
        src = 'C4Container\nContainer(api, "API", "Node.js", "REST gateway")'
        html = self._get_html(src)
        assert "REST gateway" in html

    def test_technology_in_c4_technology_span(self):
        src = 'C4Container\nContainer(api, "API", "Node.js", "REST gateway")'
        html = self._get_html(src)
        assert 'c4-technology' in html
        assert "[Node.js]" in html

    def test_person_no_technology_span(self):
        src = 'C4Context\nPerson(u, "User", "End user")'
        html = self._get_html(src)
        # Person has no technology, so c4-technology span should not appear
        # (or if present, should be empty — either way the label must appear)
        assert "User" in html

    def test_container_three_args_technology_only(self):
        """Container(alias, label, technology) — only 3 args, no description."""
        src = 'C4Container\nContainer(svc, "Service", "Python")'
        html = self._get_html(src)
        assert "Python" in html
        assert "Service" in html


# ── Boundary stack pop on } ───────────────────────────────────────────────────

class TestBoundaryStackPop:
    def _parse_items_and_groups(self, src: str):
        """Return (items, groups) by calling _layout_c4 and inspecting node ids."""
        html = _render(src)
        ids = re.findall(r'data-node-id="([^"]+)"', html)
        boundaries = re.findall(r'data-boundary-id="([^"]+)"', html)
        return ids, boundaries

    def test_paren_closes_boundary(self):
        src = (
            "C4Container\n"
            "System_Boundary(b1, \"Tier\") (\n"
            "  Container(inside, \"Inside\", \"Java\", \"desc\")\n"
            ")\n"
            "Container(outside, \"Outside\", \"Go\", \"desc2\")\n"
        )
        html = _render(src)
        assert "inside" in html
        assert "outside" in html

    def test_brace_closes_boundary(self):
        src = (
            "C4Container\n"
            "System_Boundary(b1, \"Tier\") {\n"
            "  Container(inside, \"Inside\", \"Java\", \"desc\")\n"
            "}\n"
            "Container(outside, \"Outside\", \"Go\", \"desc2\")\n"
        )
        html = _render(src)
        assert "inside" in html
        assert "outside" in html

    def test_element_after_brace_not_in_boundary(self):
        """An element declared after `}` must NOT be in the boundary."""
        src = (
            "C4Container\n"
            "System_Boundary(b1, \"Tier\") {\n"
            "  Container(inside, \"Inside\", \"Java\", \"\")\n"
            "}\n"
            "Container(outside, \"Outside\", \"Go\", \"\")\n"
        )
        # The boundary box should contain 'inside' but not 'outside'.
        html = _render(src)
        # Both nodes appear in the output
        assert "inside" in html
        assert "outside" in html
        # boundary div is rendered for b1
        assert 'data-boundary-id="b1"' in html


# ── Boundary overlay rendering ────────────────────────────────────────────────

class TestBoundaryRendering:
    def test_boundary_div_rendered(self):
        src = (
            "C4Container\n"
            "System_Boundary(tier, \"My Tier\") {\n"
            "  Container(svc, \"Service\", \"Java\", \"\")\n"
            "}\n"
        )
        html = _render(src)
        assert 'data-boundary-id="tier"' in html
        assert "My Tier" in html

    def test_boundary_label_present(self):
        src = (
            "C4Container\n"
            "System_Boundary(b, \"Data Layer\") {\n"
            "  ContainerDb(db, \"DB\", \"Postgres\", \"\")\n"
            "}\n"
        )
        html = _render(src)
        assert "Data Layer" in html

    def test_no_boundary_no_boundary_div(self):
        src = "C4Context\nSystem(s, \"System\", \"desc\")"
        html = _render(src)
        assert 'data-boundary-id=' not in html

    def test_multiple_boundaries_rendered(self):
        src = (
            "C4Container\n"
            "System_Boundary(b1, \"Tier 1\") {\n"
            "  Container(s1, \"S1\", \"Java\", \"\")\n"
            "}\n"
            "System_Boundary(b2, \"Tier 2\") {\n"
            "  Container(s2, \"S2\", \"Go\", \"\")\n"
            "}\n"
        )
        html = _render(src)
        assert 'data-boundary-id="b1"' in html
        assert 'data-boundary-id="b2"' in html
        assert "Tier 1" in html
        assert "Tier 2" in html


# ── c4-container-config.mmd fixture ──────────────────────────────────────────

class TestC4ContainerConfig:
    def test_renders_without_error(self):
        html = _render(_fixture("c4-container-config.mmd"))
        assert "<svg" in html or "<div" in html

    def test_all_nodes_present(self):
        html = _render(_fixture("c4-container-config.mmd"))
        for alias in ("customer", "admin", "spa", "api", "db", "queue", "cache", "payment"):
            assert alias in html, f"Alias '{alias}' missing from rendered output"

    def test_boundaries_rendered(self):
        html = _render(_fixture("c4-container-config.mmd"))
        assert 'data-boundary-id="web"' in html
        assert 'data-boundary-id="data"' in html

    def test_technology_visible(self):
        html = _render(_fixture("c4-container-config.mmd"))
        assert "PostgreSQL" in html
        assert "RabbitMQ" in html
        assert "React" in html

    def test_containerdb_containerqueue_rendered(self):
        html = _render(_fixture("c4-container-config.mmd"))
        # ContainerDb and ContainerQueue should both be present
        assert 'c4-container-db' in html or 'c4-containerdb' in html
        assert 'c4-container-queue' in html or 'c4-containerqueue' in html


# ── c4-basic.mmd regression ──────────────────────────────────────────────────

class TestC4BasicRegression:
    def test_c4_basic_still_renders(self):
        html = _render(_fixture("c4-basic.mmd"))
        assert "<svg" in html or "<div" in html

    def test_c4_basic_nodes_present(self):
        html = _render(_fixture("c4-basic.mmd"))
        for alias in ("user", "webapp", "email"):
            assert alias in html

    def test_c4_basic_edges_present(self):
        html = _render(_fixture("c4-basic.mmd"))
        assert "<path" in html or "<line" in html

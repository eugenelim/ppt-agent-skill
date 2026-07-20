#!/usr/bin/env python3
"""ER diagram syntax coverage tests for the mermaid_render layout engine.

Covers every documented erDiagram syntax behavior:
- Basic entity/relationship rendering
- All cardinality token combinations
- Solid vs. dashed relationship types
- Entity attribute blocks (PK, FK, UK, comments)
- Relationship labels (quoted and unquoted)
- Edge cases: standalone entity, empty diagram, hyphenated names

Import note: ``to_html`` lives in ``mermaid_render``, not ``mermaid_layout``
(the latter is a shim to ``mermaid_render.layout`` which does not re-export
``to_html``). We import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


def _er(body: str) -> str:
    """Render a snippet of erDiagram body lines via to_html."""
    return to_html(f"erDiagram\n{body}")


# ── TestERBasic ───────────────────────────────────────────────────────────────


class TestERBasic:
    def test_simple_relationship_renders(self):
        """Two entities connected by a relationship appear in the HTML."""
        html = _er("  CUSTOMER ||--o{ ORDER : places")
        assert "CUSTOMER" in html
        assert "ORDER" in html

    def test_entity_node_id_attributes(self):
        """Both entities produce node divs with data-node-id attributes."""
        html = _er("  CUSTOMER ||--o{ ORDER : places")
        assert 'data-node-id="CUSTOMER"' in html
        assert 'data-node-id="ORDER"' in html

    def test_multiple_relationships_all_entities_present(self):
        """Multiple relationship lines each register all involved entities."""
        html = _er(
            "  CUSTOMER ||--o{ ORDER : places\n"
            "  ORDER ||--|{ LINE_ITEM : contains"
        )
        assert "CUSTOMER" in html
        assert "ORDER" in html
        assert "LINE_ITEM" in html

    def test_output_is_html_document(self):
        """to_html returns a full HTML document wrapping the diagram fragment."""
        html = _er("  A ||--|| B : rel")
        assert html.lstrip().startswith("<!DOCTYPE") or "<html" in html

    def test_diagram_class_present(self):
        """The rendered fragment contains the 'diagram mermaid-layout' class."""
        html = _er("  A ||--|| B : rel")
        assert "diagram mermaid-layout" in html

    def test_empty_diagram_raises_value_error(self):
        """A diagram with no parseable entities raises ValueError."""
        with pytest.raises(ValueError, match="No entities"):
            to_html("erDiagram\n  %% comment only")


# ── TestERCardinality ─────────────────────────────────────────────────────────


class TestERCardinality:
    @pytest.mark.parametrize("card_src,card_dst,desc", [
        ("||", "||",  "one-to-one"),
        ("||", "o{",  "one-to-zero-or-many"),
        ("||", "|{",  "one-to-one-or-many"),
        ("||", "|o",  "one-to-zero-or-one"),
        ("}|", "||",  "many-to-one"),
        ("}o", "||",  "zero-or-many-to-one"),
        ("o|", "||",  "zero-or-one-to-one"),
        ("}|", "o{",  "many-to-zero-or-many"),
        ("}o", "o{",  "zero-or-many-to-zero-or-many"),
        ("}o", "|{",  "zero-or-many-to-one-or-many"),
        ("o|", "|o",  "zero-or-one-to-zero-or-one"),
    ])
    def test_cardinality_token_combo_renders(self, card_src, card_dst, desc):
        """Every documented cardinality token combination renders without raising."""
        html = _er(f"  ENTITY_A {card_src}--{card_dst} ENTITY_B : rel")
        assert "ENTITY_A" in html, f"{desc}: ENTITY_A missing"
        assert "ENTITY_B" in html, f"{desc}: ENTITY_B missing"

    def test_crow_foot_markers_injected_into_svg(self):
        """Crow-foot SVG markers are injected for zero-many cardinality (circle element)."""
        html = _er("  A ||--o{ B : rel")
        # zero-many (o{) produces a circle for the zero indicator
        assert "<circle" in html

    def test_exactly_one_both_sides_produces_tick_lines(self):
        """Exactly-one (||) on both sides produces tick mark SVG lines."""
        html = _er("  A ||--|| B : rel")
        # each "one" produces a perpendicular line; SVG overlay must be present
        assert "<svg" in html
        assert "<line" in html


# ── TestERRelationshipType ────────────────────────────────────────────────────


class TestERRelationshipType:
    def test_solid_identifying_line(self):
        """Solid relationship (--) renders without error and includes both entities."""
        html = _er("  A ||--|| B : links")
        assert "A" in html
        assert "B" in html

    def test_dashed_non_identifying_line(self):
        """Dashed / non-identifying relationship (..) renders without error."""
        html = _er("  A ||..|| B : links")
        assert "A" in html
        assert "B" in html

    def test_mixed_solid_and_dashed_in_one_diagram(self):
        """Diagrams that mix solid and dashed relationships render all entities."""
        html = _er(
            "  A ||--|| B : solid_rel\n"
            "  B ||..o{ C : dashed_rel"
        )
        assert "A" in html
        assert "B" in html
        assert "C" in html

    def test_dashed_one_to_many(self):
        """Dashed one-to-many ('..|{') combination renders correctly."""
        html = _er("  A ||..|{ B : rel")
        assert "A" in html
        assert "B" in html


# ── TestERAttributes ──────────────────────────────────────────────────────────


class TestERAttributes:
    def test_pk_attribute_no_crash(self):
        """Entity attribute block with PK marker is accepted."""
        src = (
            "  CUSTOMER {\n"
            "    int customerId PK\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "CUSTOMER" in html

    def test_fk_attribute_no_crash(self):
        """Entity attribute block with FK marker is accepted."""
        src = (
            "  ORDER {\n"
            "    int customerId FK\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "ORDER" in html

    def test_uk_attribute_no_crash(self):
        """Entity attribute block with UK (unique key) marker is accepted."""
        src = (
            "  CUSTOMER {\n"
            "    string email UK\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "CUSTOMER" in html

    def test_multiple_constraint_markers_in_one_block(self):
        """Entity with PK, FK, and UK annotations all in one block renders."""
        src = (
            "  CUSTOMER {\n"
            "    int customerId PK\n"
            "    string email UK\n"
            "    int accountId FK\n"
            "    string name\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "CUSTOMER" in html

    def test_attribute_content_embedded_in_label(self):
        """Attribute lines are concatenated into the node's pipe-separated label."""
        src = (
            "  CUSTOMER {\n"
            "    string name\n"
            "    int customerId PK\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        # Attribute content appears somewhere in the rendered HTML
        assert "customerId" in html

    def test_attribute_comment_no_crash(self):
        """Quoted inline comment after attribute type and name is accepted."""
        src = (
            "  CUSTOMER {\n"
            '    string name "the customer name"\n'
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "CUSTOMER" in html

    def test_attribute_comment_content_in_output(self):
        """Quoted comment text appears somewhere in the rendered HTML."""
        src = (
            "  CUSTOMER {\n"
            '    string name "the customer name"\n'
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "customer name" in html

    def test_standalone_entity_block_renders(self):
        """An entity with only an attribute block (no relationship line) renders.

        The entity block creates the node; no relationship is required for
        the renderer to produce output.
        """
        src = (
            "  CUSTOMER {\n"
            "    int customerId PK\n"
            "    string name\n"
            "  }"
        )
        html = _er(src)
        assert "CUSTOMER" in html

    def test_multiple_entity_blocks_with_shared_relationship(self):
        """Two entity blocks plus a relationship line all render correctly."""
        src = (
            "  CUSTOMER {\n"
            "    int customerId PK\n"
            "    string email FK\n"
            "    date createdAt\n"
            "  }\n"
            "  ORDER {\n"
            "    int orderId PK\n"
            "    int customerId FK\n"
            "  }\n"
            "  CUSTOMER ||--o{ ORDER : places"
        )
        html = _er(src)
        assert "CUSTOMER" in html
        assert "ORDER" in html
        assert "customerId" in html


# ── TestERRelationshipLabels ──────────────────────────────────────────────────


class TestERRelationshipLabels:
    def test_unquoted_single_word_label_in_output(self):
        """An unquoted single-word label appears as data-edge-label in the HTML."""
        html = _er("  CUSTOMER ||--o{ ORDER : places")
        assert 'data-edge-label="places"' in html

    def test_quoted_multiword_label_no_crash(self):
        """A quoted multi-word label is accepted without raising."""
        html = _er('  CUSTOMER ||--o{ ORDER : "places order"')
        assert "CUSTOMER" in html
        assert "ORDER" in html

    def test_quoted_multiword_label_appears_in_output(self):
        """The text of a quoted label appears somewhere in the rendered HTML."""
        html = _er('  CUSTOMER ||--o{ ORDER : "places order"')
        assert "places order" in html

    def test_empty_label_no_crash(self):
        """An empty label (': ' with no text) is accepted without raising."""
        html = _er("  A ||--|| B : ")
        assert "A" in html
        assert "B" in html

    def test_multiple_relationships_each_have_edge_label(self):
        """Each labeled relationship produces its own data-edge-label attribute."""
        html = _er(
            "  CUSTOMER ||--o{ ORDER : places\n"
            "  ORDER ||--|{ LINE_ITEM : contains"
        )
        assert 'data-edge-label="places"' in html
        assert 'data-edge-label="contains"' in html


# ── TestERHyphenatedEntityName ────────────────────────────────────────────────


class TestERHyphenatedEntityName:
    def test_hyphenated_entity_mixed_diagram_valid_entities_render(self):
        """Valid entities from other lines still render when a hyphenated-name
        relationship line is silently skipped by the \\w+ entity-ID regex.
        """
        src = (
            "  CUSTOMER ||--o{ ORDER : places\n"
            "  LINE-ITEM ||--|| ORDER : belongs"
        )
        html = _er(src)
        assert "CUSTOMER" in html
        assert "ORDER" in html

    def test_hyphenated_entity_only_raises_value_error(self):
        """A diagram containing only a hyphenated-entity relationship raises ValueError.

        The line is not parseable (\\w+ cannot match LINE-ITEM), so no nodes
        are registered and the renderer raises 'No entities found'.
        """
        with pytest.raises(ValueError, match="No entities"):
            to_html("erDiagram\n  LINE-ITEM ||--|| ORDER : belongs")

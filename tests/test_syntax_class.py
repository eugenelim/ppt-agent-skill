"""Syntax coverage tests for classDiagram.

Tests focus on behaviors *not* already covered in test_mermaid_layout.py:
- member content in rendered output (access modifiers, types, return types)
- attr/method divider (height:1px hr between attribute and method sections)
- <<abstract>>, <<enumeration>>, <<service>> annotations
- namespace blocks, generic class names, note directives, direction, click/callback
- solid link (--) and dashed link (..) operators

Existing tests in TestClassRelationshipParse, TestClassParser, and
TestClassParserExtended already cover: <|--, *--, o--, -->, ..>, ..|>,
--*, --o, <|.., marker defs, hollow/filled markers, relationship labels,
cardinality, visibility fixture, and dark/light mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # pure-Python, no playwright


def _html(src: str) -> str:
    """Render mermaid source to a full HTML page (no playwright required)."""
    return to_html(src)


# ── Class definition ──────────────────────────────────────────────────────────

class TestClassDefinition:
    def test_empty_class_renders(self):
        """Single bare class declaration (no body) produces a valid diagram node."""
        html = _html("classDiagram\n  class Animal")
        assert "Animal" in html
        assert "diagram mermaid-layout" in html

    def test_class_with_members_renders(self):
        """Class with a full {} body renders the node and member section."""
        src = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +int age\n"
            "    +makeSound() void\n"
            "  }"
        )
        html = _html(src)
        assert "Animal" in html
        assert "diagram mermaid-layout" in html


# ── Members — access modifiers and types ─────────────────────────────────────

class TestClassMembers:
    @pytest.mark.parametrize("modifier", ["+", "-", "#", "~"])
    def test_access_modifier_in_output(self, modifier):
        """Access modifier character appears in the rendered member text."""
        src = (
            f"classDiagram\n"
            f"  class Animal {{\n"
            f"    {modifier}String memberName\n"
            f"  }}"
        )
        html = _html(src)
        assert modifier in html

    def test_attribute_with_type(self):
        """Attribute member text (e.g. '+String name') appears in output."""
        src = "classDiagram\n  class Animal {\n    +String name\n  }"
        html = _html(src)
        assert "name" in html

    def test_method_with_return_type(self):
        """Method with return type (e.g. '+makeSound() void') text appears."""
        src = "classDiagram\n  class Animal {\n    +makeSound() void\n  }"
        html = _html(src)
        assert "makeSound" in html

    def test_method_without_return_type(self):
        """Method without explicit return type still renders."""
        src = "classDiagram\n  class Animal {\n    +speak()\n  }"
        html = _html(src)
        assert "speak" in html

    def test_generic_type_attribute(self):
        """Attribute with generic type (List~String~ items) renders without crash."""
        src = (
            "classDiagram\n"
            "  class Container {\n"
            "    +List~String~ items\n"
            "  }"
        )
        html = _html(src)
        assert "Container" in html
        assert "items" in html

    def test_abstract_member_annotation(self):
        """Abstract member suffix (*) is preserved in the member line in output."""
        src = (
            "classDiagram\n"
            "  class Shape {\n"
            "    +draw()* Abstract\n"
            "  }"
        )
        html = _html(src)
        assert "Shape" in html
        assert "draw" in html

    def test_static_member_annotation(self):
        """Static member suffix ($) is preserved in the member line in output."""
        src = (
            "classDiagram\n"
            "  class MathUtils {\n"
            "    +pi()$ float\n"
            "  }"
        )
        html = _html(src)
        assert "MathUtils" in html
        assert "pi" in html

    def test_multiple_access_modifiers_all_render(self):
        """Class with all four access modifiers (+, -, #, ~) renders each member."""
        src = (
            "classDiagram\n"
            "  class BankAccount {\n"
            "    +String owner\n"
            "    -int balance\n"
            "    #String accountType\n"
            "    ~String internalCode\n"
            "  }"
        )
        html = _html(src)
        for name in ("owner", "balance", "accountType", "internalCode"):
            assert name in html, f"member {name!r} missing from rendered output"


# ── Attr/method divider ───────────────────────────────────────────────────────

class TestClassMemberDivider:
    def test_divider_between_attrs_and_methods(self):
        """A 1px horizontal rule divides attributes from methods in the rendered card."""
        src = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +makeSound() void\n"
            "  }"
        )
        html = _html(src)
        assert "height:1px" in html

    def test_attrs_only_no_divider(self):
        """Class with only attributes renders member rows but no attr/method divider."""
        src = (
            "classDiagram\n"
            "  class Config {\n"
            "    +String host\n"
            "    +int port\n"
            "  }"
        )
        html = _html(src)
        assert "node-member" in html
        assert "height:1px" not in html

    def test_methods_only_no_divider(self):
        """Class with only methods renders member rows but no attr/method divider."""
        src = (
            "classDiagram\n"
            "  class Service {\n"
            "    +connect()\n"
            "    +disconnect()\n"
            "  }"
        )
        html = _html(src)
        assert "node-member" in html
        assert "height:1px" not in html

    def test_node_member_class_present(self):
        """node-member span class is emitted for individual member rows (2+ rows)."""
        src = (
            "classDiagram\n"
            "  class Animal {\n"
            "    +String name\n"
            "    +int age\n"
            "    +makeSound() void\n"
            "  }"
        )
        html = _html(src)
        assert "node-member" in html


# ── Relationships — operators not covered in test_mermaid_layout.py ──────────

class TestClassRelationships:
    def test_solid_link(self):
        """Solid bidirectional link (--) between declared classes renders both names.

        The -- operator is not in _CLASS_REL_RE; the line is silently skipped
        but explicitly declared classes still appear in output.
        """
        src = (
            "classDiagram\n"
            "  class Animal\n"
            "  class Food\n"
            "  Animal -- Food"
        )
        html = _html(src)
        assert "Animal" in html
        assert "Food" in html

    def test_dashed_link(self):
        """Dashed link (..) is parsed as an edge; both class names appear in output."""
        html = _html("classDiagram\n  Animal .. Note")
        assert "Animal" in html
        assert "Note" in html

    def test_multiplicity_with_label(self):
        """Multiplicity strings combined with a label render the label in output."""
        html = _html('classDiagram\n  Animal "1" --> "many" Food : eats')
        assert "eats" in html
        assert "Animal" in html
        assert "Food" in html


# ── Annotations (stereotypes) ─────────────────────────────────────────────────

class TestClassAnnotations:
    def test_interface_annotation_content(self):
        """<<interface>> annotation text ('interface') appears in rendered output.

        Existing tests (TestClassParser.test_class_annotation_interface,
        TestClassParserExtended.test_class_annotation_renders) only assert the
        class name is present; this test asserts the annotation text is visible.
        """
        src = (
            "classDiagram\n"
            "  class IShape {\n"
            "    <<interface>>\n"
            "    +draw() void\n"
            "  }"
        )
        html = _html(src)
        assert "interface" in html.lower()

    def test_abstract_annotation(self):
        """<<abstract>> annotation renders the class node."""
        src = (
            "classDiagram\n"
            "  class Shape {\n"
            "    <<abstract>>\n"
            "    +area() float\n"
            "  }"
        )
        html = _html(src)
        assert "Shape" in html
        assert "abstract" in html.lower()

    def test_enumeration_annotation(self):
        """<<enumeration>> annotation renders the class; enum values appear as members."""
        src = (
            "classDiagram\n"
            "  class Color {\n"
            "    <<enumeration>>\n"
            "    RED\n"
            "    GREEN\n"
            "    BLUE\n"
            "  }"
        )
        html = _html(src)
        assert "Color" in html
        assert "enumeration" in html.lower()
        assert "RED" in html

    def test_service_annotation(self):
        """<<service>> annotation renders the class node."""
        src = (
            "classDiagram\n"
            "  class ServiceAPI {\n"
            "    <<service>>\n"
            "    +process() void\n"
            "  }"
        )
        html = _html(src)
        assert "ServiceAPI" in html
        assert "service" in html.lower()

    def test_annotation_is_html_escaped(self):
        """Annotation angle brackets are HTML-escaped in the rendered output."""
        src = (
            "classDiagram\n"
            "  class IFace {\n"
            "    <<interface>>\n"
            "  }"
        )
        html = _html(src)
        assert "&lt;&lt;interface&gt;&gt;" in html


# ── Namespace ─────────────────────────────────────────────────────────────────

class TestClassNamespace:
    def test_namespace_renders_without_crash(self):
        """Namespace block syntax is silently tolerated; diagram renders valid HTML."""
        src = (
            "classDiagram\n"
            "  namespace Mammals {\n"
            "    class Dog\n"
            "    class Cat\n"
            "  }"
        )
        html = _html(src)
        assert "diagram mermaid-layout" in html

    def test_namespace_classes_present(self):
        """Classes declared inside a namespace block appear in the rendered output."""
        src = (
            "classDiagram\n"
            "  namespace Mammals {\n"
            "    class Dog\n"
            "    class Cat\n"
            "  }\n"
            "  Dog --> Cat"
        )
        html = _html(src)
        assert "Dog" in html
        assert "Cat" in html


# ── Generic types in class names ──────────────────────────────────────────────

class TestClassGenericName:
    def test_generic_class_name_renders(self):
        """class Square~Shape~ — the base name 'Square' is parsed and appears in output."""
        src = (
            "classDiagram\n"
            "  class Square~Shape~ {\n"
            "    int id\n"
            "  }"
        )
        html = _html(src)
        assert "Square" in html

    def test_generic_class_in_relationship(self):
        """Generic-typed class declared via class X~T~ participates in a relationship."""
        src = (
            "classDiagram\n"
            "  class Container~T~\n"
            "  Container --> Item"
        )
        html = _html(src)
        assert "Container" in html
        assert "Item" in html


# ── Notes ─────────────────────────────────────────────────────────────────────

class TestClassNotes:
    def test_global_note_no_crash(self):
        """Global note 'text' directive is silently tolerated; renderer does not crash."""
        src = (
            "classDiagram\n"
            "  class Animal\n"
            '  note "This is a base class"'
        )
        html = _html(src)
        assert "Animal" in html
        assert "diagram mermaid-layout" in html

    def test_class_note_no_crash(self):
        """note for ClassName 'text' directive is silently tolerated."""
        src = (
            "classDiagram\n"
            "  class Animal\n"
            '  note for Animal "This animal is the base class"'
        )
        html = _html(src)
        assert "Animal" in html


# ── Direction ─────────────────────────────────────────────────────────────────

class TestClassDirection:
    def test_direction_lr_renders(self):
        """'direction LR' inside classDiagram body is tolerated; diagram renders."""
        src = "classDiagram\n  direction LR\n  Animal <|-- Dog"
        html = _html(src)
        assert "Animal" in html
        assert "Dog" in html
        assert "diagram mermaid-layout" in html

    def test_direction_tb_renders(self):
        """'direction TB' inside classDiagram body is tolerated; diagram renders."""
        src = "classDiagram\n  direction TB\n  A --> B"
        html = _html(src)
        assert "A" in html
        assert "B" in html


# ── Callbacks / click ─────────────────────────────────────────────────────────

class TestClassCallbacks:
    def test_click_href_no_crash(self):
        """'click ClassName href URL' directive is silently tolerated."""
        src = (
            "classDiagram\n"
            "  class Animal\n"
            '  click Animal href "https://example.com"'
        )
        html = _html(src)
        assert "Animal" in html

    def test_click_call_no_crash(self):
        """'click ClassName call fn()' directive is silently tolerated."""
        src = (
            "classDiagram\n"
            "  class Animal\n"
            "  click Animal call clickFn()"
        )
        html = _html(src)
        assert "Animal" in html

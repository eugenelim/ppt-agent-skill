#!/usr/bin/env python3
"""Pytest tests for ZenUML sequence diagram syntax coverage.

ZenUML diagrams use the ``zenuml`` keyword.  ``zenuml`` is NOT listed in
the explicit dispatch table of ``mermaid_render.layout._strategies._dispatch``
(and is not in ``_KNOWN_DIRECTIVES``), so it falls through to the
**unknown-directive graph-topology best-effort fallback**.  That fallback
successfully extracts partial nodes from ZenUML method-call syntax — for
example ``Alice.request(data) {`` is parsed as a node named ``Alice.request``
— and returns a rendered HTML document.  **No ValueError is raised.**

These tests:

1. Document all real ZenUML syntax variants (as fixture constants and
   docstrings), so the contract is readable without consulting the mermaid.js
   docs.
2. Assert that each variant renders without raising.
3. Assert structural invariants: the output is a full HTML document, contains
   the ``diagram mermaid-layout`` CSS class, and embeds actor/method names
   extracted by the fallback parser.

ZenUML syntax reference (mermaid.js docs)
------------------------------------------
::

    zenuml
      @Actor Alice
      @Database DB
      Alice.request(data) {
        DB.query(sql)
        return result
      }
      if(condition) {
        Alice->notify()
      } else {
        Alice->skip()
      }
      par {
        Alice.ping()
        DB.check()
      }
      try {
        Alice.call()
      } catch {
        Alice.handle()
      } finally {
        Alice.cleanup()
      }
      while(running) {
        Alice.poll()
      }
      for(item: list) {
        Alice.process(item)
      }

Key features:
- ``@Actor`` / ``@Database`` annotation types
- Method calls with ``{}`` body blocks
- Explicit arrow ``->`` for fire-and-forget calls
- Control flow: ``if/else``, ``par``, ``try/catch/finally``, ``while``,
  ``for``, ``forEach``, ``opt``, ``loop``
- Line comments with ``//``

Import pattern mirrors ``tests/test_syntax_pie.py``: ``sys.path.insert`` so
the test is self-contained and does not require conftest.py adjustments.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture sources — each constant documents one syntax variant
# ---------------------------------------------------------------------------

# Minimal: two participants, one method call with body, explicit return.
ZENUML_BASIC_CALL = """zenuml
  @Actor Alice
  @Database DB
  Alice.request(data) {
    DB.query(sql)
    return result
  }"""

# @Actor and @Database annotation types side-by-side, explicit -> arrow.
ZENUML_ANNOTATIONS = """zenuml
  @Actor Alice
  @Database DB
  Alice->DB.ping()"""

# Explicit arrow (fire-and-forget, no body block) between two @Actor participants.
ZENUML_ARROW_CALL = """zenuml
  @Actor Alice
  @Actor Bob
  Alice->Bob.notify()"""

# if / else control flow block.
ZENUML_IF_ELSE = """zenuml
  @Actor Alice
  if(condition) {
    Alice->notify()
  } else {
    Alice->skip()
  }"""

# par (parallel) block — two simultaneous calls.
ZENUML_PAR = """zenuml
  @Actor Alice
  @Database DB
  par {
    Alice.ping()
    DB.check()
  }"""

# try / catch / finally control flow.
ZENUML_TRY_CATCH_FINALLY = """zenuml
  @Actor Alice
  try {
    Alice.call()
  } catch {
    Alice.handle()
  } finally {
    Alice.cleanup()
  }"""

# while loop.
ZENUML_WHILE = """zenuml
  @Actor Alice
  while(running) {
    Alice.poll()
  }"""

# for loop.
ZENUML_FOR = """zenuml
  @Actor Alice
  for(item: list) {
    Alice.process(item)
  }"""

# Full real-world example: annotations + all control flow blocks (nested).
ZENUML_NESTED_CALLS = """zenuml
  @Actor Alice
  @Database DB
  Alice.request(data) {
    DB.query(sql)
    return result
  }
  if(condition) {
    Alice->notify()
  } else {
    Alice->skip()
  }
  par {
    Alice.ping()
    DB.check()
  }"""

# Comment lines (// syntax).
ZENUML_WITH_COMMENTS = """zenuml
  // This is a comment
  @Actor Alice
  @Actor Bob
  Alice->Bob.hello()"""

# forEach loop variant.
ZENUML_FOR_EACH = """zenuml
  @Actor Alice
  forEach(item: collection) {
    Alice.process(item)
  }"""

# opt block (optional interaction).
ZENUML_OPT = """zenuml
  @Actor Alice
  opt(condition) {
    Alice.optionalCall()
  }"""

# loop block.
ZENUML_LOOP = """zenuml
  @Actor Alice
  loop(5) {
    Alice.repeat()
  }"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _data_node_ids(html: str) -> list[str]:
    """Return all data-node-id attribute values from rendered HTML."""
    return re.findall(r'data-node-id="([^"]+)"', html)


# ---------------------------------------------------------------------------
# Tests — basic call
# ---------------------------------------------------------------------------

class TestZenUMLBasicCall:
    """Method calls with body blocks render via best-effort graph-topology fallback."""

    def test_basic_call_does_not_raise(self):
        """to_html does not raise for a basic method-call-with-body zenuml source."""
        html = to_html(ZENUML_BASIC_CALL)
        assert html

    def test_basic_call_returns_html_document(self):
        """Output is a full standalone HTML document."""
        html = to_html(ZENUML_BASIC_CALL)
        assert html.lstrip().startswith("<!DOCTYPE html") or "<html" in html

    def test_basic_call_mermaid_layout_class(self):
        """Rendered fragment carries the mermaid-layout CSS class."""
        html = to_html(ZENUML_BASIC_CALL)
        assert "mermaid-layout" in html

    def test_basic_call_actor_name_in_output(self):
        """Actor name 'Alice' (from method-call token) appears in rendered HTML."""
        html = to_html(ZENUML_BASIC_CALL)
        assert "Alice" in html

    def test_basic_call_database_name_in_output(self):
        """Database participant 'DB' (from method-call token) appears in rendered HTML."""
        html = to_html(ZENUML_BASIC_CALL)
        assert "DB" in html

    def test_basic_call_contains_svg(self):
        """An SVG element is present to draw edges between extracted nodes."""
        html = to_html(ZENUML_BASIC_CALL)
        assert "<svg" in html


# ---------------------------------------------------------------------------
# Tests — annotation types
# ---------------------------------------------------------------------------

class TestZenUMLAnnotations:
    """@Actor and @Database annotations are valid ZenUML; fallback renders them."""

    def test_actor_annotation_renders(self):
        """Source with @Actor annotations renders without raising."""
        html = to_html(ZENUML_ANNOTATIONS)
        assert html

    def test_actor_and_database_annotations_render(self):
        """Both @Actor and @Database annotations in one diagram render without raising."""
        html = to_html(ZENUML_ANNOTATIONS)
        assert "mermaid-layout" in html

    def test_actor_name_in_annotated_output(self):
        """Actor name from @Actor-annotated participant appears in rendered HTML."""
        html = to_html(ZENUML_ANNOTATIONS)
        assert "Alice" in html

    def test_arrow_call_renders(self):
        """Explicit fire-and-forget -> call between @Actor participants renders."""
        html = to_html(ZENUML_ARROW_CALL)
        assert html
        assert "Alice" in html


# ---------------------------------------------------------------------------
# Tests — control flow blocks
# ---------------------------------------------------------------------------

class TestZenUMLControlFlow:
    """All ZenUML control flow block keywords render via the graph-topology fallback."""

    def test_if_else_renders(self):
        """if/else block renders without raising."""
        html = to_html(ZENUML_IF_ELSE)
        assert html
        assert "mermaid-layout" in html

    def test_if_keyword_in_output(self):
        """'if' keyword appears as an extracted node in the rendered HTML."""
        html = to_html(ZENUML_IF_ELSE)
        assert "if" in html

    def test_par_block_renders(self):
        """par (parallel) block renders without raising."""
        html = to_html(ZENUML_PAR)
        assert html
        assert "mermaid-layout" in html

    def test_par_keyword_in_output(self):
        """'par' keyword appears as an extracted node in the rendered HTML."""
        html = to_html(ZENUML_PAR)
        assert "par" in html

    def test_try_catch_finally_renders(self):
        """try/catch/finally block renders without raising."""
        html = to_html(ZENUML_TRY_CATCH_FINALLY)
        assert html
        assert "mermaid-layout" in html

    def test_try_keyword_in_output(self):
        """'try' keyword appears as an extracted node in the rendered HTML."""
        html = to_html(ZENUML_TRY_CATCH_FINALLY)
        assert "try" in html

    def test_while_loop_renders(self):
        """while loop renders without raising."""
        html = to_html(ZENUML_WHILE)
        assert html
        assert "mermaid-layout" in html

    def test_while_keyword_in_output(self):
        """'while' keyword appears as an extracted node in the rendered HTML."""
        html = to_html(ZENUML_WHILE)
        assert "while" in html

    def test_for_loop_renders(self):
        """for loop renders without raising."""
        html = to_html(ZENUML_FOR)
        assert html
        assert "mermaid-layout" in html

    def test_for_keyword_in_output(self):
        """'for' keyword appears as an extracted node in the rendered HTML."""
        html = to_html(ZENUML_FOR)
        assert "for" in html

    def test_foreach_renders(self):
        """forEach loop renders without raising."""
        html = to_html(ZENUML_FOR_EACH)
        assert html

    def test_opt_block_renders(self):
        """opt (optional) block renders without raising."""
        html = to_html(ZENUML_OPT)
        assert html

    def test_loop_block_renders(self):
        """loop block renders without raising."""
        html = to_html(ZENUML_LOOP)
        assert html


# ---------------------------------------------------------------------------
# Tests — nested calls
# ---------------------------------------------------------------------------

class TestZenUMLNestedCalls:
    """Full real-world ZenUML with annotations + multiple control flow blocks."""

    def test_nested_calls_renders(self):
        """Full example with nested method calls and multiple control flow blocks renders."""
        html = to_html(ZENUML_NESTED_CALLS)
        assert html
        assert "mermaid-layout" in html

    def test_nested_calls_alice_in_output(self):
        """Actor 'Alice' from nested method calls appears in rendered HTML."""
        html = to_html(ZENUML_NESTED_CALLS)
        assert "Alice" in html

    def test_nested_calls_db_in_output(self):
        """Database 'DB' from nested method calls appears in rendered HTML."""
        html = to_html(ZENUML_NESTED_CALLS)
        assert "DB" in html

    def test_nested_calls_produces_multiple_nodes(self):
        """Full nested diagram extracts multiple node IDs from the ZenUML source."""
        html = to_html(ZENUML_NESTED_CALLS)
        node_ids = _data_node_ids(html)
        assert len(node_ids) > 1

    def test_comment_lines_do_not_crash(self):
        """ZenUML source with // comment lines renders without raising."""
        html = to_html(ZENUML_WITH_COMMENTS)
        assert html
        assert "mermaid-layout" in html

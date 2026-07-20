#!/usr/bin/env python3
"""Pytest tests for ZenUML sequence diagram syntax coverage.

ZenUML diagrams use the ``zenuml`` keyword.  As of AC-3.3 (mermaid-render-
correctness spec), ``zenuml`` is **explicitly unsupported** by the pure-Python
renderer.  ``to_html`` raises ``ValueError`` with a "not supported" message.
Use mmdc (mermaid-js CLI) for ZenUML rendering.

These tests:

1. Document all real ZenUML syntax variants (as fixture constants and
   docstrings), so the contract is readable without consulting the mermaid.js
   docs.
2. Assert that each variant raises ``ValueError`` (not a silent generic render).
3. Verify the error message references the directive name.

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
    """Method calls with body blocks raise ValueError (unsupported, AC-3.3)."""

    def test_basic_call_raises_unsupported(self):
        """Basic method-call ZenUML raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            to_html(ZENUML_BASIC_CALL)

    def test_error_message_contains_directive(self):
        """ValueError message references the zenuml directive name."""
        with pytest.raises(ValueError) as exc_info:
            to_html(ZENUML_BASIC_CALL)
        assert "zenuml" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Tests — annotation types
# ---------------------------------------------------------------------------

class TestZenUMLAnnotations:
    """@Actor and @Database annotation variants raise ValueError (unsupported)."""

    def test_actor_annotation_raises(self):
        """Source with @Actor annotations raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_ANNOTATIONS)

    def test_arrow_call_raises(self):
        """Explicit fire-and-forget -> call raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_ARROW_CALL)


# ---------------------------------------------------------------------------
# Tests — control flow blocks
# ---------------------------------------------------------------------------

class TestZenUMLControlFlow:
    """All ZenUML control flow block keywords raise ValueError (unsupported)."""

    def test_if_else_raises(self):
        """if/else block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_IF_ELSE)

    def test_par_block_raises(self):
        """par (parallel) block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_PAR)

    def test_try_catch_finally_raises(self):
        """try/catch/finally block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_TRY_CATCH_FINALLY)

    def test_while_loop_raises(self):
        """while loop raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_WHILE)

    def test_for_loop_raises(self):
        """for loop raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_FOR)

    def test_foreach_raises(self):
        """forEach loop raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_FOR_EACH)

    def test_opt_block_raises(self):
        """opt (optional) block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_OPT)

    def test_loop_block_raises(self):
        """loop block raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_LOOP)


# ---------------------------------------------------------------------------
# Tests — nested calls
# ---------------------------------------------------------------------------

class TestZenUMLNestedCalls:
    """Full real-world ZenUML — all raise ValueError (unsupported)."""

    def test_nested_calls_raises(self):
        """Full example with nested method calls raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_NESTED_CALLS)

    def test_comment_lines_raise(self):
        """ZenUML source with // comment lines raises ValueError."""
        with pytest.raises(ValueError):
            to_html(ZENUML_WITH_COMMENTS)

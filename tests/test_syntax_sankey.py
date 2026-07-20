#!/usr/bin/env python3
"""Sankey diagram (sankey-beta) syntax coverage tests.

Mermaid sankey-beta syntax reference
-------------------------------------
::

    sankey-beta
    source,target,value
    Electricity,Lighting,28.7
    Electricity,Heating,42.3
    Gas,Heating,60.0
    Nuclear,Electricity,92.9
    "Fuel, Oil",Heating,10.5
    "Fuel, Oil","Electricity Gen",0.9

Key syntax features:
- Keyword is ``sankey-beta`` (not ``sankey``).
- CSV format: three columns — ``source,target,value``.
- Values are numeric (integers or decimals).
- Sources/targets that contain commas must be double-quoted: ``"Fuel, Oil"``.
- Double-quote literal inside a quoted string uses ``""`` escaping.
- Optional ``%%{init: {...}}%%`` frontmatter configures ``linkColor``,
  ``nodeAlignment``, ``nodeWidth``, and ``nodePadding``.

Support status
--------------
``sankey-beta`` is **supported** by the pure-Python renderer via the
graph-topology fallback: ``to_html`` returns valid HTML and does not raise
``ValueError``.  The fallback parses source-column names as graph nodes; the
target column and numeric value column are not interpreted as graph edges, so
only source node names (and the literal string ``source`` from the CSV header)
appear in the rendered output.  This is a known limitation of the fallback —
mermaid.js's actual Sankey flow-band rendering is not reproduced.

Import note: ``to_html`` lives in ``mermaid_render``, not the backward-compat
``mermaid_layout`` shim.  Import directly from ``mermaid_render``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_HEADER = "sankey-beta\nsource,target,value\n"


def _sankey(body: str) -> str:
    """Render a sankey-beta diagram with a CSV body via to_html."""
    return to_html(_HEADER + body)


# ---------------------------------------------------------------------------
# TestSankeyBetaSupport — sankey-beta is supported (no ValueError)
# ---------------------------------------------------------------------------

class TestSankeyBetaSupport:
    """sankey-beta renders without raising ValueError."""

    def test_does_not_raise(self):
        """Minimal sankey-beta diagram renders without any exception."""
        _sankey("A,B,10\n")  # must not raise

    def test_returns_nonempty_html(self):
        """to_html returns a non-empty string for sankey-beta."""
        html = _sankey("A,B,10\n")
        assert html

    def test_returns_full_html_document(self):
        """to_html returns a full HTML document (not a bare fragment)."""
        html = _sankey("A,B,10\n")
        assert "<html" in html or html.lstrip().startswith("<!DOCTYPE")

    def test_diagram_class_present(self):
        """The rendered output contains the 'mermaid-layout' CSS class marker."""
        html = _sankey("A,B,10\n")
        assert "mermaid-layout" in html

    def test_not_value_error_for_basic_source(self):
        """sankey-beta with basic rows does not raise ValueError (not a rejected type)."""
        try:
            _sankey("Electricity,Lighting,28.7\n")
        except ValueError as exc:
            pytest.fail(f"to_html raised ValueError unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# TestSankeyBetaBasic — basic 3-row CSV
# ---------------------------------------------------------------------------

class TestSankeyBetaBasic:
    """Basic three-row CSV with simple alphanumeric source names."""

    _SRC = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
    )

    def test_renders_without_error(self):
        """Three data rows render without raising any exception."""
        _sankey(self._SRC)

    def test_source_names_appear_in_output(self):
        """Source column values (Electricity, Gas) appear in the rendered HTML."""
        html = _sankey(self._SRC)
        assert "Electricity" in html
        assert "Gas" in html

    def test_html_contains_svg_or_nodes(self):
        """Rendered HTML contains node or SVG elements (non-trivial output)."""
        html = _sankey(self._SRC)
        assert "<div" in html or "<svg" in html

    def test_three_rows_render_same_as_two(self):
        """Adding a third data row does not crash or regress the render."""
        two_row = _sankey("Electricity,Lighting,28.7\nElectricity,Heating,42.3\n")
        three_row = _sankey(self._SRC)
        assert "mermaid-layout" in two_row
        assert "mermaid-layout" in three_row


# ---------------------------------------------------------------------------
# TestSankeyBetaQuotedValues — quoted sources/targets containing commas
# ---------------------------------------------------------------------------

class TestSankeyBetaQuotedValues:
    """Quoted identifiers with embedded commas: \"Fuel, Oil\"."""

    _SRC_QUOTED_SOURCE = '"Fuel, Oil",Heating,10.5\n'
    _SRC_QUOTED_TARGET = 'Nuclear,"Electricity Gen",92.9\n'
    _SRC_BOTH_QUOTED = '"Fuel, Oil","Electricity Gen",0.9\n'
    _SRC_MULTI_QUOTED = (
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
        'Nuclear,"Electricity Gen",92.9\n'
    )

    def test_quoted_source_does_not_raise(self):
        """A row with a quoted source (\"Fuel, Oil\") renders without error."""
        _sankey(self._SRC_QUOTED_SOURCE)

    def test_quoted_target_does_not_raise(self):
        """A row with a quoted target (\"Electricity Gen\") renders without error."""
        _sankey(self._SRC_QUOTED_TARGET)

    def test_both_quoted_does_not_raise(self):
        """A row with both source and target quoted renders without error."""
        _sankey(self._SRC_BOTH_QUOTED)

    def test_multiple_quoted_rows_do_not_raise(self):
        """Multiple rows mixing quoted and unquoted identifiers render without error."""
        _sankey(self._SRC_MULTI_QUOTED)

    def test_quoted_rows_produce_nonempty_html(self):
        """Quoted-identifier rows produce a non-empty HTML document."""
        html = _sankey(self._SRC_MULTI_QUOTED)
        assert html
        assert "mermaid-layout" in html


# ---------------------------------------------------------------------------
# TestSankeyBetaDecimalValues — decimal numeric flow values
# ---------------------------------------------------------------------------

class TestSankeyBetaDecimalValues:
    """Flow values can be fractional (decimals), not just integers."""

    def test_decimal_value_renders(self):
        """A row with a decimal value (28.7) renders without error."""
        _sankey("Electricity,Lighting,28.7\n")

    def test_all_decimal_rows_render(self):
        """Multiple decimal-value rows all render without error."""
        src = (
            "Electricity,Lighting,28.7\n"
            "Electricity,Heating,42.3\n"
            "Gas,Heating,60.0\n"
            "Nuclear,Electricity,92.9\n"
        )
        html = _sankey(src)
        assert "mermaid-layout" in html

    def test_small_decimal_value(self):
        """A very small decimal value (0.9) does not crash the renderer."""
        _sankey('"Fuel, Oil","Electricity Gen",0.9\n')

    def test_large_integer_value(self):
        """A large integer flow value (e.g., 10000) renders without error."""
        _sankey("Coal,Power,10000\n")

    def test_decimal_and_integer_mixed(self):
        """Rows mixing decimal and integer values all render without error."""
        src = "A,B,100\nC,D,55.5\nE,F,0.1\n"
        html = _sankey(src)
        assert "mermaid-layout" in html


# ---------------------------------------------------------------------------
# TestSankeyBetaMultiFlow — multi-source / multi-target flows
# ---------------------------------------------------------------------------

class TestSankeyBetaMultiFlow:
    """Multi-source and multi-target flow patterns (fan-out and fan-in)."""

    _FULL_EXAMPLE = (
        "Electricity,Lighting,28.7\n"
        "Electricity,Heating,42.3\n"
        "Gas,Heating,60.0\n"
        "Nuclear,Electricity,92.9\n"
        '"Fuel, Oil",Heating,10.5\n'
        '"Fuel, Oil","Electricity Gen",0.9\n'
    )

    def test_multi_source_single_target_renders(self):
        """Multiple sources flowing into the same target renders without error."""
        src = (
            "Electricity,Heating,42.3\n"
            "Gas,Heating,60.0\n"
            '"Fuel, Oil",Heating,10.5\n'
        )
        html = _sankey(src)
        assert "mermaid-layout" in html

    def test_single_source_multi_target_renders(self):
        """One source fanning out to multiple targets renders without error."""
        src = (
            "Electricity,Lighting,28.7\n"
            "Electricity,Heating,42.3\n"
            "Electricity,Other,5.0\n"
        )
        html = _sankey(src)
        assert "mermaid-layout" in html
        assert "Electricity" in html

    def test_full_example_renders(self):
        """The full mermaid.js docs example (all 6 rows) renders without error."""
        html = _sankey(self._FULL_EXAMPLE)
        assert "mermaid-layout" in html

    def test_full_example_source_names_present(self):
        """Source-column names (Electricity, Gas, Nuclear) appear in rendered HTML."""
        html = _sankey(self._FULL_EXAMPLE)
        assert "Electricity" in html
        assert "Gas" in html
        assert "Nuclear" in html

    def test_many_rows_render(self):
        """A diagram with six data rows renders without error."""
        html = _sankey(self._FULL_EXAMPLE)
        assert html
        assert "<html" in html or html.lstrip().startswith("<!DOCTYPE")

    def test_chain_flow_renders(self):
        """A three-step chain A→B→C renders without error."""
        src = "A,B,50\nB,C,50\n"
        html = _sankey(src)
        assert "mermaid-layout" in html

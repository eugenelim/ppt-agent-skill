"""Regression tests for mmdc 11.15 SVG data-et selector names.

These tests render two canonical sequence-diagram fixtures via the mmdc CLI and
assert that the confirmed data-et attribute names and counts match what
SequenceGeometry produces.  All tests are marked external_reference and skip
cleanly when mmdc is not on PATH.

Confirmed selector inventory (mmdc 11.15):
  data-et="participant"       <g> wrapping each participant box
  data-et="message"           <line> for each message arrow
  data-et="life-line"         <line> for each lifeline
  data-et="note"              <g> for each Note element
  data-et="control-structure" <g> for alt/opt/loop/par/break fragments
  class="activationN"         <rect> for each activation box (NO data-et)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture source diagrams
# ---------------------------------------------------------------------------

# Diagram 1: Alice/Bob with a note and an activation
# Expected: participants=2, messages=4, notes=1, fragments=0, activations=1
_DIAGRAM_1 = """sequenceDiagram
    participant Alice
    participant Bob
    Alice->>Bob: Hello
    Note over Alice,Bob: A note
    activate Bob
    Bob-->>Alice: Got it
    Alice->>Bob: Done
    deactivate Bob
    Bob-->>Alice: OK
"""

# Diagram 2: A/B/C with alt/loop/opt fragments and an activation
# Expected: participants=3, messages=8, fragments=3, notes=0, activations=1
_DIAGRAM_2 = """sequenceDiagram
    participant A
    participant B
    participant C
    A->>B: msg1
    alt condition
        B->>C: msg2
        C-->>B: msg3
    else otherwise
        B->>A: msg4
    end
    loop every tick
        A->>C: msg5
        C-->>A: msg6
    end
    opt maybe
        A->>B: msg7
    end
    activate A
    B-->>A: msg8
    deactivate A
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mmdc_path() -> str | None:
    return shutil.which("mmdc")


def _render_to_svg(src: str, tmp_dir: str) -> str:
    """Render a diagram source string to SVG via mmdc; return the SVG text."""
    mmdc = _mmdc_path()
    inp = Path(tmp_dir) / "diagram.mmd"
    out = Path(tmp_dir) / "diagram.svg"
    inp.write_text(src, encoding="utf-8")
    subprocess.run(
        [mmdc, "-i", str(inp), "-o", str(out)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return out.read_text(encoding="utf-8")


def _count_data_et(svg_text: str, et_val: str) -> int:
    """Count occurrences of data-et="<et_val>" in raw SVG text."""
    return svg_text.count(f'data-et="{et_val}"')


# ---------------------------------------------------------------------------
# Module-scoped fixture: render both diagrams once per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mmdc_svgs():
    """Render both canonical diagrams and return (svg1_text, svg2_text).

    Skips the entire module if mmdc is not on PATH.
    """
    if not _mmdc_path():
        pytest.skip("mmdc not on PATH — install mermaid-js CLI to run these tests")

    with tempfile.TemporaryDirectory(prefix="test_mmdc_selectors_1_") as td1, \
         tempfile.TemporaryDirectory(prefix="test_mmdc_selectors_2_") as td2:
        svg1 = _render_to_svg(_DIAGRAM_1, td1)
        svg2 = _render_to_svg(_DIAGRAM_2, td2)
        yield svg1, svg2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.external_reference
def test_participant_selector(mmdc_svgs):
    """data-et="participant": svg1=2, svg2=3."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "participant") == 2, (
        f"svg1 participant count mismatch: got {_count_data_et(svg1, 'participant')}"
    )
    assert _count_data_et(svg2, "participant") == 3, (
        f"svg2 participant count mismatch: got {_count_data_et(svg2, 'participant')}"
    )


@pytest.mark.external_reference
def test_message_selector(mmdc_svgs):
    """data-et="message": svg1=4, svg2=8."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "message") == 4, (
        f"svg1 message count mismatch: got {_count_data_et(svg1, 'message')}"
    )
    assert _count_data_et(svg2, "message") == 8, (
        f"svg2 message count mismatch: got {_count_data_et(svg2, 'message')}"
    )


@pytest.mark.external_reference
def test_note_selector(mmdc_svgs):
    """data-et="note": svg1=1, svg2=0."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "note") == 1, (
        f"svg1 note count mismatch: got {_count_data_et(svg1, 'note')}"
    )
    assert _count_data_et(svg2, "note") == 0, (
        f"svg2 note count mismatch: got {_count_data_et(svg2, 'note')}"
    )


@pytest.mark.external_reference
def test_control_structure_selector(mmdc_svgs):
    """data-et="control-structure": svg1=0, svg2=3."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "control-structure") == 0, (
        f"svg1 control-structure count mismatch: got {_count_data_et(svg1, 'control-structure')}"
    )
    assert _count_data_et(svg2, "control-structure") == 3, (
        f"svg2 control-structure count mismatch: got {_count_data_et(svg2, 'control-structure')}"
    )


@pytest.mark.external_reference
def test_activation_no_data_et(mmdc_svgs):
    """Activation boxes do NOT use data-et="activation" — the attribute is absent."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "activation") == 0, (
        f'svg1 unexpectedly contains data-et="activation"' 
    )
    assert _count_data_et(svg2, "activation") == 0, (
        f'svg2 unexpectedly contains data-et="activation"'
    )


@pytest.mark.external_reference
def test_activation_uses_class_pattern(mmdc_svgs):
    """Activation boxes use class="activationN" on <rect>: svg1=1, svg2=1."""
    svg1, svg2 = mmdc_svgs
    svg1_matches = re.findall(r'class="activation\d+"', svg1)
    svg2_matches = re.findall(r'class="activation\d+"', svg2)
    assert len(svg1_matches) == 1, (
        f"svg1 activation class count mismatch: got {len(svg1_matches)}"
    )
    assert len(svg2_matches) == 1, (
        f"svg2 activation class count mismatch: got {len(svg2_matches)}"
    )


@pytest.mark.external_reference
def test_life_line_selector(mmdc_svgs):
    """data-et="life-line": svg1=2, svg2=3."""
    svg1, svg2 = mmdc_svgs
    assert _count_data_et(svg1, "life-line") == 2, (
        f"svg1 life-line count mismatch: got {_count_data_et(svg1, 'life-line')}"
    )
    assert _count_data_et(svg2, "life-line") == 3, (
        f"svg2 life-line count mismatch: got {_count_data_et(svg2, 'life-line')}"
    )

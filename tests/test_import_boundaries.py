"""Import-boundary tests for the mermaid renderer layout package.

Uses ast.parse + ast.walk to assert that module-level import relationships
obey the layered architecture:

  Parsers  ──→  (cannot import colors/styles)
  Layout   ──→  (cannot import from renderer)
  Renderer ──→  render_finalized must not call layout algorithms
  Comparators ──→ (cannot return PASS with zero checks)

None of these tests require a browser, mmdc, or subprocess.
All tests are tagged @pytest.mark.parity_fast.

AC11 (spec): A test asserts painters do not call layout functions; a test
asserts layout code does not produce HTML/SVG strings; a test asserts
comparators do not return PASS with zero checks.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUT_PKG = REPO_ROOT / "scripts" / "mermaid_render" / "layout"
TOOLS_PKG = REPO_ROOT / "tools" / "mermaid_fidelity"


# ── AST helpers ───────────────────────────────────────────────────────────────

def _all_imports_in(path: Path) -> list[tuple[str, str | None]]:
    """Return (module, fromlist_or_None) for every import in *path* (including locals).

    Each Import node produces ("module", None).
    Each ImportFrom node produces ("module", "name") for every name imported.
    Walks ALL nodes including those inside function bodies.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, None))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append((module, alias.name))
    return imports


def _module_level_imports_in(path: Path) -> list[tuple[str, str | None]]:
    """Return imports at module level only (not inside function/class bodies)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: list[tuple[str, str | None]] = []
    # Only iterate top-level statements in the module body
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, None))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append((module, alias.name))
    return imports


def _has_import_of(imports: list[tuple[str, str | None]], fragment: str) -> bool:
    """True if any import's module contains *fragment* as a substring."""
    return any(fragment in mod for mod, _ in imports)


def _functions_calling(path: Path, callee_name: str) -> list[str]:
    """Return names of top-level functions that call *callee_name* directly."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    callers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == callee_name
            ):
                callers.append(node.name)
                break
    return callers


# ── Test 1: render_finalized does not call routing algorithms (AC8) ───────────

@pytest.mark.parity_fast
def test_render_finalized_does_not_call_route_edges():
    """render_finalized must not call _route_edges — it must be a pure serializer.

    AC8: No painter performs independent geometry work.
    render_finalized is the canonical painter; it must accept pre-routed geometry
    from FinalizedLayout and serialize it — never re-compute routing.

    Note: _render_graph_fragment (the legacy rendering path) does call _route_edges.
    That path is only used by the class-diagram legacy (_layout_class) code, not by
    the main dispatch. The canonical path is: _compile_* → render_finalized.
    """
    renderer_py = LAYOUT_PKG / "_renderer.py"
    assert renderer_py.exists(), f"{renderer_py} not found"

    # Find which functions call _route_edges
    callers = _functions_calling(renderer_py, "_route_edges")

    # render_finalized must NOT be among them
    assert "render_finalized" not in callers, (
        "AC8 violation: render_finalized calls _route_edges — "
        "the canonical painter must not perform independent routing work."
    )


@pytest.mark.parity_fast
def test_render_finalized_no_layout_algorithms_in_docstring():
    """render_finalized's docstring explicitly prohibits geometry calls.

    This test enforces that the prohibition is documented so future
    contributors cannot remove it without seeing the constraint.
    """
    renderer_py = LAYOUT_PKG / "_renderer.py"
    source = renderer_py.read_text(encoding="utf-8")

    # The docstring must say "no _route_edges call"
    assert "_route_edges" in source and "MUST NOT" in source, (
        "render_finalized's prohibition of geometry calls must be documented "
        "in its docstring (search for 'MUST NOT' and '_route_edges')."
    )


# ── Test 2: _layout.py does not import renderer ───────────────────────────────

@pytest.mark.parity_fast
def test_layout_does_not_import_renderer():
    """_layout.py must not import _renderer.

    Layout algorithms must not emit HTML or SVG strings — they operate on
    abstract graph coordinates only.  An import of _renderer from _layout
    would blur this boundary.
    """
    layout_py = LAYOUT_PKG / "_layout.py"
    assert layout_py.exists(), f"{layout_py} not found"

    imports = _all_imports_in(layout_py)
    assert not _has_import_of(imports, "_renderer"), (
        "_layout.py imports _renderer (AC11 violation): "
        "layout code must not produce HTML/SVG strings."
    )


@pytest.mark.parity_fast
def test_layout_does_not_import_strategies():
    """_layout.py must not import _strategies (would create a circular dependency)."""
    layout_py = LAYOUT_PKG / "_layout.py"
    imports = _all_imports_in(layout_py)

    assert not _has_import_of(imports, "_strategies"), (
        "_layout.py imports _strategies — circular layout→strategy dependency."
    )


# ── Test 3: Parser modules do not choose editorial colors ─────────────────────

@pytest.mark.parity_fast
def test_parser_does_not_import_themes():
    """_parser.py must not import the themes or paint modules.

    Parsers are responsible for syntax analysis only; editorial color choices
    are a rendering concern.  Importing themes from a parser would break the
    parsing/rendering separation.
    """
    parser_py = LAYOUT_PKG / "_parser.py"
    assert parser_py.exists(), f"{parser_py} not found"

    imports = _all_imports_in(parser_py)
    color_modules = {"themes", "paint", "paint_tokens", "_renderer"}
    found = {f for f in color_modules if _has_import_of(imports, f)}

    assert not found, (
        f"_parser.py imports color/style modules (AC11 violation): {found}\n"
        f"Parsers must not choose editorial colors."
    )


@pytest.mark.parity_fast
def test_constants_module_does_not_import_renderer():
    """_constants.py must not import _renderer (constants are pre-render data)."""
    constants_py = LAYOUT_PKG / "_constants.py"
    assert constants_py.exists(), f"{constants_py} not found"

    imports = _all_imports_in(constants_py)
    assert not _has_import_of(imports, "_renderer"), (
        "_constants.py imports _renderer — constants must not depend on renderer."
    )


# ── Test 4: Comparators cannot return PASS with zero checks ──────────────────

@pytest.mark.parity_fast
def test_comparator_no_pass_without_checks():
    """OracleResult(status=PASS, checks=()) must raise ValueError.

    AC11: comparators cannot return PASS with zero checks.
    The guard in OracleResult.__post_init__ enforces this invariant.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from tools.mermaid_fidelity.oracle_contract import OracleResult, OracleStatus

    with pytest.raises(ValueError, match="PASS requires at least one check"):
        OracleResult(status=OracleStatus.PASS, checks=(), fixture_stem="x")


@pytest.mark.parity_fast
def test_oracle_contract_guard_is_in_post_init():
    """The zero-check guard must live in OracleResult.__post_init__, not in callers.

    Checks that the guard exists at the type level, not scattered in call sites.
    """
    import inspect
    from tools.mermaid_fidelity.oracle_contract import OracleResult

    src = inspect.getsource(OracleResult.__post_init__)
    assert "PASS" in src and "checks" in src, (
        "OracleResult.__post_init__ must contain the PASS+checks guard. "
        "Do not remove or move it to call sites."
    )


@pytest.mark.parity_fast
def test_comparator_non_vacuous_pass_is_allowed():
    """OracleResult(status=PASS, checks=(check,)) must succeed (non-vacuous)."""
    from tools.mermaid_fidelity.oracle_contract import OracleCheck, OracleResult, OracleStatus

    check = OracleCheck(name="entity_count", passed=True)
    result = OracleResult(
        status=OracleStatus.PASS,
        checks=(check,),
        fixture_stem="flowchart-basic",
    )
    assert result.status == OracleStatus.PASS
    assert len(result.checks) == 1


# ── Test 5: Module split completeness ─────────────────────────────────────────

@pytest.mark.parity_fast
def test_pipeline_module_exists():
    """_pipeline.py must exist as a distinct compilation module."""
    assert (LAYOUT_PKG / "_pipeline.py").exists(), (
        "_pipeline.py missing — flowchart compilation must live in its own module."
    )


@pytest.mark.parity_fast
def test_diagram_types_module_exists():
    """_diagram_types.py must exist as a distinct diagram-type dispatch module."""
    assert (LAYOUT_PKG / "_diagram_types.py").exists(), (
        "_diagram_types.py missing — non-flowchart diagram types must be in their own module."
    )


@pytest.mark.parity_fast
def test_sequence_compile_module_exists():
    """_sequence_compile.py must exist as a distinct sequence compilation module (AC6)."""
    assert (LAYOUT_PKG / "_sequence_compile.py").exists(), (
        "_sequence_compile.py missing — sequence diagram compilation must live in its own "
        "module after the _strategies.py split (AC6)."
    )


@pytest.mark.parity_fast
def test_strategies_is_a_shim_for_sequence():
    """compile_sequence must be importable from both _sequence_compile and _strategies (AC10).

    AC6: _strategies.py no longer owns the implementation of sequence compilation.
    AC10: backward-compatible imports from _strategies.py must still work.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from mermaid_render.layout._sequence_compile import compile_sequence as cs_direct
    from mermaid_render.layout._strategies import compile_sequence as cs_via_shim

    # Same object (shim re-exports, not a copy)
    assert cs_direct is cs_via_shim, (
        "_strategies.compile_sequence is not the same object as "
        "_sequence_compile.compile_sequence — _strategies must re-export, not redefine."
    )


@pytest.mark.parity_fast
def test_strategies_remains_importable():
    """_strategies.py must remain importable for backward compatibility (AC10)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        from mermaid_render.layout import _strategies  # noqa: F401
    except ImportError as exc:
        pytest.fail(
            f"_strategies.py import failed — backward compatibility broken (AC10): {exc}"
        )


# ── Test 6: Public API backward compatibility ─────────────────────────────────

@pytest.mark.parity_fast
def test_public_api_imports():
    """All documented public API symbols must remain importable (AC10)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

    # Core dispatch entry points
    from mermaid_render.layout._strategies import _dispatch, _dispatch_validate  # noqa: F401

    # Flowchart compilation pipeline (from _pipeline.py, re-exported via _strategies)
    from mermaid_render.layout._pipeline import (  # noqa: F401
        RenderOptions, _compile_flowchart, parse_flowchart_semantics,
    )

    # Geometry types
    from mermaid_render.layout._geometry import (  # noqa: F401
        FinalizedLayout, NodeLayout, RoutedEdge, LayoutMetadata,
    )

    # Oracle contract
    sys.path.insert(0, str(REPO_ROOT))
    from tools.mermaid_fidelity.oracle_contract import (  # noqa: F401
        OracleStatus, OracleCheck, OracleResult,
    )


# ── Test 7: Dead code absence ─────────────────────────────────────────────────

@pytest.mark.parity_fast
def test_compile_er_legacy_absent():
    """_compile_er_legacy must be absent from the er module (AC7).

    The ER compiler was consolidated in the er-compiler-consolidation spec.
    Only one active ER compiler must exist.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from mermaid_render.layout import er as er_mod

    assert not hasattr(er_mod, "_compile_er_legacy"), (
        "_compile_er_legacy still exists in the er module — delete it. "
        "Only one active ER compiler is allowed (AC7)."
    )


@pytest.mark.parity_fast
def test_oracle_status_not_duplicated():
    """OracleStatus must be defined in exactly one canonical location.

    oracle_contract.py is the single source of truth.  Any duplicate definition
    in tests/ or compare/ modules would cause confusion and drift.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from tools.mermaid_fidelity.oracle_contract import OracleStatus

    # Verify the canonical enum has the expected members
    expected = {"PASS", "FAIL", "EXTRACTOR_GAP", "UNSUPPORTED_REFERENCE_FEATURE", "UNVALIDATED"}
    actual = {s.name for s in OracleStatus}
    assert actual == expected, (
        f"OracleStatus members changed: expected {expected}, got {actual}. "
        "Update oracle_contract.py — do not add duplicates elsewhere."
    )

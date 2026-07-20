#!/usr/bin/env python3
"""Gitgraph syntax coverage tests for the mermaid_render layout engine.

``gitgraph`` is a Mermaid diagram type not supported by the pure-Python
renderer.  These tests document every real gitgraph syntax construct and
assert that ``to_html`` raises ``ValueError`` gracefully for each one
instead of crashing with an unhandled exception or returning garbage HTML.

Real syntax covered:
  - Plain ``gitgraph`` (no orientation suffix)
  - ``gitgraph LR:`` / ``gitgraph TB:`` / ``gitgraph BT:`` orientation variants
  - ``commit`` with ``id:``, ``tag:``, and ``type:`` attributes
  - ``branch`` / ``checkout`` / ``merge`` commands
  - ``cherry-pick id: "xxx"``
  - ``%%{init: {...}}%%`` config-block prefix
  - All three commit type values: NORMAL, REVERSE, HIGHLIGHT

Import note: ``to_html`` lives in ``mermaid_render``, not in the
``mermaid_layout`` shim (which does not re-export ``to_html``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── TestGitGraphUnsupported ───────────────────────────────────────────────────


class TestGitGraphUnsupported:
    """Every gitgraph syntax variant raises ValueError from to_html."""

    def test_basic_gitgraph_raises(self):
        """Plain ``gitgraph`` with a few commits raises ValueError."""
        src = """\
gitgraph
   commit id: "init"
   branch develop
   checkout develop
   commit id: "feat-1"
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    def test_gitgraph_with_branches_raises(self):
        """Full branch/merge/cherry-pick workflow raises ValueError."""
        src = """\
gitgraph LR:
   commit id: "init"
   branch develop
   checkout develop
   commit id: "feat-1" tag: "v0.1" type: HIGHLIGHT
   commit id: "feat-2" type: REVERSE
   checkout main
   merge develop id: "merge-1" tag: "v1.0"
   cherry-pick id: "feat-1"
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    def test_gitgraph_tb_raises(self):
        """``gitgraph TB:`` orientation raises ValueError."""
        src = """\
gitgraph TB:
   commit
   branch feature
   checkout feature
   commit
   checkout main
   merge feature
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    def test_gitgraph_bt_raises(self):
        """``gitgraph BT:`` orientation raises ValueError."""
        src = """\
gitgraph BT:
   commit id: "a"
   branch dev
   checkout dev
   commit id: "b"
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    def test_gitgraph_cherry_pick_raises(self):
        """Gitgraph containing a ``cherry-pick`` command raises ValueError."""
        src = """\
gitgraph
   commit id: "base"
   branch hotfix
   checkout hotfix
   commit id: "fix-1" tag: "v1.0.1"
   checkout main
   cherry-pick id: "fix-1"
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    @pytest.mark.parametrize("commit_type", ["NORMAL", "REVERSE", "HIGHLIGHT"])
    def test_commit_types_raise(self, commit_type: str):
        """Each commit type variant (NORMAL / REVERSE / HIGHLIGHT) raises ValueError."""
        src = f"""\
gitgraph
   commit id: "c1" type: {commit_type}
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

    def test_error_is_value_error(self):
        """The exception raised for gitgraph is specifically ValueError, not a subtype."""
        src = """\
gitgraph
   commit
"""
        with pytest.raises(ValueError, match="gitgraph") as exc_info:
            to_html(src)
        assert type(exc_info.value) is ValueError, (
            f"Expected exact ValueError, got {type(exc_info.value)!r}"
        )

    def test_gitgraph_with_init_config_block_raises(self):
        """Gitgraph prefixed by an ``%%{init: {...}}%%`` config block raises ValueError.

        ``_detect_directive`` skips ``%%``-prefixed lines, so the gitgraph
        directive is still detected correctly and the renderer still raises.
        """
        src = """\
%%{init: { 'logLevel': 'debug', 'theme': 'default', 'gitGraph': {'rotateCommitLabel': false}}}%%
gitgraph
  commit
  branch dev
  commit
"""
        with pytest.raises(ValueError, match="not supported by the pure-Python renderer"):
            to_html(src)

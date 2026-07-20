#!/usr/bin/env python3
"""Gitgraph syntax coverage tests for the mermaid_render layout engine.

``gitgraph`` now has a basic renderer in the pure-Python engine.  These tests
document supported syntax constructs and verify they produce HTML output.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mermaid_render import to_html  # noqa: E402


# ── TestGitGraphRendered ──────────────────────────────────────────────────────


class TestGitGraphRendered:
    """Every gitgraph syntax variant produces HTML output from to_html."""

    def test_basic_gitgraph_renders(self):
        """Plain ``gitgraph`` with a few commits produces output."""
        src = """\
gitgraph
   commit id: "init"
   branch develop
   checkout develop
   commit id: "feat-1"
"""
        html = to_html(src)
        assert "main" in html
        assert "develop" in html

    def test_gitgraph_with_branches_renders(self):
        """Full branch/merge workflow renders HTML."""
        src = """\
gitgraph LR:
   commit id: "init"
   branch develop
   checkout develop
   commit id: "feat-1" tag: "v0.1" type: HIGHLIGHT
   commit id: "feat-2" type: REVERSE
   checkout main
   merge develop id: "merge-1" tag: "v1.0"
"""
        html = to_html(src)
        assert html
        assert "develop" in html

    def test_gitgraph_tb_renders(self):
        """``gitgraph TB:`` orientation renders HTML."""
        src = """\
gitgraph TB:
   commit
   branch feature
   checkout feature
   commit
   checkout main
   merge feature
"""
        html = to_html(src)
        assert html

    def test_gitgraph_commit_circles(self):
        """Commit nodes are rendered as circles."""
        src = """\
gitgraph
   commit
   commit
   branch dev
   checkout dev
   commit
"""
        html = to_html(src)
        assert "border-radius:50%" in html

    @pytest.mark.parametrize("commit_type", ["NORMAL", "REVERSE", "HIGHLIGHT"])
    def test_commit_types_render(self, commit_type: str):
        """Each commit type variant renders HTML."""
        src = f"""\
gitgraph
   commit id: "c1" type: {commit_type}
"""
        html = to_html(src)
        assert html

    def test_gitgraph_with_init_config_block_renders(self):
        """Gitgraph prefixed by an ``%%{init: {...}}%%`` config block renders HTML."""
        src = """\
%%{init: { 'logLevel': 'debug', 'theme': 'default', 'gitGraph': {'rotateCommitLabel': false}}}%%
gitgraph
  commit
  branch dev
  commit
"""
        html = to_html(src)
        assert html
        assert "main" in html

    def test_gitgraph_merge_connects_branches(self):
        """Merge creates a connection between branches in the SVG."""
        src = """\
gitgraph
   commit
   branch develop
   checkout develop
   commit
   checkout main
   merge develop
   commit
"""
        html = to_html(src)
        assert "develop" in html
        # merge should draw a curved path
        assert "<path" in html

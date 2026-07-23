"""Tests for no-sandbox container isolation (AST06/ASI02).

These tests verify infrastructure exists and env var control works.
They do NOT build or run the Docker image — use @pytest.mark.external_reference
for tests that require a live Docker daemon.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on sys.path so `mermaid_render.*` is importable.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

ROOT = Path(__file__).resolve().parent.parent


class TestEnvVarControl:
    """AC-3: RENDER_IN_CONTAINER=1 removes --no-sandbox from launch args."""

    @pytest.fixture(autouse=True)
    def restore_browser_module(self):
        """Reload browser module to default state after each env-mutating test.

        monkeypatch reverts the env var, but importlib.reload() leaves the
        module in the last-reloaded state. This fixture ensures _LAUNCH_ARGS
        reflects the default (non-container) env after every test in this class,
        preventing state leaking into other browser-launching tests in the session.
        """
        yield
        # Ensure RENDER_IN_CONTAINER is cleared (handles any monkeypatch teardown order).
        os.environ.pop("RENDER_IN_CONTAINER", None)
        import mermaid_render.browser as b
        importlib.reload(b)

    def test_default_includes_no_sandbox(self, monkeypatch):
        """Without env var, --no-sandbox is present."""
        monkeypatch.delenv("RENDER_IN_CONTAINER", raising=False)
        import mermaid_render.browser as b
        importlib.reload(b)
        assert "--no-sandbox" in b._LAUNCH_ARGS

    def test_container_mode_excludes_no_sandbox(self, monkeypatch):
        """With RENDER_IN_CONTAINER=1, --no-sandbox is absent."""
        monkeypatch.setenv("RENDER_IN_CONTAINER", "1")
        import mermaid_render.browser as b
        importlib.reload(b)
        assert "--no-sandbox" not in b._LAUNCH_ARGS

    def test_container_mode_preserves_other_args(self, monkeypatch):
        """Container mode preserves --disable-gpu and --font-render-hinting."""
        monkeypatch.setenv("RENDER_IN_CONTAINER", "1")
        import mermaid_render.browser as b
        importlib.reload(b)
        assert "--disable-gpu" in b._LAUNCH_ARGS
        assert "--font-render-hinting=none" in b._LAUNCH_ARGS


class TestDockerfileExists:
    """AC-1: Dockerfile exists and has key content."""

    def test_dockerfile_exists(self):
        assert (ROOT / "docker" / "render" / "Dockerfile").exists()

    def test_dockerfile_has_playwright_install(self):
        content = (ROOT / "docker" / "render" / "Dockerfile").read_text()
        assert "playwright install" in content and "chromium" in content

    def test_dockerfile_no_no_sandbox_in_launch(self):
        """Dockerfile must not bake --no-sandbox into the image command."""
        content = (ROOT / "docker" / "render" / "Dockerfile").read_text()
        assert "--no-sandbox" not in content


class TestSeccompProfile:
    """AC-2: seccomp profile is valid and has required structure."""

    def test_seccomp_profile_exists(self):
        assert (ROOT / "docker" / "render" / "chrome.json").exists()

    def test_seccomp_profile_is_valid_json(self):
        content = (ROOT / "docker" / "render" / "chrome.json").read_text()
        profile = json.loads(content)
        assert "defaultAction" in profile
        assert "syscalls" in profile

    def test_seccomp_default_action_is_deny(self):
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        assert profile["defaultAction"] in ("SCMP_ACT_ERRNO", "SCMP_ACT_KILL")

    def test_seccomp_has_substantial_allowlist(self):
        """Profile should allow at minimum the core Chromium syscalls."""
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        allowed_names = {
            name
            for entry in profile["syscalls"]
            if entry.get("action") == "SCMP_ACT_ALLOW"
            for name in entry.get("names", [])
        }
        assert len(allowed_names) >= 50, (
            f"Expected at least 50 allowed syscalls, got {len(allowed_names)}"
        )

    def test_seccomp_blocks_clone3(self):
        """clone3 must not be in the ALLOW list."""
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        allowed_names = {
            name
            for entry in profile["syscalls"]
            if entry.get("action") == "SCMP_ACT_ALLOW"
            for name in entry.get("names", [])
        }
        assert "clone3" not in allowed_names

    def test_seccomp_clone3_returns_enosys(self):
        """clone3 must return ENOSYS (38) so glibc falls back to clone()."""
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        clone3_entry = next(
            (e for e in profile["syscalls"] if "clone3" in e.get("names", [])), None
        )
        assert clone3_entry is not None, "clone3 entry missing from syscalls"
        assert clone3_entry.get("errnoRet") == 38, (
            "clone3 must return ENOSYS (38) not EPERM — glibc >= 2.34 only "
            "falls back to clone() on ENOSYS"
        )

    def test_seccomp_blocks_mount(self):
        """mount must not be in the allowlist."""
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        allowed_names = {
            name
            for entry in profile["syscalls"]
            if entry.get("action") == "SCMP_ACT_ALLOW"
            for name in entry.get("names", [])
        }
        assert "mount" not in allowed_names

    def test_seccomp_blocks_pivot_root(self):
        """pivot_root must not be in the allowlist."""
        profile = json.loads((ROOT / "docker" / "render" / "chrome.json").read_text())
        allowed_names = {
            name
            for entry in profile["syscalls"]
            if entry.get("action") == "SCMP_ACT_ALLOW"
            for name in entry.get("names", [])
        }
        assert "pivot_root" not in allowed_names


class TestRenderContainerFunction:
    """AC-4: render_html_in_container builds the expected docker run command."""

    def test_render_container_importable(self):
        """render_container module is importable and exports the function."""
        from mermaid_render import render_container
        assert callable(render_container.render_html_in_container)

    def test_render_html_in_container_command_structure(self, tmp_path, monkeypatch):
        """render_html_in_container assembles the expected docker run argv."""
        from mermaid_render import render_container

        html = tmp_path / "slide.html"
        html.write_text("<html><body></body></html>")
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        # Provide a dummy seccomp file so the fail-closed check passes.
        fake_seccomp = tmp_path / "chrome.json"
        fake_seccomp.write_text('{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}')
        monkeypatch.setattr(render_container, "_SECCOMP", fake_seccomp)

        captured: list = []

        def fake_run(cmd, **kwargs):
            captured.append(list(cmd))

        monkeypatch.setattr(subprocess, "run", fake_run)
        render_container.render_html_in_container(html, output_dir=out_dir)

        assert captured, "subprocess.run was not called"
        cmd = captured[0]
        assert cmd[0] == "docker"
        assert "--cap-drop=ALL" in cmd
        assert "--cap-add=SYS_ADMIN" in cmd
        assert "--network=none" in cmd
        assert any("ppt-agent-render" in arg for arg in cmd)
        assert "RENDER_IN_CONTAINER=1" in cmd
        assert any("seccomp" in arg for arg in cmd)
        # CLI contract: positional HTML path and output dir flag
        assert f"/input/{html.name}" in cmd
        assert "-o" in cmd
        o_idx = cmd.index("-o")
        assert cmd[o_idx + 1] == "/output"

    def test_render_html_in_container_fails_without_seccomp(self, tmp_path, monkeypatch):
        """render_html_in_container raises FileNotFoundError when seccomp missing (fail-closed)."""
        from mermaid_render import render_container

        monkeypatch.setattr(render_container, "_SECCOMP", tmp_path / "missing.json")

        html = tmp_path / "slide.html"
        html.write_text("<html></html>")
        out_dir = tmp_path / "output"

        with pytest.raises(FileNotFoundError, match="Seccomp profile not found"):
            render_container.render_html_in_container(html, output_dir=out_dir)

"""Toolchain lockfile for browser geometry capture.

Pins the exact Mermaid CLI version used for reference captures.
The provenance recorder uses these constants to validate the detected
runtime versions against the expected lockfile versions.
"""
from __future__ import annotations

import subprocess
from typing import Optional


# ── pinned versions ────────────────────────────────────────────────────────────

MERMAID_CLI_VERSION = "11.15.0"
NODE_MIN_VERSION = "18.0.0"
PLAYWRIGHT_MIN_VERSION = "1.40.0"


# ── version detection ──────────────────────────────────────────────────────────

def _run_version_cmd(cmd: list[str]) -> Optional[str]:
    """Run a shell command and return its stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_versions() -> dict[str, str]:
    """Detect installed toolchain versions.

    Returns a dict with keys: mermaid_cli, node, playwright.
    Values are the detected version strings, or "" when unavailable.
    """
    mermaid_raw = _run_version_cmd(["mmdc", "--version"])
    node_raw = _run_version_cmd(["node", "--version"])

    # playwright version via python package
    playwright_version = ""
    try:
        import playwright  # type: ignore[import-untyped]
        playwright_version = getattr(playwright, "__version__", "")
        if not playwright_version:
            # fallback: read from package metadata
            from importlib.metadata import version as pkg_version
            playwright_version = pkg_version("playwright")
    except Exception:
        pass

    # Strip leading 'v' from node version string
    if node_raw and node_raw.startswith("v"):
        node_raw = node_raw[1:]

    return {
        "mermaid_cli": mermaid_raw or "",
        "node": node_raw or "",
        "playwright": playwright_version,
    }

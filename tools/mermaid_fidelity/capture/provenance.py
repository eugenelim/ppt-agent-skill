"""Provenance recorder for browser geometry capture.

Records toolchain versions and font fingerprints at capture time.
This information is stored in ReferenceDiagram.provenance and used
as part of the cache key.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path
from typing import Optional

from tools.mermaid_fidelity.capture.versions import detect_versions, MERMAID_CLI_VERSION
from tools.mermaid_fidelity.models import ReferenceProvenance


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_chromium_version() -> str:
    """Detect the Chromium version used by Playwright."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]
        with sync_playwright() as p:
            browser = p.chromium.launch()
            version = browser.version
            browser.close()
        return version
    except Exception:
        pass

    # Fallback: try chromium CLI
    for cmd in [["chromium", "--version"], ["chromium-browser", "--version"],
                ["google-chrome", "--version"]]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return "unknown"


def _detect_font_families() -> list[str]:
    """Return the list of font families likely available in the render environment."""
    # Mermaid uses these font families by default
    return ["trebuchet ms", "verdana", "arial", "sans-serif"]


def _compute_font_fingerprint(font_families: list[str]) -> str:
    """Compute a fingerprint for the font environment.

    For a real browser environment this would hash actual font files.
    In a unit-test context (no browser) it hashes the family name list.
    """
    # Try to find and hash font files
    font_file_hashes: list[str] = []
    font_search_dirs = [
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
        Path("/usr/local/share/fonts"),
    ]

    for family in font_families:
        family_lower = family.lower().replace(" ", "")
        for search_dir in font_search_dirs:
            if not search_dir.exists():
                continue
            for font_file in search_dir.rglob("*.ttf"):
                if family_lower in font_file.stem.lower():
                    try:
                        font_file_hashes.append(_sha256_file(font_file))
                        break
                    except OSError:
                        pass

    if font_file_hashes:
        combined = "|".join(sorted(font_file_hashes))
        return _sha256_bytes(combined.encode()).hex()

    # Fallback: hash the family names themselves
    combined = "|".join(sorted(font_families))
    return _sha256_bytes(combined.encode())


def record_provenance(
    source_hash: str,
    fixture: str = "",
    render_config_hash: str = "",
    captured_at: Optional[str] = None,
) -> ReferenceProvenance:
    """Record provenance for a capture run.

    Args:
        source_hash: SHA-256 hex of the .mmd source bytes.
        fixture: Fixture stem identifier.
        render_config_hash: SHA-256 of the render configuration dict.
        captured_at: ISO 8601 timestamp string; None means not recorded.

    Returns:
        ReferenceProvenance with all fields populated.
    """
    versions = detect_versions()
    font_families = _detect_font_families()
    font_fingerprint = _compute_font_fingerprint(font_families)

    return ReferenceProvenance(
        mermaid_version=versions.get("mermaid_cli", "unknown") or "unknown",
        mmdc_version=versions.get("mermaid_cli", "unknown") or "unknown",
        node_version=versions.get("node", "unknown") or "unknown",
        playwright_version=versions.get("playwright", "unknown") or "unknown",
        chromium_version="unknown",  # filled by BatchRunner when browser is available
        platform=platform.system(),
        font_families=font_families,
        font_fingerprint=font_fingerprint,
        fixture_source_hash=source_hash,
        render_config_hash=render_config_hash,
        captured_at=captured_at,
    )

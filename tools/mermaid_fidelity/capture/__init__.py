"""Browser-based geometry capture pipeline for Mermaid fidelity benchmarking.

This package renders Mermaid fixtures through a pinned Playwright/Chromium
stack and extracts structured ReferenceDiagram JSON records. Structured JSON
records — not screenshots — are the oracle input.

Public API:
    BatchRunner    — renders a list of fixtures in one long-lived browser session
    extract_diagram — extracts a ReferenceDiagram from raw SVG text
    record_provenance — records toolchain versions and font fingerprints
    DiagramCache   — cache keyed by source hash + toolchain versions
"""
from __future__ import annotations

from tools.mermaid_fidelity.capture.extractor import extract_diagram
from tools.mermaid_fidelity.capture.provenance import record_provenance
from tools.mermaid_fidelity.capture.cache import DiagramCache
from tools.mermaid_fidelity.capture.versions import (
    MERMAID_CLI_VERSION,
    NODE_MIN_VERSION,
    PLAYWRIGHT_MIN_VERSION,
)

__all__ = [
    "extract_diagram",
    "record_provenance",
    "DiagramCache",
    "MERMAID_CLI_VERSION",
    "NODE_MIN_VERSION",
    "PLAYWRIGHT_MIN_VERSION",
    "BatchRunner",
]

# BatchRunner is browser-dependent; import lazily to avoid hard import failure
# in environments without Playwright.
def __getattr__(name: str):  # noqa: N807
    if name == "BatchRunner":
        from tools.mermaid_fidelity.capture.runner import BatchRunner
        return BatchRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

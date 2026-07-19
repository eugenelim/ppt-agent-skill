#!/usr/bin/env python3
"""diagram_render_check.py — browser-based DOM inspection for diagram HTML.

Renders each DiagramCase in a real headless browser via Playwright and checks:
  DIAG-01  hasDiagram present
  DIAG-02  nodeCount matches expected
  DIAG-03  edge SVG paths present when expected
  DIAG-04  legend present when expected
  DIAG-05  legend is at bottom of wrapper
  DIAG-06  no overflowing nodes
  DIAG-07  no nodes outside canvas bounds
  DIAG-08  canvas has non-zero size
  DIAG-09  unexpected legend (warn)

Exit codes:
  0  all pass
  1  any FAIL
  2  only WARN (no FAIL)

If Playwright/Chromium is not available, prints [SKIP] and exits 0.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ── Project layout ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# scripts/ on sys.path so bare `from _browser import` resolves
sys.path.insert(0, str(ROOT / "scripts"))
from _browser import _setup_page, get_browser

# ── DOM inspection expression (verbatim JS port from Puppeteer version) ───────
_DOM_INSPECT_JS = r"""() => {
    return {
        // Basic presence
        hasDiagram: !!(document.querySelector('.diagram.mermaid-layout') ||
                       document.querySelector('.diagram-lifeline')),
        nodeCount: document.querySelectorAll('.node').length,

        // Edge SVG — flowcharts use <path stroke=...>, sequence diagrams use <line stroke=...>
        svgPresent: !!document.querySelector('svg'),
        edgePathCount: document.querySelectorAll('svg path[stroke], svg line[stroke], svg polyline[stroke]').length,

        // Legend checks
        legendPresent: !!document.querySelector('.diagram-legend'),
        legendAtBottom: (() => {
            const wrapper = document.querySelector('.diagram-wrapper');
            const legend = document.querySelector('.diagram-legend');
            if (!wrapper || !legend) return null;
            const wRect = wrapper.getBoundingClientRect();
            const lRect = legend.getBoundingClientRect();
            const gapToBottom = Math.abs(wRect.bottom - lRect.bottom);
            return { gapPx: Math.round(gapToBottom), isAtBottom: gapToBottom < 30 };
        })(),

        // Node overflow: any node where scrollWidth > clientWidth + 4 or scrollHeight > clientHeight + 4
        overflowNodes: (() => {
            const bad = [];
            document.querySelectorAll('.node').forEach(n => {
                if (n.scrollWidth > n.clientWidth + 4 || n.scrollHeight > n.clientHeight + 4) {
                    bad.push(n.querySelector('.node-label')?.textContent?.trim().slice(0, 40) || '(unlabeled)');
                }
            });
            return bad;
        })(),

        // Nodes outside diagram canvas bounds
        outsideNodes: (() => {
            const canvas = document.querySelector('.diagram.mermaid-layout');
            if (!canvas) return [];
            const cRect = canvas.getBoundingClientRect();
            const bad = [];
            document.querySelectorAll('.node').forEach(n => {
                const r = n.getBoundingClientRect();
                if (r.right > cRect.right + 8 || r.bottom > cRect.bottom + 8 ||
                    r.left < cRect.left - 8 || r.top < cRect.top - 8) {
                    bad.push(n.querySelector('.node-label')?.textContent?.trim().slice(0, 40) || '(unlabeled)');
                }
            });
            return bad;
        })(),

        // Canvas dimensions (sanity check non-zero)
        canvasSize: (() => {
            const c = document.querySelector('.diagram.mermaid-layout');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return { w: Math.round(r.width), h: Math.round(r.height) };
        })()
    };
}"""

# ── CSS fixture wrapper ───────────────────────────────────────────────────────
FIXTURE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
:root {{
  --card-bg-from: #ffffff;
  --card-bg-to: #f5f5f5;
  --card-border: #cccccc;
  --node-border: #cccccc;
  --text-primary: #111111;
  --text-secondary: #555555;
  --font-primary: sans-serif;
  --label-font: sans-serif;
  --accent-1: #4466cc;
  --edge: #888888;
  --edge-strong: #333333;
  --group-border: #4466cc;
  --bg-primary: #ffffff;
  --node-fg: #111111;
  --node-fg-dim: #555555;
  --node-bg-from: #ffffff;
  --node-bg-to: #f5f5f5;
}}
body {{ margin: 0; padding: 16px; background: white; }}
.slide-area {{ width: 840px; min-height: 400px; padding: 16px; box-sizing: border-box; display: flex; flex-direction: column; }}
</style>
</head>
<body>
<div class="slide-area">
{fragment}
</div>
</body>
</html>
"""


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DiagramCase:
    name: str
    source: str
    expected_nodes: int
    expected_edges: bool
    expect_legend: bool


@dataclass
class Finding:
    case: str
    check_id: str
    severity: str  # "FAIL" | "WARN"
    detail: str


# ── Test cases ────────────────────────────────────────────────────────────────

CASES: list[DiagramCase] = [
    DiagramCase("simple-tb", "flowchart TB\n  A[Start] --> B[Process] --> C[End]",
                expected_nodes=3, expected_edges=True, expect_legend=False),
    DiagramCase("lr-forward", "flowchart LR\n  A[API] --> B[Service] --> C[DB]",
                expected_nodes=3, expected_edges=True, expect_legend=False),
    DiagramCase("back-edge", "flowchart LR\n  A-->B\n  B-->C\n  C-->A",
                expected_nodes=3, expected_edges=True, expect_legend=False),
    DiagramCase("multi-back-edges", "flowchart LR\n  A-->B\n  B-->C\n  C-->A\n  B-->A",
                expected_nodes=3, expected_edges=True, expect_legend=False),
    DiagramCase("legend-trigger", "flowchart TB\n  A-->B\n  A-.->C\n  B==>C",
                expected_nodes=3, expected_edges=True, expect_legend=True),
    DiagramCase("subgraph", "flowchart LR\n  subgraph sg[Group]\n    A-->B\n  end\n  B-->C",
                expected_nodes=3, expected_edges=True, expect_legend=True),
    DiagramCase("long-labels", "flowchart TB\n  A[Authentication Service] --> B[Authorization Gateway]\n  B --> C[Data Access Layer]",
                expected_nodes=3, expected_edges=True, expect_legend=False),
    DiagramCase("sequence", "sequenceDiagram\n  A->>B: request\n  B-->>A: response",
                expected_nodes=2, expected_edges=True, expect_legend=False),
]


# ── Playwright availability ───────────────────────────────────────────────────

def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


# ── Fragment generation ───────────────────────────────────────────────────────

def _render_fragment(source: str) -> tuple[bool, str]:
    """Run mermaid_layout and return (ok, html_fragment_or_error)."""
    ml = ROOT / "scripts" / "mermaid_layout"
    r = subprocess.run(
        [sys.executable, str(ml), "--source", source, "--width-hint", "840"],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        return False, r.stderr or r.stdout
    return True, r.stdout


# ── Evaluation ────────────────────────────────────────────────────────────────

def _evaluate(case: DiagramCase, dom: dict) -> list[Finding]:
    findings: list[Finding] = []

    def fail(check_id: str, detail: str) -> None:
        findings.append(Finding(case=case.name, check_id=check_id, severity="FAIL", detail=detail))

    def warn(check_id: str, detail: str) -> None:
        findings.append(Finding(case=case.name, check_id=check_id, severity="WARN", detail=detail))

    # DIAG-01: diagram canvas present
    if not dom.get("hasDiagram"):
        fail("DIAG-01", "no .diagram.mermaid-layout or .diagram-lifeline found")

    # DIAG-02: node count
    node_count = dom.get("nodeCount", 0)
    if node_count < case.expected_nodes:
        fail("DIAG-02", f"nodeCount {node_count} < expected {case.expected_nodes}")
    elif node_count > case.expected_nodes + 2:
        warn("DIAG-02", f"nodeCount {node_count} > expected {case.expected_nodes}+2 (extra nodes?)")

    # DIAG-03: edges present when expected
    if case.expected_edges:
        edge_count = dom.get("edgePathCount", 0)
        if edge_count < 1:
            fail("DIAG-03", f"expected edges but edgePathCount={edge_count}")

    # DIAG-04: legend present when expected
    legend_present = dom.get("legendPresent", False)
    if case.expect_legend and not legend_present:
        fail("DIAG-04", "expected .diagram-legend but it is absent")

    # DIAG-05: legend at bottom
    if legend_present:
        lab = dom.get("legendAtBottom")
        if lab is not None and not lab.get("isAtBottom", True):
            gap = lab.get("gapPx", -1)
            warn("DIAG-05", f"legend gap {gap}px from bottom of wrapper (expected < 30px)")

    # DIAG-06: overflow nodes
    overflow = dom.get("overflowNodes", [])
    if overflow:
        fail("DIAG-06", f"overflowing nodes: {overflow}")

    # DIAG-07: nodes outside canvas
    outside = dom.get("outsideNodes", [])
    if outside:
        fail("DIAG-07", f"nodes outside canvas bounds: {outside}")

    # DIAG-08: canvas has non-zero size
    cs = dom.get("canvasSize")
    if cs is None:
        fail("DIAG-08", "canvas element not found (canvasSize is null)")
    elif cs.get("w", 0) <= 50 or cs.get("h", 0) <= 20:
        fail("DIAG-08", f"canvas has near-zero size: {cs}")

    # DIAG-09: unexpected legend
    if not case.expect_legend and legend_present:
        warn("DIAG-09", "legend appeared but was not expected for this case")

    return findings


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not _playwright_available():
        print("[SKIP] diagram_render_check: playwright not available")
        return 0

    # Phase 1: render each case to HTML
    import shutil
    tmp_html_files: list[tuple[DiagramCase, str | None, str]] = []
    tmpdir = tempfile.mkdtemp(prefix="diag_render_check_")

    for case in CASES:
        ok, fragment = _render_fragment(case.source)
        if not ok:
            tmp_html_files.append((case, None, fragment))
            continue

        html = FIXTURE_TEMPLATE.format(fragment=fragment)
        tmp_path = str(Path(tmpdir) / f"{case.name}.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html)
        tmp_html_files.append((case, tmp_path, ""))

    # Phase 2: run Playwright on all available HTML files
    dom_results: dict[str, dict] = {}

    config_items = [
        (case, tmp_path)
        for case, tmp_path, _ in tmp_html_files
        if tmp_path is not None
    ]

    if config_items:
        try:
            with get_browser() as browser:
                for case, tmp_path in config_items:
                    page = browser.new_page()
                    _setup_page(page, width=1280, height=900)
                    page.goto("file://" + tmp_path, wait_until="networkidle", timeout=30000)
                    page.evaluate("async () => { await document.fonts.ready; }")
                    dom = page.evaluate(_DOM_INSPECT_JS)
                    dom_results[case.name] = dom
                    page.close()
        except RuntimeError as e:
            print(f"[SKIP] diagram_render_check: {e}")
            shutil.rmtree(tmpdir, ignore_errors=True)
            return 0
        except Exception as e:
            print(f"[ERROR] Playwright script failed: {e}", file=sys.stderr)

    shutil.rmtree(tmpdir, ignore_errors=True)

    # Phase 3: evaluate findings
    all_findings: list[Finding] = []

    CHECKS_PER_CASE = 9  # DIAG-01 through DIAG-09

    print(f"\ndiagram_render_check — {len(CASES)} cases")
    print("─" * 60)

    for case, tmp_path, render_error in tmp_html_files:
        if tmp_path is None:
            findings = [Finding(case=case.name, check_id="DIAG-00", severity="FAIL",
                                detail=f"mermaid_layout failed: {render_error[:100]}")]
        elif case.name not in dom_results:
            findings = [Finding(case=case.name, check_id="DIAG-00", severity="FAIL",
                                detail="Playwright did not return DOM result for this case")]
        else:
            dom = dom_results[case.name]
            findings = _evaluate(case, dom)

        all_findings.extend(findings)

        fails = [f for f in findings if f.severity == "FAIL"]
        warns = [f for f in findings if f.severity == "WARN"]

        if not findings:
            print(f" {case.name:<22} ✓ {CHECKS_PER_CASE}/{CHECKS_PER_CASE} checks")
        elif not fails and warns:
            warn_summary = "; ".join(f"{w.check_id}: {w.detail}" for w in warns)
            print(f" {case.name:<22} ~ WARN  {warn_summary}")
        else:
            fail_summary = "; ".join(f"{f.check_id}: {f.detail}" for f in fails)
            print(f" {case.name:<22} ✗ FAIL  {fail_summary}")
            if warns:
                for w in warns:
                    print(f"   {'':22}  WARN  {w.check_id}: {w.detail}")

    print("─" * 60)

    total_fails = sum(1 for f in all_findings if f.severity == "FAIL")
    total_warns = sum(1 for f in all_findings if f.severity == "WARN")
    pass_count = sum(
        1 for case, tmp_path, _ in tmp_html_files
        if not any(f.case == case.name and f.severity == "FAIL" for f in all_findings)
        and not any(f.case == case.name and f.severity == "WARN" for f in all_findings)
    )
    warn_only_count = sum(
        1 for case, tmp_path, _ in tmp_html_files
        if not any(f.case == case.name and f.severity == "FAIL" for f in all_findings)
        and any(f.case == case.name and f.severity == "WARN" for f in all_findings)
    )

    print(f"SUMMARY: {pass_count} pass, {total_warns} warn, {total_fails} fail")
    print()

    if total_fails > 0:
        return 1
    if total_warns > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

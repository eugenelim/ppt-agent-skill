"""Report generation: JSON, Markdown, and optional HTML."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ComparisonStatus
from .runner import CaseRunResult, RunSummary
from .serialization import to_json


def generate_json_report(
    summary: RunSummary,
    report_dir: Path,
    ref_id: str,
) -> Path:
    """Write report.json and return its path."""
    report_dir.mkdir(parents=True, exist_ok=True)
    data = _build_report_dict(summary, ref_id)
    out = report_dir / "report.json"
    out.write_text(to_json(data), encoding="utf-8")
    return out


def generate_md_report(
    summary: RunSummary,
    report_dir: Path,
    ref_id: str,
) -> Path:
    """Write report.md and return its path."""
    report_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Mermaid Fidelity Report — Phase 1")
    lines.append(f"\nReference: `{ref_id}`")
    lines.append(f"\n**{summary.passed}/{summary.total}** cases passed")
    lines.append(f"\n### Lifecycle Breakdown\n")
    lines.append(f"- **Active** (native-rendered): {summary.active_passed}/{summary.active_total} passed")
    if summary.active_failed:
        lines.append(f"  - {summary.active_failed} active failure(s) — must be fixed before merge")
    lines.append(
        f"- **Planned** (native not yet implemented): "
        f"{summary.planned_unsupported}/{summary.planned_total} unsupported (expected)"
    )
    if summary.semantic_mismatches:
        lines.append(f"\n- {summary.semantic_mismatches} semantic mismatch(es)")
    if summary.quality_failures:
        lines.append(f"- {summary.quality_failures} quality failure(s)")
    if summary.extractor_gaps:
        lines.append(f"- {summary.extractor_gaps} extractor gap(s)")
    if summary.parse_mismatches:
        lines.append(f"- {summary.parse_mismatches} parse mismatch(es)")
    if summary.other_failures:
        lines.append(f"- {summary.other_failures} other failure(s)")

    lines.append("\n## Cases\n")
    lines.append("| Case | Status | Reason |")
    lines.append("| ---- | ------ | ------ |")
    for r in summary.results:
        icon = "✓" if r.final_status == ComparisonStatus.PASS else "✗"
        reason = (r.reason or "")[:80]
        lines.append(f"| `{r.case_id}` | {icon} {r.final_status.value} | {reason} |")

    lines.append("\n## Scored Metrics\n")
    lines.append("Scored metrics are informational only and do not gate CI.\n")
    lines.append("| Case | Center Err | Width Err | Height Err | Canvas Δ | Text Lines |")
    lines.append("| ---- | ---------- | --------- | ---------- | -------- | ---------- |")
    for r in summary.results:
        if r.scored_metrics:
            m = r.scored_metrics
            ce = _fmt(m.normalized_entity_center_error)
            we = _fmt(m.median_entity_width_error)
            he = _fmt(m.median_entity_height_error)
            ca = _fmt(m.canvas_aspect_delta)
            tl = _fmt(m.text_line_agreement)
            lines.append(f"| `{r.case_id}` | {ce} | {we} | {he} | {ca} | {tl} |")

    out = report_dir / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_html_report(
    summary: RunSummary,
    report_dir: Path,
    ref_id: str,
) -> Path:
    """Write a minimal self-contained index.html and return its path."""
    report_dir.mkdir(parents=True, exist_ok=True)
    data = _build_report_dict(summary, ref_id)

    rows = ""
    for r in summary.results:
        color = "#2d6a2d" if r.final_status == ComparisonStatus.PASS else "#8b0000"
        reason = (r.reason or "")[:120]
        rows += (
            f'<tr><td><code>{r.case_id}</code></td>'
            f'<td style="color:{color}">{r.final_status.value}</td>'
            f'<td>{reason}</td></tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Mermaid Fidelity Report</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;}}
th{{background:#f0f0f0;}}
.pass{{color:#2d6a2d;}} .fail{{color:#8b0000;}}
</style></head>
<body>
<h1>Mermaid Fidelity Report — Phase 1</h1>
<p>Reference: <code>{ref_id}</code></p>
<p><strong>{summary.passed}/{summary.total}</strong> cases passed</p>
<p>Active: {summary.active_passed}/{summary.active_total} | Planned unsupported: {summary.planned_unsupported}/{summary.planned_total}</p>
<table>
<tr><th>Case</th><th>Status</th><th>Reason</th></tr>
{rows}
</table>
<details><summary>Raw JSON</summary>
<pre style="overflow:auto;background:#f5f5f5;padding:1em;">{to_json(data)}</pre>
</details>
</body></html>
"""
    out = report_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def _build_report_dict(summary: RunSummary, ref_id: str) -> dict:
    cases_data: list[dict] = []
    for r in summary.results:
        case_data: dict = {
            "case_id": r.case_id,
            "final_status": r.final_status.value,
            "reason": r.reason,
            "diagnostics": r.diagnostics,
        }
        if r.native_obs:
            nat = r.native_obs
            case_data["parse_status"] = {
                "accepted": nat.parse_result.accepted,
                "diagram_type": nat.parse_result.diagram_type,
            }
            if nat.geometry and nat.geometry.canvas_bounds:
                cb = nat.geometry.canvas_bounds
                case_data["native_canvas"] = {
                    "width": cb.width,
                    "height": cb.height,
                }
            if nat.geometry and nat.geometry.content_bounds:
                ctb = nat.geometry.content_bounds
                case_data["native_content"] = {
                    "width": ctb.width,
                    "height": ctb.height,
                }
        if r.semantic_result:
            sd = r.semantic_result
            case_data["semantic"] = {
                "passed": sd.passed,
                "diff_lines": sd.diff.to_lines(),
                "strict_fields_checked": sd.strict_fields_checked,
            }
        if r.scored_metrics:
            m = r.scored_metrics
            case_data["scored_metrics"] = {
                "normalized_entity_center_error": m.normalized_entity_center_error,
                "median_entity_width_error": m.median_entity_width_error,
                "median_entity_height_error": m.median_entity_height_error,
                "content_aspect_delta": m.content_aspect_delta,
                "canvas_aspect_delta": m.canvas_aspect_delta,
                "text_line_agreement": m.text_line_agreement,
                "crossing_count_delta": m.crossing_count_delta,
                "bend_count_delta": m.bend_count_delta,
            }
        if r.native_obs and r.native_obs.artifact_refs:
            case_data["artifacts"] = r.native_obs.artifact_refs
        cases_data.append(case_data)

    return {
        "schema_version": 1,
        "ref_id": ref_id,
        "summary": {
            "total": summary.total,
            "passed": summary.passed,
            "active_total": summary.active_total,
            "active_passed": summary.active_passed,
            "active_failed": summary.active_failed,
            "planned_total": summary.planned_total,
            "planned_unsupported": summary.planned_unsupported,
            "semantic_mismatches": summary.semantic_mismatches,
            "quality_failures": summary.quality_failures,
            "extractor_gaps": summary.extractor_gaps,
            "parse_mismatches": summary.parse_mismatches,
            "other_failures": summary.other_failures,
        },
        "cases": cases_data,
    }


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.4f}"


def emit_oracle_report(result: "OracleResult", provenance: dict) -> dict:
    """Emit a stable JSON-serializable oracle report dict."""
    return {
        "fixture": result.fixture_stem,
        "source_hash": provenance.get("source_hash", ""),
        "status": result.status.value,
        "checks_executed": len(result.checks),
        "failed_checks": sum(1 for c in result.checks if not c.passed),
        "extractor_gaps": [d for d in result.diagnostics if "extractor" in d.lower()],
        "unsupported_fields": [d for d in result.diagnostics if "unsupported" in d.lower()],
        "native_backend_metadata": provenance.get("native_backend_metadata", {}),
        "reference_version_metadata": provenance.get("reference_version_metadata", {}),
    }

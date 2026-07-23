# Spec: smoke-skill-pre-existing-fixture-drift

**Mode**: Light

## Objective

Fix three pre-existing failures in `tools/smoke_skill.py` caused by fixture drift: stale heading
strings in assert_contains calls, missing runtime-style inject files, and a literal template
placeholder leaking through unfilled-vars detection.

## Acceptance Criteria

1. `python3 tools/smoke_skill.py` exits with `errors: 0`.

2. `resource-loader-resolve` and `resource-loader-resolve-snapshot` pass: assert_contains
   expects `## 6. KPI 指标卡 (kpi_card)` and `## 7. 指标行 (metric_row)`, which are the
   current headings inside `references/charts/basic.md`. `scripts/resource_loader.py` maps
   chart_type values (`kpi`, `metric-row`) to their grouped recipe file (`basic.md`) via a
   `_CHART_TYPE_TO_FILE` dict, mirroring the same mapping already in `planning_validator.py`.

3. `prompt-style-phase1` passes: `references/styles/runtime-style-rules.md` and
   `references/styles/runtime-style-palette-index.md` exist and are non-empty, so the
   `--inject-file` arguments in the smoke test command succeed.

4. `prompt-page-planning` passes: the literal `{{PAGE_NUM}}` example inside backticks in
   `references/playbooks/step4/page-planning-playbook.md` is replaced with single-brace
   `{PAGE_NUM}`, avoiding false-positive detection by `assert_no_unfilled_vars`.

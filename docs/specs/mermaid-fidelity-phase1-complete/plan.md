# Plan: Mermaid Fidelity Phase 1 — Complete End-to-End Harness

## Declined patterns

- Tempted to rewrite `run.py` from scratch using a clean argparse hierarchy; declining — minimal targeted fixes preserve existing behavior while adding the spec-required interface.
- Tempted to add a composite compatibility score to the report; declining — spec explicitly prohibits it.
- Tempted to add auto-probing of mmdc environment versions at every `run` invocation; declining — environment is pinned at capture time; prober only runs at `capture-reference`.
- Tempted to refactor `NativeAdapter` geometry extraction code path; declining — it remains as `NativeHtmlAdapter` secondary lane, unchanged.
- Tempted to add Playwright browser-geometry extraction to `native_svg.py` adapter in Checkpoint 1; declining — pure XML geometry extraction from SVG is sufficient for the Checkpoint 1 vertical slice.

## Resolve-vs-surface disposition

All items resolved with referent (spec + repo source inspection). No value-origination or irreversible-risk items require surfacing; oracle capture in Checkpoint 2 is manually inspected before committing per spec requirement.

---

**Status: Executing**

---

## Task T0a: Extend ComparisonStatus enum and fix gating set
Depends on: none
Verification: TDD

Done when:
- `ComparisonStatus` in `tools/mermaid_fidelity/models.py` gains `RELATIVE_LAYOUT_MISMATCH`, `STALE_ORACLE`, `INVALID_MANIFEST`
- `runner.py run_case` re-maps: missing oracle file → `STALE_ORACLE` (was `EXTRACTOR_GAP`); layout check failure → `RELATIVE_LAYOUT_MISMATCH` (was `SEMANTIC_MISMATCH`)
- `INVALID_MANIFEST` is emitted by `cmd_validate` in `cli.py` when the manifest fails structural checks (unknown checks, duplicates, or unsupported check for diagram family)
- `cli.py cmd_run` hard-fail inline status list (`cli.py:103-112`) extended with `RELATIVE_LAYOUT_MISMATCH`, `STALE_ORACLE`, `INVALID_MANIFEST`, **and `QUALITY_FAILURE`** — the complete gating set is exactly: `PARSE_MISMATCH, SEMANTIC_MISMATCH, RELATIVE_LAYOUT_MISMATCH, QUALITY_FAILURE, EXTRACTOR_GAP, STALE_ORACLE, INVALID_MANIFEST, NATIVE_UNSUPPORTED, NONDETERMINISTIC, INTERNAL_ERROR`
- Scored metric differences alone do not produce nonzero exit
- Existing 105 fidelity tests still pass (update any test asserting on old status string)

Tests: additions to `tests/fidelity/test_models.py`:
- `test_relative_layout_mismatch_status_exists`
- `test_stale_oracle_status_exists`
- `test_invalid_manifest_status_exists`
- `test_quality_failure_in_gating_set`

Approach:
- Add to `ComparisonStatus` enum in `models.py`
- In `runner.py run_case`: locate oracle-load path (`oracle_dir / ref_id / "cases" / ...`), change `FileNotFoundError` return status to `STALE_ORACLE`; locate layout-failure return, change to `RELATIVE_LAYOUT_MISMATCH`
- In `cli.py`: find the inline hard-fail status list and extend it (introduce `_HARD_FAIL_STATUSES` constant at module level to make it greppable, or extend the existing inline set — either way enumerate the complete set)

---

## Task T0b: Fix runner._deserialize_observation geometry/quality drop
Depends on: none
Verification: TDD

Done when:
- `runner._deserialize_observation(raw_dict)` (and helpers `_deserialize_semantic`, `_deserialize_geometry`, `_deserialize_quality`) reconstructs full `Observation` including geometry and quality
- Does not hardcode `geometry=None, quality=None`
- Test: load a committed oracle JSON file for a case that has geometry → assert `obs.geometry is not None`
- Round-trip test: `runner.run_case` loads oracle, `ref_obs.geometry` is populated

Tests: additions to `tests/fidelity/test_serialization_roundtrip.py`:
- `test_deserialize_preserves_geometry` — build obs with geometry, dump, load via `_deserialize_observation`, assert geometry not None
- `test_runner_loads_geometry_from_oracle` — write temp oracle file with geometry, run case, assert ref_obs.geometry not None

Approach:
- Inspect `runner.py` for `_deserialize_observation` (or equivalent)
- If it hardcodes `geometry=None`: implement proper recursive dict→dataclass reconstruction
- Use `Observation.from_dict()` pattern (same as T5 will write); if T5 creates it, T0b uses it — adjust T5 to be a pre-req if needed

---

## Task T0c: Fix run.py to delegate to cli.py
Depends on: T0a
Verification: goal-based

Done when:
- `run.py main()` builds parser via `mermaid_fidelity.cli.build_parser()` or equivalent and delegates each command to `cli.cmd_run / cmd_capture_reference / cmd_determinism / cmd_validate`
- `run.py` provides only: sys.path setup, manifest_loader, profile_loader, native_adapter_factory, ref_adapter_factory callbacks
- No duplicate CLI logic (argument parsing, overwrite guard, format-specific report writing) in run.py
- All argument-level fixes from old T1 happen in `cli.py` if not already there (--case alias, --runs, --output, --force, cmd_determinism dict-return crash)
- `python3 tests/fidelity/run.py run --case flowchart.groups.complex --report-dir /tmp/p1` no argparse error
- `python3 tests/fidelity/run.py validate` exits 0
- `python3 tests/fidelity/run.py capture-reference --output tests/fidelity/oracle/mermaid-11.15.0-neutral` exits nonzero with "would overwrite" message
- `python3 tests/fidelity/run.py determinism --runs 3 --report-dir /tmp/p1-det` no crash

Approach:
- Read `tools/mermaid_fidelity/cli.py` fully to understand its dependency-injection API
- Verify `cli.py cmd_run` already calls `runner.run_all(manifest, profile, ref_id, ...)` correctly
- Verify `cli.py cmd_determinism` handles dict return correctly
- Verify `cli.py` already has `--case`, `--force`, `--runs`, `--report-dir` on the right subparsers
- Rewrite `run.py main()` to call `cli.build_parser()` + pass callbacks; remove duplicate cmd_* functions from run.py
- Keep sys.path setup and callback factories in run.py (repo-specific, correct to live there)

---

## Task T0: Fix NodeLayout.parent_group_id AttributeError
Depends on: none
Verification: TDD

Done when:
- `NodeLayout` in `_geometry.py` gains `parent_group_id: Optional[str] = None`
- All 20 previously-failing `to_svg` tests pass
- Existing 105 fidelity unit tests still pass

Tests: `tests/test_mermaid_layout.py`, `tests/test_svg_bounds.py`, `tests/test_fix_flowchart.py`, `tests/test_flowchart_geometry.py`, `tests/test_syntax_flowchart.py` (all 20 previously-failing)

Approach:
- Add `parent_group_id: Optional[str] = None` to `NodeLayout` in `_geometry.py:278` (after `accent_color`)
- Existing `_renderer.py:1667` already reads `nl.parent_group_id`; FinalizedLayout assemblers must populate it from group membership
- Check `render_finalized()` assembler to confirm it sets `parent_group_id` on `NodeLayout` from the group tree
- If assembler doesn't set it, trace how `NodeLayout` is constructed and add it there

---

## Task T1: (merged into T0c — see above)

---

## Task T2: Create tests/fidelity/adapters/native_svg.py
Depends on: T0, T4
Verification: goal-based

Done when:
- `NativeSvgAdapter` in `adapters/native_svg.py` exists and implements `FidelityAdapter` protocol
- Calls `mermaid_render.to_svg(source)` (public API, no internal renderer functions)
- Extracts semantic `Entity`, `Relation`, `Group` objects from `data-*` attributes in the SVG
- Returns complete `Observation` with `parse_result`, `semantic`, `geometry=None` (geometry added in T14), `quality=None`
- Returns `NATIVE_UNSUPPORTED` for `ValueError` from `to_svg()`
- Returns `INTERNAL_ERROR` for unexpected exceptions
- Retains raw SVG bytes as optional diagnostic artifact
- `run.py` uses `NativeSvgAdapter` as the authoritative native adapter

Approach:
- Import `to_svg` from `mermaid_render`
- Parse SVG as XML via `xml.etree.ElementTree` (safe, no lxml dependency)
- Extract `data-node-id`, `data-kind`, `data-label`, `data-shape`, `data-order`, `data-parent-id` from SVG elements
- Extract `data-src`, `data-dst`, `data-relation-id`, `data-arrow` from path/line elements
- Extract `data-group-id`, `data-group-label` from group elements
- Infer `diagram_type` from `data-diagram-type` on root SVG element
- Use `ImplementationIdentity(name="mermaid_render_svg", ...)`
- Note: this adapter depends on T4 (semantic attributes on SVG) to work fully

---

## Task T3: Rename NativeAdapter → NativeHtmlAdapter
Depends on: T0c, T2
Verification: goal-based

Done when:
- `adapters/native.py` renames `NativeAdapter` class to `NativeHtmlAdapter`
- Module docstring updated to state "secondary HTML consistency lane"
- `run.py` no longer imports `NativeAdapter`; imports `NativeSvgAdapter` as primary, `NativeHtmlAdapter` optionally for consistency lane
- No import errors in existing tests (test_phase1.py imports are updated if needed)

Approach:
- Rename class in-place; add `NativeAdapter = NativeHtmlAdapter` backward-compat alias for existing tests
- Update module docstring
- Update run.py import

---

## Task T4: Add semantic data attributes to native SVG output
Depends on: T0
Verification: TDD

Done when:
- `scripts/mermaid_render/native_svg.py` scene builders emit `data-semantic-id`, `data-kind`, `data-label`, `data-shape`, `data-order`, `data-parent-id` on node `_SceneElement` objects
- `scripts/mermaid_render/native_svg.py` scene builders emit `data-src`, `data-dst`, `data-relation-id`, `data-arrow`, `data-relation-kind` on edge `_SceneElement` objects
- `scripts/mermaid_render/native_svg.py` scene builders emit `data-group-id`, `data-group-label` on group `_SceneElement` objects
- `svg_serializer.py` writes `data-{name}="{value}"` for each `data_attrs` entry (already does via `_SceneElement.data_attrs`)
- Stripping only the new `data-*` attributes produces identical visual SVG (no geometry or style change)
- All existing `to_svg()` tests still pass
- New focused serializer tests for each new attribute

Tests: `tests/test_svg_attributes.py` (new file)
- `test_node_semantic_id_present` — `data-node-id` / `data-semantic-id` on node element
- `test_edge_src_dst_present` — `data-src` and `data-dst` on edge element
- `test_group_id_present` — `data-group-id` on group element
- `test_attribute_strip_geometry_unchanged` — strip data-* attrs, compare geometry
- `test_parent_id_set_for_grouped_node` — node inside subgraph has `data-parent-id`

Approach:
- Inspect `_graph_topology_scene` in `native_svg.py` to find where `_SceneElement` objects are created for nodes, edges, groups
- Pass `data_attrs=(("node-id", node_id), ("kind", "node"), ("label", label), ("shape", shape), ("order", str(order)), ("parent-id", parent_id))` to node elements
- Pass `data_attrs=(("src", src), ("dst", dst), ("relation-id", rel_id), ("arrow", arrow))` to edge elements
- Pass `data_attrs=(("group-id", group_id), ("group-label", label))` to group elements
- Note: `data_attrs` are `(name, value)` pairs; serializer writes `data-{name}="{value}"`
- Use real semantic scene data only (from scene builder's input topology); no text reconstruction
- Escape attribute values with `html.escape`

---

## Task T5: Verify and complete JSON round-trip
Depends on: T0b
Verification: TDD

Done when:
- `Observation` fully round-trips via `to_json` / `load_json` → `_deserialize_observation`: every field preserved
- No `None` substitution for geometry/quality after loading (relies on T0b fix)
- Test `loads(dumps(obs)) == obs` passes for an `Observation` with all fields populated
- Deserialization handles nested dataclasses: `BoundingBox`, `EntityGeometry`, `RelationGeometry`, `GroupGeometry`, `Entity`, `Relation`, `Group`, `OrderedEvent`, `SemanticDiagram`, `GeometryObservation`, `QualityObservation`
- Exclude `capture_timestamp` from equality check

Tests: `tests/fidelity/test_serialization_roundtrip.py` (new file)
- `test_full_observation_roundtrip` — build populated Observation, dump, load, assert equal
- `test_geometry_roundtrip` — GeometryObservation with all sub-fields
- `test_quality_roundtrip` — QualityObservation with various QualityFindingKind values
- `test_semantic_roundtrip` — SemanticDiagram with entities/relations/groups/ordered_events

Approach:
- Inspect `serialization.py` `to_json` / `load_json`: if `load_json` returns raw dict, add `Observation.from_dict(d)` classmethod (or improve `_deserialize_observation` in runner.py — T0b)
- Keep `to_json` using existing `dataclasses.asdict` + JSON encoding
- T0b owns the fix; T5 owns the test coverage

---

## Task T6: Safe reference overwrite behavior
Depends on: T0c
Verification: TDD

Done when:
- `run.py capture-reference --output <dir>` refuses to overwrite existing files (environment.json or any case/*.json) and exits nonzero
- `run.py capture-reference --output <dir> --force` overwrites atomically (write to `.tmp` then rename)
- Interrupted capture leaves previous oracle intact
- Lists files that would be replaced when refusing

Tests: `tests/fidelity/test_capture_reference.py` (new file)
- `test_refuses_overwrite_without_force` — create existing case file, run without --force, assert exit 1 and file listing
- `test_force_overwrites_atomically` — mock adapter returning known obs, run with --force, assert file updated
- `test_interrupted_capture_leaves_oracle_intact` — mock write failure midway, assert old file unchanged

Approach:
- In `cmd_capture_reference`: before writing, collect existing files that would be overwritten
- If any exist and `--force` not set: print file list, return nonzero
- With `--force`: write to `{path}.tmp` then `os.replace(tmp, path)` (atomic on POSIX)

---

## Task T7: End-to-end vertical slice smoke test
Depends on: T0, T0a, T0b, T0c, T2, T3, T4, T5, T6
Verification: goal-based

Done when:
- `python3 tests/fidelity/run.py run --case flowchart.groups.complex --report-dir /tmp/p1-smoke` completes without exception
- `report.json` and `report.md` are produced
- No INTERNAL_ERROR status in output
- Case appears in the report

Approach:
- This is an integration smoke — execute the command, observe output
- If oracle file missing for case, status is STALE_ORACLE (not INTERNAL_ERROR) — that's acceptable at this stage

---

## Task T8: Pin and probe the reference environment
Depends on: T0c
Verification: goal-based

Done when:
- `oracle/mermaid-11.15.0-neutral/environment.json` populated with actually-probed values for: mermaid_version, mermaid_integrity, mmdc_version, playwright_version, chromium_revision, node_version, viewport_width/height, device_scale_factor, locale, timezone, reduced_motion, mermaid_config_hash, css_profile_hash, font_info
- No unresolved semver range used as reference identity
- Capture timestamps excluded from fingerprints
- `capture-reference` command probes environment at capture time and writes environment.json

Approach:
- Add `_probe_environment()` to `adapters/reference.py` that runs:
  - `mmdc --version` → mmdc_version
  - Node.js: `node --version`
  - Playwright: `playwright.__version__`
  - Chromium: detect from Playwright browser executable path
  - Hash `mermaid-neutral.json` config → mermaid_config_hash
  - Hash `native-neutral.css` → css_profile_hash
  - Hash installed mermaid npm package → mermaid_integrity
- Update `environment.json` via `capture-reference`

---

## Task T9: Improve reference adapter — flowchart family
Depends on: T8
Verification: goal-based

Done when:
- `ReferenceAdapter.observe()` for flowchart cases extracts: direction, node IDs, labels, shapes, edges with source/target/label/arrow, subgraph containment, nested groups
- All 11 flowchart cases can be captured without EXTRACTOR_GAP for strict fields
- `EXTRACTOR_GAP` returned (not silent None) for any field that can't be extracted

Approach:
- Use Mermaid parser (via `mmdc --parse-only` or embedded Node.js) for semantic extraction
- Parse rendered SVG for geometry fallback
- Return `EXTRACTOR_GAP` object with field/case/reason for gaps

---

## Task T10: Improve reference adapter — sequence, architecture, ER families
Depends on: T9
Verification: goal-based

Done when:
- Sequence cases extract: actors, actor order, messages with exact order, source/target, label, arrow type, activations, notes, blocks
- Architecture cases extract: services, groups, containment, connections, connection direction
- ER cases extract: entities, relationships, cardinality at both endpoints, identifying state

---

## Task T11: Capture all 24 oracle observations
Depends on: T9, T10
Verification: goal-based (requires manual inspection)

Done when:
- `oracle/mermaid-11.15.0-neutral/cases/{case_id}.json` exists for all 24 cases
- Each file passes schema validation (correct schema_version, required fields)
- Source hash in each file matches current fixture file hash
- No case has REFERENCE_RENDER_FAILURE or INTERNAL_ERROR status
- Each captured case manually inspected before commit

Approach:
- Run `capture-reference --force` for all 24 cases
- Inspect each JSON for plausible semantic content
- Commit only after inspection

---

## Task T11b: Implement cmd_validate oracle-integrity checks
Depends on: T11
Verification: goal-based

Done when:
- `cli.py cmd_validate` (and `run.py validate`) checks all six oracle-integrity conditions:
  1. Every manifest case ID has a corresponding `oracle/<ref_id>/cases/<case_id>.json` file
  2. No unexpected JSON files in `oracle/<ref_id>/cases/` (no case IDs not in manifest)
  3. All oracle files use expected `schema_version`
  4. All oracle files use the same reference identity (implementation name + version)
  5. No strict field in any oracle file has an unresolved `EXTRACTOR_GAP` status (when strict check is declared for the case)
  6. Every oracle file's `source_hash` matches SHA256 of the current fixture file
- Validation fails with `INVALID_MANIFEST` / nonzero exit on any violation
- Lists all violations before exiting
- `python3 tests/fidelity/run.py validate` exits 0 after T11 oracle capture

Approach:
- Extend `cmd_validate` in `cli.py` after manifest parse: load environment.json, iterate oracle cases dir, perform all six checks
- `INVALID_MANIFEST` status returned for structural violations; report them all

---

## Task T12: Fix semantic multiplicity — parallel edges
Depends on: none
Verification: TDD

Done when:
- `flowchart.parallel.links` regression test verifies 2 parallel A→B edges remain 2 distinct relations
- `compare_semantic` uses multiset-compatible canonical key: `(kind, source, target, label, arrow, order)` — not a set-keyed dedup
- `stable_relation_id` in `canonical.py` produces distinct IDs for parallel edges
- Duplicate-count differences are reported

Tests: additions to `tests/fidelity/test_comparators.py`:
- `test_parallel_edges_not_collapsed`
- `test_parallel_edge_count_diff_detected`

Approach:
- Inspect `compare/semantic.py` compare logic for relations — if it uses `{(src, dst): relation}` dict, switch to list-based multiset comparison
- Use `Counter` keyed on canonical relation tuple for count comparison

---

## Task T13: Make missing strict data explicit — EXTRACTOR_GAP
Depends on: none
Verification: TDD

Done when:
- A missing native shape does not match a populated reference shape (no silent None == None pass)
- An unavailable reference field returns `EXTRACTOR_GAP` status (not PASS)
- An unavailable native field returns `EXTRACTOR_GAP` status
- `ComparisonStatus.EXTRACTOR_GAP` causes nonzero exit per spec status/exit behavior

Tests: additions to `tests/fidelity/test_comparators.py`:
- `test_missing_native_shape_is_not_pass`
- `test_ref_extractor_gap_surfaces`
- `test_native_extractor_gap_surfaces`

---

## Task T14: Complete SVG geometry extraction in native_svg adapter
Depends on: T2, T4
Verification: TDD

Done when:
- `NativeSvgAdapter` extracts from SVG XML: viewBox, SVG width/height, entity bbox (from `<rect>/<circle>` inside node groups), group bbox, relation path sample points (32 per connector), source/target endpoints, bend count
- Uses pure XML parsing (no browser) for geometry from SVG element coordinates
- For transforms: resolves `translate(x y)` on group elements to absolute coordinates
- Returns populated `GeometryObservation` with `content_bounds`, `canvas_bounds`, `viewbox`

Tests: additions to `tests/fidelity/test_native_svg_adapter.py`:
- `test_entity_bbox_extracted`
- `test_viewbox_extracted`
- `test_relation_path_sampled`

---

## Task T15: Implement strict relative-layout checks
Depends on: T14
Verification: TDD

Done when:
- `compare_relative_layout()` in `compare/geometry.py` executes manifest strict checks:
  - diagram direction (TB/LR/BT/RL) agreement
  - major rank / above-below relations
  - actor left-to-right order
  - message order
  - group containment
  - nested group containment
  - semantic sibling order
  - relation endpoint identity
  - required object visibility
- Uses named tolerances from `QualityTolerances`

Tests: additions to `tests/fidelity/test_comparators.py`:
- `test_direction_mismatch_detected`
- `test_containment_violation_detected`

---

## Task T16: Implement scored layout metrics (report-only, not CI gate)
Depends on: T14, T15
Verification: TDD

Done when:
- `score_layout_metrics()` computes all 13 metrics independently:
  normalized_entity_center_error, median_entity_width_error, median_entity_height_error, text_line_agreement, content_aspect_delta, canvas_aspect_delta, whitespace_density_delta, group_padding_delta, bend_count_delta, crossing_count_delta, endpoint_side_agreement, sampled_connector_path_distance, relation_label_position_error
- No composite score
- Metrics included in report but do not produce nonzero exit

Tests: additions to `tests/fidelity/test_comparators.py`:
- `test_scored_metrics_all_present`
- `test_scored_metrics_no_gate_failure`

---

## Task T17: Complete native quality checks
Depends on: T14
Verification: TDD

Done when:
- `run_quality_checks()` in `compare/quality.py` detects all spec-required conditions:
  clipped text, content outside viewBox, zero-area semantic objects, invisible semantic objects, missing SVG elements, substantial unrelated entity overlap, child elements outside declared groups, detached relation endpoints, wrong-semantic-object endpoint attachment, relation labels outside canvas, malformed/non-finite geometry
- Reuses predicates from `tools/diagram_render_check.py` where applicable
- Existing `diagram_render_check.py` CLI behavior unchanged

Tests: additions to `tests/fidelity/test_comparators.py` or new `test_quality_checks.py`:
- `test_clipped_text_detected`
- `test_outside_canvas_detected`
- `test_overlap_detected`
- `test_detached_endpoint_detected`

---

## Task T18: Honor manifest exactly — validate all check names
Depends on: T12, T13, T15, T16, T17
Verification: TDD

Done when:
- Every check name in `cases.toml` maps to an implemented comparator capability
- `validate` command fails on unknown checks, duplicates, unsupported-strict, unimplemented-scored, family-inappropriate checks
- Runner does not use a hidden fixed check set ignoring the manifest
- Check-name-to-comparator mapping is explicit:
  - Strict: `parse` → ParseObservation.accepted; `diagram-type` → SemanticDiagram.diagram_type; `entities` → entity set comparison; `relations` → relation set comparison; `labels` → entity/relation label comparison; `direction` → SemanticDiagram.direction; `containment` → group membership comparison; `edge-endpoints` → relation source/target; `actor-order` → ordered_events order; `message-order` → ordered_events order; `cardinality` → Relation cardinality attributes; `identifying` → Relation identifying state
  - Scored: `entity-centers` → normalized_entity_center_error; `entity-sizes` → median_entity_width/height_error; `canvas-aspect` → canvas_aspect_delta; `connector-paths` → sampled_connector_path_distance; `text-lines` → text_line_agreement; `group-padding` → group_padding_delta; `crossing-count` → crossing_count_delta; `bend-count` → bend_count_delta; `whitespace-density` → whitespace_density_delta; `endpoint-side` → endpoint_side_agreement

Tests: additions to `tests/fidelity/test_manifest.py`:
- `test_unknown_check_fails_validation`
- `test_duplicate_check_fails_validation`
- `test_all_cases_toml_checks_map_to_comparator`

---

## Task T19: Expand mutation tests
Depends on: T12, T13, T17
Verification: TDD

Done when:
- `tests/fidelity/test_mutations.py` covers all 19 spec-required mutations:
  1. deleted relation
  2. reversed relation
  3. extra phantom entity
  4. changed label
  5. changed shape
  6. changed parent group
  7. duplicate parallel-edge count change
  8. swapped sequence-message order
  9. changed arrow type
  10. changed ER cardinality
  11. changed identifying state
  12. child moved outside group
  13. substantial unrelated-node overlap
  14. detached endpoint
  15. changed diagram direction
  16. additional crossing
  17. text clipping
  18. palette-only change (no semantic failure)
  19. shadow-only change (no semantic failure)
  20. scored geometry change without hard failure

---

## Task T20: Full local run — all 24 cases
Depends on: T7, T11, T18, T19
Verification: goal-based

Done when:
- `python3 tests/fidelity/run.py run --report-dir tests/fidelity/reports/local` iterates all 24 cases
- `report.json` and `report.md` produced
- No INTERNAL_ERROR in output
- Command exits nonzero only if hard failures (SEMANTIC_MISMATCH etc.) present

---

## Task T21: Determinism validation
Depends on: T20
Verification: goal-based

Done when:
- `python3 tests/fidelity/run.py determinism --runs 3 --report-dir tests/fidelity/reports/determinism` completes
- Uses the 6-case determinism subset: flowchart.groups.complex, flowchart.parallel.links, flowchart.shapes.new, sequence.complex, architecture.groups.complex, er.ecommerce
- All canonical observations stable across 3 runs
- Differing JSON paths reported if nondeterministic

---

## Task T22: CI integration
Depends on: T20, T21
Verification: goal-based

Done when:
- `.github/workflows/tests.yml` existing `fidelity-phase1` job (browser-free, Python job) is extended to also run:
  `python3 tests/fidelity/run.py validate`
  `python3 tests/fidelity/run.py run --report-dir tests/fidelity/reports/ci`
  `python3 tests/fidelity/run.py determinism --runs 3 --report-dir tests/fidelity/reports/determinism-ci`
- This job consumes committed oracle JSON (no mmdc re-capture)
- Artifacts uploaded with `always()` condition: report.json, report.md, native SVG artifacts for failing cases, determinism diffs
- Hard failure statuses (PARSE_MISMATCH/SEMANTIC_MISMATCH/RELATIVE_LAYOUT_MISMATCH/QUALITY_FAILURE/EXTRACTOR_GAP/STALE_ORACLE/NONDETERMINISTIC/INTERNAL_ERROR) cause non-zero exit; scored metrics alone do not
- `fidelity-unit` job (browser-free unit tests) unchanged
- No other existing jobs weakened

Approach:
- The `fidelity-phase1` job in tests.yml currently runs `tests/fidelity/test_phase1.py -k "not TestReferenceAdapter"`
- Extend it to also run the three `run.py` commands after the pytest step
- Add artifact upload step with `if: always()`

---

## Task T23: Strengthen package boundary tests
Depends on: none
Verification: TDD

Done when:
- `tests/fidelity/test_core_boundary.py` verifications:
  1. Parses all imports under `tools/mermaid_fidelity/**/*.py`
  2. Rejects imports from `scripts`, `tests`, `mermaid_render`, `pytest`
  3. Rejects repository-root discovery via fixed parent traversal
  4. Rejects `sys.path` mutation in reusable core
  5. Imports `mermaid_fidelity` in subprocess with only `tools/` on PYTHONPATH
  6. Confirms Playwright not loaded by base-package import
  7. Confirms Pillow not loaded by base-package import
  8. Runs core unit tests without repository adapters
  9. Confirms no hardcoded `tests/fixtures` paths
  10. Confirms portable JSON contains no absolute paths

---

## Task T24: Update Phase 1 documentation
Depends on: T20, T21, T22
Verification: goal-based

Done when:
- `tests/fidelity/README.md` covers: native SVG target, HTML secondary lane, exact reference identity, capture/overwrite behavior, oracle validation, strict vs. scored checks, determinism, CI behavior, failure inspection, adding a new case, Phase 1 claims and non-claims, future extraction path
- Does not claim pixel identity or describe scored metrics as compatibility guarantees

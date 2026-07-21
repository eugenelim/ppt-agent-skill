# Adversarial Review Pass 1 — renderer-hardening-2026-07

## Blockers

**1. Status field uses a value outside the pinned vocabulary.** `spec.md:5`. `**Status:** In progress` is not one of `Draft | Approved | Implementing | Shipped | Archived` (CONVENTIONS §4). Fix: change to `Implementing`.

**2. `_best_label_pos` callers under-enumerated — plan will produce a runtime crash.** `plan.md:72-74` says update `_label_on_longest` plus "All direct calls in `_route_edges` self-loop section." There are nine call sites (`_routing.py:255,663,679,699,715,766,793,820,858`), most outside the self-loop section. Fix: enumerate and unwrap all nine call sites.

**3. AC-P2.1 test does not exercise the property it claims to verify.** `plan.md:353-375`. The proposed graph (`A→B→C→A` + `C→D`) is a single cycle — DFS and greedy both reverse exactly one edge. The "produces same or fewer reversals than DFS" claim is untested and also too strong (greedy doesn't guarantee fewer reversals on all graphs). Fix: replace with correctness assertion (no cycles remain after _break_cycles) plus determinism assertion.

**4. Two of AC-P4.1's three named tests are missing from the plan.** `spec.md:44` names `test_perimeter_retry_finds_path` and `test_routing_failure_omits_edge`; Task 7 writes only the first. Fix: add both missing tests.

## Concerns

**5. AC-P4.2 overflow behavior has no test.** `spec.md:46` names `test_allocate_face_ports_overflow`; Task 8 replaced it with a centering test. Fix: add overflow test asserting `lane` increments past capacity.

**6. AC-P0.5 gallery exit-code-1 has no durable test.** `spec.md:27` requires a test that `main()` exits 1, but `validate()` is a permanent empty stub. Fix: monkeypatch `_classify_status` in a committed test.

**7. Plan modifies `_strategies.py` outside spec's In-scope boundary.** `spec.md:64-72` omits `_strategies.py`. Fix: add it.

**8. AC-P4.3 reverse-edge fix is untested.** `plan.md:308-333` has two tests but both target back-edge path only; line 739 (`s.x >= d.x + NODE_W`) fix is untested. Fix: add reverse-edge test.

**9. Empty-candidates branch of `_best_label_pos` unaddressed.** `_routing.py:410-412` has a separate `if not candidates:` path returning `(0,0)`. After return-type change this branch must also return `LabelPlacement`. Fix: specify LabelPlacement for empty-candidates path.

**10. AC-P0.1 checked `[x]` while the code is unchanged.** `spec.md:19`. Fix: revert to `[ ]`.

**11. Priority source is unresolvable reference.** `spec.md:9,13` cites "the full review document attached to the workspace" with no in-repo path. Fix: commit the review doc and cite it.

## Nits

**12. Test names diverge between spec and plan.** `spec.md:48` vs `plan.md:322`. Fix: align names.

**13. Task DAG is fully serialized despite independent tasks.** Tasks 1 and 11 are independent. Fix: `Depends on: none`.

**14. Task 4 Touches omits `_strategies.py`.** Fix: add it.

**15. Plan has no Status field.** Fix: add plan Status header.

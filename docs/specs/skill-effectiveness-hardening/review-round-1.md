# Adversarial review — round 1 (implementation diff)

## Blockers

**1. Spec Testing Strategy & Risks contradict claim-only design.** `docs/specs/skill-effectiveness-hardening/spec.md:115`. Testing Strategy/Risks referenced a `--resume` test that intentionally doesn't exist. Fix: drop the resume test clause. — RESOLVED.

**2. Spec/plan metadata not advanced.** `docs/specs/skill-effectiveness-hardening/spec.md:7`. Status still Implementing, ACs unchecked. Fix: flip to Shipped/Done, check ACs. — RESOLVED.

## Concerns

**3. scripts/README.md edit outside declared Boundaries.** `scripts/README.md:10`. Bundled ride-along not declared. Fix: add to Touches list. — RESOLVED.

## Nits

**4. F4 index row attributes 23-file count loosely to tpl-*.** `SKILL.md:362`. Fix: reword to 23 文件（tpl-* 21 + module-* 2）. — RESOLVED.

Verified clean: F7 drops no grounding obligation (contract table byte-untouched); F2 tokenizes per-span correctly; resolve_output_dir.py preserves atomic-claim semantics; F5 tables byte-identical; F1 radar routes to advanced.md; gates 0/0.

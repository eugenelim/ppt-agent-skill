# Vendor Bundle Checksum Gate

- **Status:** Shipped
- **Slug:** vendor-bundle-checksum-gate

## Objective

Pin the SHA-256 checksum of `dom-to-svg.bundle.js` in both vendor locations and
verify it in CI, so accidental or malicious bundle replacement is detected
immediately.

## Boundaries

**Always do:**
- Use stdlib `hashlib` only — no new runtime dependencies.
- Exit 1 immediately after printing all mismatches (fail-all, not fail-fast).

**Never do:**
- Never auto-repair a mismatched bundle (verify-only; no download, no overwrite).
- Never fetch hashes from the network — PINNED values live in the source file.

## Testing Strategy

TDD: exercise both the match path (exit 0) and mismatch path (exit 1 +
`SHA-256 mismatch` on stderr) at the **process level** via subprocess so that
the `sys.exit(1)` wiring is proven, plus at the function level via
`monkeypatch.setattr(mod, "ROOT", tmp_path)` for unit clarity. The `--update`
flag is verified by asserting both exit 0 and `dom-to-svg.bundle.js` in stdout.

## Acceptance Criteria

- [x] `tools/check_bundle_hash.py` exists and exits 0 when both bundles match
      their pinned hashes.
- [x] `tools/check_bundle_hash.py` exits 1 and prints a descriptive error when
      either bundle does not match its pinned hash (verified at process level).
- [x] `--update` flag prints current hashes for PINNED dict update (exit 0).
- [x] A new CI job `vendor-bundle-checksum` in `.github/workflows/tests.yml`
      runs `python tools/check_bundle_hash.py` and `pytest tests/test_bundle_hash.py`,
      failing the build on mismatch.
- [x] `tests/test_bundle_hash.py` passes under `pytest tests/test_bundle_hash.py -v`
      covering match, mismatch (subprocess exit code), and `--update` paths.
- [x] `pytest tests/ -q --tb=short -x` passes.

## Tasks

1. Write `tools/check_bundle_hash.py` with hardcoded current SHA-256 hashes.
2. Add `tests/test_bundle_hash.py` covering match, mismatch (process-level exit 1),
   and `--update` flag.
3. Add `vendor-bundle-checksum` job to `.github/workflows/tests.yml`.

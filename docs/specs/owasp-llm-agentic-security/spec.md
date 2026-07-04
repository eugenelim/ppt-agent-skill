# OWASP LLM/Agentic Skills Security Hardening

Mode: light (no risk trigger fired — security hardening of existing code, no new features, no structural changes)

## Objective

Address the 6 Concerns and 2 Nits from the security-reviewer's OWASP LLM Top 10 / Agentic Skills Top 10 pass. Zero functional changes — only security hardening.

## Acceptance Criteria

- [x] AC1 (Concern 1): Puppeteer in html2svg.py, html2png.py, build_pdf.py blocks outbound HTTP(S) requests via `page.setRequestInterception`; `file://` and `data:` are allowed.
- [x] AC2 (Concern 2): `--no-sandbox` documented with security rationale and AST06 isolation declaration added to SKILL.md metadata.
- [x] AC3 (Concern 3): `sandbox="allow-same-origin"` removed from preview iframes in html_packager.py; srcdoc content uses opaque-origin sandboxing.
- [x] AC4 (Concern 4): npm version pins documented; SKILL.md pip install updated with `==` pins; `npx -y` replaced with version-pinned invocation; `package.json` + `package-lock.json` committed; `npm install` calls replaced with `npm ci`; `requirements.txt` added; `npm audit` + `pip-audit` wired in CI (`.github/workflows/security-audit.yml`).
- [x] AC5 (Concern 5): `{{BACKGROUND_CONTEXT}}`, `{{CONTEXT}}`, `{{SEARCH_RESULTS}}` in prompts.md wrapped with `<untrusted_source>` delimiters and a standing directive added.
- [x] AC6 (Concern 6): html2svg.py's CONVERT_SCRIPT path-confines image reads to the deck directory before `fs.readFileSync`.
- [x] Nit 7: proof_gate.py documents the self-attestation limitation.
- [x] Nit 8: SKILL.md frontmatter gains a `metadata:` security block.

## Not in scope

- Removing `--no-sandbox` (would break containerized environments; AST06 declaration is the fix)
- Full npm lockfile (requires `npm install` in CI; deferred to backlog)
- ~~svg2pptx.py lxml parser flags (XXE check; separate targeted investigation needed)~~ — resolved in PR #30: `resolve_entities=False, no_network=True, load_dtd=False` added to module-level `_SVG_PARSER`
- PageAgent phase-split credential propagation (ASI03; addressed in subsequent pass 2026-07-04: explicit scope-gate lines added to all 9 orchestrator/stage prompts)

## Tasks

1. html2svg.py — request interception + path confinement (AC1, AC6)
2. html2png.py — request interception (AC1)
3. build_pdf.py — request interception (AC1)
4. html_packager.py — remove allow-same-origin (AC3)
5. prompts.md — add untrusted_source delimiters (AC5)
6. SKILL.md — security metadata + pip pins + isolation declaration (AC2, AC4, Nit 8)
7. proof_gate.py — add self-attestation comment (Nit 7)

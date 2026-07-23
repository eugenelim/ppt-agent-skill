Mode: full (security boundary + structural change + new dependency)

# no-sandbox-container-isolation

**Status:** Shipped

## Objective

Provide a Docker-based render path that replaces Chromium's internal `--no-sandbox` flag
with OS-level container isolation (seccomp profile + minimal capabilities), activated by
`RENDER_IN_CONTAINER=1`. The default path (no env var) is unchanged.

## Acceptance Criteria

- [x] AC-1: `docker/render/Dockerfile` exists; builds a minimal image with Node, Playwright's
  Chromium, and the project's Python render dependencies; does NOT install with --no-sandbox.
- [x] AC-2: `docker/render/chrome.json` contains a valid JSON seccomp profile that permits
  Chromium's required syscalls while blocking dangerous ones (clone3 with CLONE_NEWUSER,
  mount, pivot_root, etc.).
- [x] AC-3: `scripts/mermaid_render/browser.py`: when `RENDER_IN_CONTAINER=1` env var is set,
  `_LAUNCH_ARGS` must NOT contain `"--no-sandbox"`.
- [x] AC-4: `scripts/mermaid_render/render_container.py` provides a `render_html_in_container`
  function that mounts a temp directory and calls the container render subprocess.
- [x] AC-5: `tests/test_container_isolation.py` passes with tests for:
  - AC-3 (no --no-sandbox in container mode)
  - Dockerfile exists and contains `playwright install chromium`
  - seccomp profile is valid JSON with at least a `defaultAction` and `syscalls` key
- [x] AC-6: Full test suite (excl. snapshots) passes with no new failures.

## Boundaries

**In scope:**
- `docker/render/Dockerfile` — minimal Playwright/Python image for Chromium rendering
- `docker/render/chrome.json` — Chromium-compatible seccomp syscall allowlist
- `scripts/mermaid_render/browser.py` — env var gate for `_LAUNCH_ARGS`
- `scripts/mermaid_render/render_container.py` — container dispatch helper
- `tests/test_container_isolation.py` — infrastructure and env var tests

**Out of scope:**
- Docker Compose, Makefile targets, or CI pipeline changes
- Changing the default render path (non-container behavior is unchanged)
- `workspace.toml` update (supervisor manages that separately)

## Testing Strategy

Tests do NOT build or run the Docker image (requires Docker and minutes to build).
Tests verify:
- The env var control (unit test, no Docker needed)
- The infrastructure files exist and are structurally valid

Optional test (marked `@pytest.mark.external_reference`, skipped by default):
- `test_container_renders_simple_html`: builds the image and renders a tiny fixture

## Task List

- [x] T1: Create `docker/render/Dockerfile`
- [x] T2: Create `docker/render/chrome.json` (Chromium seccomp profile)
- [x] T3: Modify `browser.py` for RENDER_IN_CONTAINER env var
- [x] T4: Create `scripts/mermaid_render/render_container.py`
- [x] T5: Create `tests/test_container_isolation.py`

## Security Controls

- `--cap-drop=ALL --cap-add=SYS_ADMIN` — minimal capabilities; SYS_ADMIN needed for
  Chromium's internal process namespace (CLONE_NEWPID/CLONE_NEWNET for renderer isolation)
- `--network=none` — renderer only needs `file://` input; no egress prevents data exfiltration
- seccomp profile (`chrome.json`) — defaultAction SCMP_ACT_ERRNO; explicit allowlist of
  Chromium-needed syscalls; explicit SCMP_ACT_ERRNO for `clone3` (errnoRet=ENOSYS for
  glibc fallback), `mount`, `pivot_root` (container-escape vectors)
- RENDER_IN_CONTAINER env var — opt-in gate; default path unchanged for backward compat

## Deferred

- `--cap-add=SYS_ADMIN` re-evaluation — verify whether seccomp profile alone suffices
  without SYS_ADMIN (requires empirical testing with Chromium namespace sandbox)
- Remove `ptrace` from chrome.json allowlist (needs verification no crash reporter requires it)
- Single-file volume mount: `-v ${html}:/input/${html.name}:ro` to minimize read surface
- Base image digest pinning: pin `FROM ... @sha256:<digest>` and `pip install --require-hashes`
- Non-root container user: add `RUN useradd ...` + `USER render` for defense in depth
- ADR/RFC for new `docker/` top-level directory

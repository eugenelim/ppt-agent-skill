# Session evidence — a field deck-build session

Source: a real Claude Code deck-build session inside Claude Desktop, whose working
directory was a **cloud-synced (OneDrive CloudStorage) File-Provider mount**, model
sonnet-4-6 / max. (Client/deck identifiers redacted.) Full narrative in
`.context/diagram-render-local-preview-findings.md`.

## Preview / local-server failures (items A, D)

- `mcp__Claude_Preview__preview_start` called with `proof-worksheet`, `slide-8`,
  `slides-preview`. First three → `No server named "X"` (it launches a *named* server
  from `.claude/launch.json`, not a file).
- Valid name `slides-preview` → `Failed to start preview server: … getcwd: cannot
  access parent directories: Operation not permitted … pyenv: cannot change working
  directory`. macOS File-Provider (OneDrive) + login-shell/pyenv cwd break. Not a port
  conflict, not a Claude permission prompt.
- Fallback each time: `open <file>.html` (user hand-off; no agent visual read).
- Contrast: every plain python/node subprocess under OneDrive succeeded that session
  (`resolve_output_dir.py`, `planning_validator.py`, `proof_gate.py`, …). Only the
  shell-launched server broke → `html2png.py` (`file://`, explicit cwd) is the immune
  path.

## Render verified textually only (item B)

- 6 parallel `Agent` render batches. Their Bash calls: `subagent_logger.py run`,
  `python3 -c "import re …"` (confirm each `data-card-id` present + file non-empty),
  and `cp` backups. **Zero** `html2png.py` / `visual_qa.py` / screenshot / browser
  calls in the render path. `page-html-playbook.md` Phase 8 completion is textual, so
  this was compliant.
- Outcome: card overflow shipped — final human turn "slide 8 — the bullet points …
  don't fit the card anymore. please fix."

## Diagram routing gap (item E)

- 16 planning files carried `"block_refs": []`. Across planning: `diagram-concept` ×2,
  `diagram-process-flow` ×2, **`diagram-architecture` ×0**.
- Two content slides that visually became diagrams (a process/pipeline and a
  concepts/relationships map) were planned as `list`/`text` cards with
  `diagram_type: None` — they only became diagrams at HTML render time, bypassing the
  recipe library.
- `planning_validator.py` has no check that a diagram-shaped card routes a recipe.

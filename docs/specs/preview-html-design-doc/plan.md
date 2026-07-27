# Plan: preview-html-design-doc

## Tasks

### Task 1 — Create `docs/product/DESIGN.md`

**Depends on:** none
**Verification mode:** Visual/manual QA
**Done when:** file exists; all AC1 sections present; every behavioral claim has
`[current]` or `[planned: <spec-slug>]` annotation; ≥ 3 resolvable citations for
bottom nav; no PII/client data.

**Approach:** Write the file with sections in order:
1. Design Intent (why single-file preview)
2. Architecture Constraints (iframe+sandbox rationale, base64 inlining) — all `[current]`
3. Navigation Bar — document CURRENT state (fixed top toolbar, Prev/Next, counter) plus
   target design (bottom bar, progress bar) marked `[planned: preview-html-nav-bottom]`
4. Controls Layout — target layout annotated as planned
5. Keyboard Shortcuts — current (arrow keys) + planned extensions noted
6. Slide Jump Modal — `[planned: preview-html-nav-bottom]`
7. Speaker Notes — `[planned: preview-html-notes]`
8. Print/PDF — `[planned: preview-html-print]`
9. Maintenance Rule (names html_packager.py as the trigger)

---

### Task 2 — Update `docs/product/README.md`

**Depends on:** Task 1 (DESIGN.md must exist)
**Verification mode:** Goal-based check
**Done when:** `grep "DESIGN.md" docs/product/README.md` returns ≥ 1 hit in the
"What lives here" list.

**Approach:** Add one bullet under "What lives here":
`- [\`DESIGN.md\`](DESIGN.md) — preview HTML design system (layout, interaction, visual conventions); updated in lockstep with \`html_packager.py\`.`

---

### Task 3 — Update `AGENTS.md`

**Depends on:** Task 1 (DESIGN.md must exist to be referenced)
**Verification mode:** Goal-based check
**Done when:**
- `grep -n "DESIGN.md" AGENTS.md` shows the table row is between the `docs/product/`
  row and the `docs/guides/` row in the Source of truth table.
- The bullet appears on the line immediately following the "Never leak PII" bullet.
- Line delta ≤ 10.

**Approach:**
1. Add table row to Source of truth table (after `docs/product/` row):
   `| What is the preview HTML designed to look/behave like? | \`docs/product/DESIGN.md\` |`
2. Add bullet to Non-negotiables after the "Never leak PII" bullet:
   ```
   - **Keep DESIGN.md current.** Any PR that changes a visual or interaction
     aspect of the preview HTML (`scripts/html_packager.py`) must update
     `docs/product/DESIGN.md` in the same commit. See the maintenance rule there.
   ```

---

## Rollout

No deploy, no migration. Docs-only PR targeting `main`.

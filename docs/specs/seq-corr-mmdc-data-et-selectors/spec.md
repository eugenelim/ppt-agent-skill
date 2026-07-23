Mode: light (no risk trigger fired)

# seq-corr-mmdc-data-et-selectors

**Status:** Shipped

## Objective

Probe mmdc 11.15 SVG output to confirm the `data-et` attribute selector names used
in T11 (`_compare_mmdc_semantic`), then lock the confirmed names in a regression test.

## Acceptance Criteria

- AC-1: Confirmed selector inventory documented (see spec body) and matches mmdc 11.15 live output.
- AC-2: `tests/test_mmdc_selectors.py` renders two canonical fixtures via mmdc and asserts
  the confirmed data-et counts match SequenceGeometry counts for each diagram.
- AC-3: Tests use `@pytest.mark.external_reference`; they skip cleanly when mmdc is not on PATH.
- AC-4: `compare_gallery.py` `_compare_mmdc_semantic` extended to also compare note count
  (`data-et="note"`) and fragment count (`data-et="control-structure"`) against SequenceGeometry.

## Confirmed selector inventory (mmdc 11.15)

- `data-et="participant"` → `<g>` wrapping each participant box
- `data-et="message"` → `<line>` for each message arrow
- `data-et="life-line"` → `<line>` for each lifeline
- `data-et="note"` → `<g>` for each Note element (NOT `<polygon>` — spec AC-11.1 was wrong)
- `data-et="control-structure"` → `<g>` for alt/opt/loop/par/break fragments
- Activations: `class="activationN"` on `<rect>` — NO `data-et` attribute (spec AC-11.1 was wrong)

## Task list

- [x] T1: Write `tests/test_mmdc_selectors.py` with selector regression tests
- [x] T2: Extend `_compare_mmdc_semantic` to add note + fragment count comparison
- [x] T3: Update workspace.toml — remove `backlog-compound-elk-ac1-ac3`, mark this spec shipped

Mode: full (structural change — new rendering pass for box grouping; unfamiliar territory)

# seq-corr-box-unsupported-fixture

**Status:** Active

## Objective

Implement sequence diagram `box` directive rendering: render a full-height colored background
rect spanning all participants in the box group, with a label at the top. Currently parsed
but silently ignored — produces no visual output.

## Background

The Mermaid `box` directive groups participants under a colored, labeled region:

```
sequenceDiagram
    box Blue Alice's group
        participant Alice
        participant Bob
    end
    Alice->>Bob: Hello
```

**mmdc 11.15 SVG output for box:**
```html
<rect x="-20" y="-5" fill="Blue" stroke="rgb(0,0,0, 0.5)" width="400" height="246" class="rect"/>
<text x="180" y="13.5" ...>Alice's group</text>
```

The box rect spans from before the leftmost participant to after the rightmost, full canvas
height, with slight negative x/y offsets to create a border. The label appears at the top center.

**Current state of parser:**
The parser (`_strategies.py`) already parses the `box` directive and records participant
group membership. The `box` keyword with color and label is available but not rendered.

## Acceptance Criteria

- [ ] AC-1: A `box` directive renders a background `<rect>` spanning all participants in the
  box group, from `y=0` to `canvas_h`, with:
  - `fill` set to the specified color (or a default gray if no color given)
  - A semi-transparent `opacity` (0.15–0.3) to not obscure participant boxes
  - `stroke` with a contrasting border
- [ ] AC-2: The box label (text after the color) is rendered as a `<text>` or `<span>` element
  at the top of the box (above participant header boxes), horizontally centered over the span.
- [ ] AC-3: Box rects are drawn BELOW participant boxes and lifelines in z-order (painted first
  in the SVG, so other elements appear on top).
- [ ] AC-4: Multiple disjoint boxes on the same diagram render without overlap or z-order conflict.
- [ ] AC-5: `tests/fixtures/sequence-box-unsupported.mmd` fixture is created with:
  - At least 2 boxes (one with color, one without)
  - Participants both inside and outside boxes
  - Messages crossing box boundaries
- [ ] AC-6: `structural_geometry` for the fixture reports `render` (not `syntax`).
- [ ] AC-7: No box rendering in diagrams without `box` directives (no regression).

## Assumptions

- **Parser**: The `box` directive is already parsed; we need to add only the render pass.
- **Colors**: Accept any CSS color string that mmdc accepts (named colors, hex, rgb). If a
  color is not specified in the `box` declaration, use `rgba(200,200,200,0.2)`.
- **Label**: The box label is the text after the optional color on the `box` line.
- **Z-order**: HTML `position:absolute` stack order — box rects use `z-index:0` or appear
  before participant divs in DOM order.
- **No geometry impact**: Box rects do not affect participant column placement or canvas width.

## Testing strategy

- Unit tests in `test_fix_sequence.py`: assert box background rect appears in HTML output;
  assert label text appears; assert no box elements in a non-box diagram.
- New fixture `tests/fixtures/sequence-box-unsupported.mmd` for integration check.
- Run `pytest tests/test_fix_sequence.py -v -k "box"` to verify.

## Deferred

- Box nesting (box inside box) — not supported by mmdc; defer.
- Animation or hover effects on box groups — out of scope.

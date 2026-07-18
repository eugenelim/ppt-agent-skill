# svg2pptx `_path` vs `_line` transform inconsistency (observed, not fixed)

`_line` maps a local coord to output as `coord*scale + o` (correct, matches how
`_walk` accumulates `ox/oy` in output-px). `_path` uses `(coord + o)*scale` under
its `if scale != 1.0` branch, which double-applies scale to the offset. Harmless
today because the renderer's overlay/inline SVG is emitted at scale=1 (the branch
falls to the `else` that does `coord + o`). `_poly` (polygon/polyline) inherits
`_path`, so it shares the same latent behaviour — deliberately, so all three stay
identical.

Left as-is: fixing it risks regressing the working path codepath and is out of
scope for shape-element coverage. Revisit if a scaled `<g>` ever wraps path/poly
geometry.

## Related: `_path` bbox regex is not exponent-aware

`_NUM_RE` (used by `points_to_path_d`) captures scientific notation (`1e3`), but
`_path`'s bbox regex `[+-]?(?:\d+\.?\d*|\.\d+)` does not — it would split `1e3`
into `1` and `3`, mis-pairing coordinates and mis-sizing the shape. Latent only:
mermaid/dom-to-svg emit plain decimals. Inherited from the pre-existing `<path>`
codepath and out of the declared attribute-scope; noted for the day exponent
coords appear.

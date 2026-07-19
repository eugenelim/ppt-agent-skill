# dom-to-svg bundle rebuild recipe

`scripts/vendor/dom-to-svg.bundle.js` is a static pre-built IIFE bundle committed to the repo.
Adopters never rebuild it. If you need to rebuild (e.g. to update dom-to-svg), follow these steps.

## Prerequisites

- Node.js ≥ 18, npm ≥ 9

## Packages

```
dom-to-svg@0.12.2
esbuild@0.28.1
```

These are in `package.json` (or restore it from git history if it has been deleted).

## Build entry (one-time file, deleted after build)

Create `scripts/vendor/build-entry.js`:

```js
import { documentToSVG, elementToSVG, inlineResources } from 'dom-to-svg';
window.__domToSvg = { documentToSVG, elementToSVG, inlineResources };
```

## esbuild command

```bash
npm ci
node_modules/.bin/esbuild scripts/vendor/build-entry.js \
  --bundle \
  --format=iife \
  --outfile=scripts/vendor/dom-to-svg.bundle.js \
  --platform=browser
```

## Cleanup

```bash
rm scripts/vendor/build-entry.js
rm -rf node_modules/
```

## Output

`scripts/vendor/dom-to-svg.bundle.js` — IIFE bundle (~227 KB), exposes `window.__domToSvg` with
`{ documentToSVG, elementToSVG, inlineResources }`.

## Verification

```bash
test -s scripts/vendor/dom-to-svg.bundle.js && echo "non-empty: OK"
grep "__domToSvg" scripts/vendor/dom-to-svg.bundle.js && echo "export: OK"
python3 -c "open('scripts/vendor/dom-to-svg.bundle.js').read(); print('UTF-8: OK')"
```

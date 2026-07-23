#!/usr/bin/env python3
"""check_bundle_hash.py -- verify dom-to-svg.bundle.js SHA-256 checksums.

Run this in CI to detect accidental bundle replacement or tampering.
Pass --update to recompute and display current hashes (for legitimate bundle updates).
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

PINNED: dict[str, str] = {
    "scripts/vendor/dom-to-svg.bundle.js": "8cfeea298514f7a834ce68dbd2ae25b58e646d2ecfe8f91989c918cf95e33950",
    "scripts/mermaid_render/vendor/dom-to-svg.bundle.js": "8cfeea298514f7a834ce68dbd2ae25b58e646d2ecfe8f91989c918cf95e33950",
}


def check() -> bool:
    ok = True
    for rel, expected in PINNED.items():
        path = ROOT / rel
        if not path.exists():
            print(f"ERROR: {rel} not found", file=sys.stderr)
            ok = False
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            print(
                f"ERROR: {rel} SHA-256 mismatch\n  expected: {expected}\n  actual:   {actual}",
                file=sys.stderr,
            )
            ok = False
        else:
            print(f"OK: {rel}")
    return ok


def update() -> None:
    for rel in PINNED:
        path = ROOT / rel
        if not path.exists():
            print(f'    # MISSING: {rel}')
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f'    "{rel}": "{h}",')


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verify dom-to-svg.bundle.js SHA-256 checksums")
    ap.add_argument("--update", action="store_true", help="Print current hashes for PINNED update")
    args = ap.parse_args()
    if args.update:
        update()
    elif not check():
        sys.exit(1)

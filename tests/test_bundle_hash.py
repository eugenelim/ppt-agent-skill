"""Verify that check_bundle_hash detects matching and mismatching hashes."""
import importlib.util
import io
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent / "tools" / "check_bundle_hash.py"

# Canonical relative paths (must match PINNED in check_bundle_hash.py)
_BUNDLE_A = "scripts/vendor/dom-to-svg.bundle.js"
_BUNDLE_B = "scripts/mermaid_render/vendor/dom-to-svg.bundle.js"


def _load_module():
    """Import check_bundle_hash as a module (avoids relying on CWD)."""
    spec = importlib.util.spec_from_file_location("check_bundle_hash", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stage_tampered_root(tmp_path, *, tamper_a=True, tamper_b=True):
    """Build a fake repo root; copy real bundles unless asked to tamper them."""
    real_root = _SCRIPT.parent.parent
    for rel in (_BUNDLE_A, _BUNDLE_B):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = real_root / rel
        if (rel == _BUNDLE_A and tamper_a) or (rel == _BUNDLE_B and tamper_b):
            dest.write_bytes(b"tampered")
        else:
            shutil.copy(src, dest)


# ── subprocess / process-level tests ──────────────────────────────────────────

def test_bundle_hash_passes():
    r = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, f"Expected hash check to pass:\n{r.stderr}"


def test_bundle_hash_update_flag():
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--update"], capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "dom-to-svg.bundle.js" in r.stdout


def test_bundle_hash_mismatch_exits_1_subprocess(tmp_path):
    """Both bundles tampered: process exits 1 and reports both mismatches."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    shutil.copy(_SCRIPT, tools_dir / "check_bundle_hash.py")
    _stage_tampered_root(tmp_path)

    r = subprocess.run(
        [sys.executable, str(tools_dir / "check_bundle_hash.py")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1, f"Expected exit 1 on mismatch, got {r.returncode}"
    # fail-all: both mismatches must appear in stderr
    assert _BUNDLE_A in r.stderr
    assert _BUNDLE_B in r.stderr
    assert r.stderr.count("SHA-256 mismatch") == 2


def test_bundle_hash_one_tampered_exits_1(tmp_path):
    """One bundle tampered, one clean: exit 1; untouched bundle still reports OK."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    shutil.copy(_SCRIPT, tools_dir / "check_bundle_hash.py")
    _stage_tampered_root(tmp_path, tamper_a=True, tamper_b=False)

    r = subprocess.run(
        [sys.executable, str(tools_dir / "check_bundle_hash.py")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "SHA-256 mismatch" in r.stderr
    assert _BUNDLE_A in r.stderr
    # The untouched bundle should have been reported OK (on stdout)
    assert f"OK: {_BUNDLE_B}" in r.stdout


# ── function-level unit tests ──────────────────────────────────────────────────

def test_bundle_hash_mismatch_check_fn(tmp_path, monkeypatch):
    """check() returns False and emits mismatch errors via function call."""
    _stage_tampered_root(tmp_path)
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        result = mod.check()

    assert result is False
    assert "SHA-256 mismatch" in stderr_buf.getvalue()


def test_bundle_hash_missing_file_exits_1(tmp_path, monkeypatch):
    """check() returns False and prints an error when a bundle file is absent."""
    # Point ROOT at an empty directory — no bundle files exist
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        result = mod.check()

    assert result is False
    assert "not found" in stderr_buf.getvalue()

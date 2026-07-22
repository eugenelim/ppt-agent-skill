"""Resource regression tests for Mermaid test infrastructure.

Verifies process-launch counts and lifecycle invariants so that
regressions (extra browser launches, missed cleanup, etc.) fail fast.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import unittest.mock as mock
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
REAL_PYTHON = os.path.realpath(sys.executable)

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# ── browser_lock ──────────────────────────────────────────────────────────────

from mermaid_render.browser_lock import browser_budget  # noqa: E402


def test_lock_acquired_and_released(tmp_path):
    lock_path = str(tmp_path / "test.lock")
    with browser_budget(lock_path=lock_path):
        assert os.path.exists(lock_path)
    # After exit the lock file still exists but is unlocked; a second acquire must succeed
    with browser_budget(lock_path=lock_path):
        pass


def test_lock_released_on_exception(tmp_path):
    lock_path = str(tmp_path / "test.lock")
    try:
        with browser_budget(lock_path=lock_path):
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass
    # Lock must be released — second acquire must not block
    acquired = threading.Event()

    def _try():
        with browser_budget(lock_path=lock_path, timeout_msg_delay=999):
            acquired.set()

    t = threading.Thread(target=_try, daemon=True)
    t.start()
    t.join(timeout=2.0)
    assert acquired.is_set(), "lock not released after exception — deadlock"


def test_lock_noop_when_fcntl_unavailable(tmp_path):
    """browser_budget is a no-op when fcntl is not available."""
    lock_path = str(tmp_path / "test.lock")
    with mock.patch.dict(sys.modules, {"fcntl": None}):
        # Re-import to pick up the patched modules dict
        import importlib
        import mermaid_render.browser_lock as bl_mod
        importlib.reload(bl_mod)
        try:
            with bl_mod.browser_budget(lock_path=lock_path):
                pass  # must not raise
        finally:
            importlib.reload(bl_mod)  # restore


# ── BrowserSession mock-based ─────────────────────────────────────────────────

import mermaid_render.browser as _browser_mod  # noqa: E402


def _make_fake_pw(launch_return=None, launch_side_effect=None):
    fake_browser = mock.MagicMock() if launch_return is None else launch_return
    fake_chromium = mock.MagicMock()
    if launch_side_effect is not None:
        fake_chromium.launch.side_effect = launch_side_effect
    else:
        fake_chromium.launch.return_value = fake_browser
    fake_pw = mock.MagicMock()
    fake_pw.chromium = fake_chromium
    return fake_pw, fake_chromium, fake_browser


def test_browser_session_single_launch():
    """BrowserSession calls chromium.launch exactly once and browser.close once on exit."""
    if not _browser_mod._PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not importable")

    fake_pw, fake_chromium, fake_browser = _make_fake_pw()

    with mock.patch.object(_browser_mod, "sync_playwright") as mock_sp:
        mock_sp.return_value.start.return_value = fake_pw
        with _browser_mod.BrowserSession() as session:
            assert session._browser is fake_browser

    fake_chromium.launch.assert_called_once()
    fake_browser.close.assert_called_once()
    fake_pw.stop.assert_called_once()


def test_browser_session_reuses_browser_across_renders(tmp_path):
    """Two render_to_png calls use new_context twice but chromium.launch once."""
    if not _browser_mod._PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not importable")

    html = tmp_path / "t.html"
    html.write_text("<html><body>hi</body></html>")

    fake_page = mock.MagicMock()
    fake_page.screenshot.return_value = b"\x89PNG\r\n"
    fake_context = mock.MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_browser = mock.MagicMock()
    fake_browser.new_context.return_value = fake_context
    fake_pw, fake_chromium, _ = _make_fake_pw(launch_return=fake_browser)

    with mock.patch.object(_browser_mod, "sync_playwright") as mock_sp:
        mock_sp.return_value.start.return_value = fake_pw
        with _browser_mod.BrowserSession() as session:
            session.render_to_png(html)
            session.render_to_png(html)

    fake_chromium.launch.assert_called_once()
    assert fake_browser.new_context.call_count == 2


def test_browser_session_closes_context_on_render_failure(tmp_path):
    """page.close and context.close called even when goto raises."""
    if not _browser_mod._PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not importable")

    html = tmp_path / "t.html"
    html.write_text("<html><body>hi</body></html>")

    fake_page = mock.MagicMock()
    fake_page.goto.side_effect = RuntimeError("network error")
    fake_context = mock.MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_browser = mock.MagicMock()
    fake_browser.new_context.return_value = fake_context
    fake_pw, _, _ = _make_fake_pw(launch_return=fake_browser)

    with mock.patch.object(_browser_mod, "sync_playwright") as mock_sp:
        mock_sp.return_value.start.return_value = fake_pw
        with _browser_mod.BrowserSession() as session:
            with pytest.raises(RuntimeError):
                session.render_to_png(html)

    fake_page.close.assert_called_once()
    fake_context.close.assert_called_once()


def test_no_playwright_install_on_missing_chromium():
    """Fail-fast: 'Executable doesn't exist' raises RuntimeError immediately, no subprocess.run."""
    if not _browser_mod._PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not importable")

    fake_pw, fake_chromium, _ = _make_fake_pw(
        launch_side_effect=Exception("Executable doesn't exist")
    )

    with mock.patch.object(_browser_mod, "sync_playwright") as mock_sp:
        mock_sp.return_value.start.return_value = fake_pw
        with pytest.raises(RuntimeError, match="playwright install chromium"):
            _browser_mod.BrowserSession().__enter__()

    # Structural guarantee: browser.py has no subprocess import, so no install can happen.
    fake_chromium.launch.assert_called_once()


# ── mmdc version/integrity caching ───────────────────────────────────────────

def test_mmdc_version_cached(monkeypatch):
    """_mmdc_version() calls subprocess.run only once per process; subsequent calls return cache."""
    sys.path.insert(0, str(REPO_ROOT / "tests" / "fidelity"))
    import adapters.reference as ref_mod

    monkeypatch.setattr(ref_mod, "_MMDC_VERSION_CACHE", ref_mod._UNSET)
    monkeypatch.setattr(ref_mod, "_MMDC_INTEGRITY_CACHE", ref_mod._UNSET)

    call_count = 0

    def fake_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = mock.MagicMock()
        result.stdout = "11.15.0"
        result.stderr = ""
        return result

    monkeypatch.setattr(ref_mod.subprocess, "run", fake_run)

    v1 = ref_mod._mmdc_version()
    v2 = ref_mod._mmdc_version()
    assert v1 == v2 == "11.15.0"
    assert call_count == 1, f"subprocess.run called {call_count} times; expected 1"


# ── Real browser integration (skips when unavailable) ─────────────────────────

@pytest.mark.browser
def test_browser_session_real_lifecycle(tmp_path):
    """Real Playwright integration: one browser, one render, clean shutdown."""
    try:
        from playwright.sync_api import sync_playwright as _sp  # noqa: F401
    except ImportError:
        pytest.skip("playwright not installed")

    html = tmp_path / "d.html"
    html.write_text(
        "<!doctype html><html><body style='background:#fff'>"
        "<p>hello</p></body></html>",
        encoding="utf-8",
    )

    with _browser_mod.BrowserSession() as session:
        png = session.render_to_png(html, scale=1.0, fullpage=True)

    assert png[:4] == b"\x89PNG", "expected PNG header"
    assert len(png) > 100


# ── SIGINT lock release ───────────────────────────────────────────────────────

@pytest.mark.isolation
@pytest.mark.skipif(
    not hasattr(signal, "SIGINT"),
    reason="SIGINT not available on this platform",
)
def test_flock_releases_after_sigint(tmp_path):
    """Lock is released when the holding process receives SIGINT."""
    lock_path = str(tmp_path / "browser.lock")

    # Child process acquires the lock then sleeps
    child_script = (
        "import sys, time\n"
        "sys.path.insert(0, 'scripts')\n"
        "from mermaid_render.browser_lock import browser_budget\n"
        f"with browser_budget(lock_path={lock_path!r}):\n"
        "    sys.stdout.write('LOCKED\\n'); sys.stdout.flush()\n"
        "    time.sleep(60)\n"
    )
    child = subprocess.Popen(
        [REAL_PYTHON, "-c", child_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=str(REPO_ROOT),
    )
    # Wait for child to confirm lock acquisition
    line = child.stdout.readline()
    assert b"LOCKED" in line, f"child did not acquire lock: {line}"

    # Send SIGINT to the child
    child.send_signal(signal.SIGINT)
    child.wait(timeout=5)

    # Main process must now acquire the lock within 2s
    acquired = threading.Event()

    def _try():
        with browser_budget(lock_path=lock_path, timeout_msg_delay=999):
            acquired.set()

    t = threading.Thread(target=_try, daemon=True)
    t.start()
    t.join(timeout=2.0)
    assert acquired.is_set(), "lock not released after child SIGINT"

"""Cross-process advisory lock for browser-heavy test processes.

browser_budget() is an OS-level exclusive flock that limits concurrent
Playwright/Chromium launches to one process at a time. This prevents a
machine from becoming unresponsive when multiple pytest invocations start
browser-heavy suites simultaneously.

Usage (in test fixtures only — not in production rendering)::

    from mermaid_render.browser_lock import browser_budget

    with browser_budget():
        with BrowserSession() as session:
            ...

- macOS / Linux: fcntl.flock (LOCK_EX) on a lockfile in the system temp dir.
- Windows / unsupported: no-op context manager (not a CI target for browser tests).
- Lock released automatically on normal exit, exception, or SIGINT/SIGTERM
  (Python's finally blocks run during KeyboardInterrupt).
- Default lockfile: $TMPDIR/mermaid-browser.lock  (overridable for tests).
- Prints a one-line waiting message via a timer thread if lock acquisition
  takes longer than timeout_msg_delay seconds.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import threading

_DEFAULT_LOCK_PATH = os.path.join(tempfile.gettempdir(), "mermaid-browser.lock")


@contextlib.contextmanager
def browser_budget(lock_path: "str | None" = None, timeout_msg_delay: float = 0.5):
    """Context manager serializing concurrent browser-heavy processes via flock.

    No-op on platforms without fcntl (e.g. Windows).
    Prints a waiting message if lock acquisition takes longer than
    timeout_msg_delay seconds.
    """
    try:
        import fcntl
    except ImportError:
        yield
        return

    path = lock_path or _DEFAULT_LOCK_PATH

    warned = False

    def _warn():
        nonlocal warned
        warned = True
        print(
            f"[mermaid-browser] waiting for browser resource lock ({path}) …",
            flush=True,
        )

    with open(path, "w") as fd:
        timer = threading.Timer(timeout_msg_delay, _warn)
        timer.start()
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        finally:
            timer.cancel()
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)

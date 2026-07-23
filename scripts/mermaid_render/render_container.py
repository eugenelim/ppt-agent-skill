"""render_container.py — helper to invoke render inside a Docker container.

Used when RENDER_IN_CONTAINER=1. Not imported by default; callers opt in
by importing this module and calling render_html_in_container().

Requires the Docker image to be built first:
    docker build -t ppt-agent-render:latest docker/render/
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_IMAGE = "ppt-agent-render:latest"
_SECCOMP = Path(__file__).resolve().parent.parent.parent / "docker" / "render" / "chrome.json"


def render_html_in_container(
    html_path: "str | Path",
    *,
    output_dir: "str | Path",
) -> None:
    """Render html_path to a PNG file in output_dir inside the Docker container.

    The output PNG filename is derived from the HTML file's stem:
    ``output_dir / (html_stem + ".png")``.

    Mounts the HTML file's parent directory read-only at /input and output_dir
    read-write at /output.  The seccomp profile at docker/render/chrome.json is
    required and enforced; the function raises FileNotFoundError rather than
    launching a container without it (fail-closed).

    Raises FileNotFoundError if the seccomp profile does not exist on disk.
    Raises subprocess.CalledProcessError on non-zero container exit.
    """
    html = Path(html_path).resolve()
    out_dir = Path(output_dir).resolve()

    if not _SECCOMP.exists():
        raise FileNotFoundError(
            f"Seccomp profile not found: {_SECCOMP}. "
            "The container must not run without an explicit seccomp profile "
            "because --cap-add=SYS_ADMIN is granted and the custom profile is "
            "the only boundary blocking dangerous SYS_ADMIN syscalls (mount, pivot_root)."
        )

    cmd = [
        "docker", "run", "--rm",
        "--cap-drop=ALL",
        "--cap-add=SYS_ADMIN",     # required for Chromium's internal process namespace
        "--network=none",           # renderer only needs file:// input; no egress needed
        f"--security-opt=seccomp={_SECCOMP}",
        "-v", f"{html.parent}:/input:ro",
        "-v", f"{out_dir}:/output",
        "-e", "RENDER_IN_CONTAINER=1",
        _IMAGE,
        f"/input/{html.name}",     # positional: html2png.py <html_file>
        "-o", "/output",           # output directory; PNG named <html_stem>.png
    ]
    subprocess.run(cmd, check=True)

# docker/render/Dockerfile
#
# Minimal Playwright/Python image for headless Chromium rendering.
# Run with --cap-drop=ALL --cap-add=SYS_ADMIN and --security-opt seccomp=chrome.json.
# Set RENDER_IN_CONTAINER=1 (baked in below) so browser.py omits the host sandbox flag.
#
# Build:
#   docker build -t ppt-agent-render:latest docker/render/
#
# Run (example):
#   docker run --rm \
#     --cap-drop=ALL --cap-add=SYS_ADMIN \
#     --security-opt=seccomp=docker/render/chrome.json \
#     -v "$PWD/slides":/input:ro \
#     -v "$PWD/out":/output \
#     --network=none \
#     -e RENDER_IN_CONTAINER=1 \
#     ppt-agent-render:latest \
#     /input/slide.html -o /output

FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install project Python dependencies.
# playwright in requirements.txt will upgrade the base-image version; the
# subsequent `playwright install chromium` step fetches the matching binary.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install the Chromium browser binary and its system dependencies matching
# the installed playwright version (--with-deps handles version skew from the base image).
RUN playwright install --with-deps chromium

# Copy render scripts only (no full source tree, keeps image small).
COPY scripts/ ./scripts/

# Signal to browser.py that this process runs inside the container so it
# omits the host sandbox flag from Chromium launch args (OS-level seccomp replaces it).
ENV RENDER_IN_CONTAINER=1

ENTRYPOINT ["python3", "scripts/html2png.py"]

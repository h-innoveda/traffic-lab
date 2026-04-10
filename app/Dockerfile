# ─────────────────────────────────────────────────────────────────
# Dockerfile — builds the Python Flask app image
#
# A Dockerfile is a recipe: "start with this base, add these files,
# run these commands, then when the container starts, run THIS."
#
# Each line is a LAYER. Docker caches layers — if requirements.txt
# hasn't changed, it won't re-run pip install (saves minutes).
# ─────────────────────────────────────────────────────────────────

# BASE IMAGE: slim = smaller image (no build tools, no docs)
# python:3.12-slim is ~50MB vs python:3.12 which is ~350MB
FROM python:3.12-slim

# Set working directory inside the container.
# All subsequent commands run from here.
WORKDIR /app

# ── LAYER 1: Install dependencies ──────────────────────────────
# Copy requirements FIRST (before app code).
# WHY? If you copy everything first, any code change invalidates
# the pip install cache. This way, pip only re-runs when
# requirements.txt changes — not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
#   --no-cache-dir: don't store pip's download cache in the image
#   (saves ~50MB of image size)

# ── LAYER 2: Copy application code ─────────────────────────────
COPY main.py .

# ── Create log directory ────────────────────────────────────────
# Promtail will read logs from /app/logs/app.log
# We create it here so the app doesn't fail if the volume isn't mounted
RUN mkdir -p /app/logs

# ── EXPOSE: documentation only ─────────────────────────────────
# This doesn't actually open a port — it's metadata telling
# Docker Compose / Kubernetes "this container listens on 5000"
EXPOSE 5000

# ── CMD: what runs when the container starts ────────────────────
# gunicorn = production WSGI server
#   -w 2          → 2 worker processes (handles concurrent requests)
#   -b 0.0.0.0:5000 → listen on all interfaces, port 5000
#   main:app      → file "main.py", Flask object named "app"
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "main:app"]

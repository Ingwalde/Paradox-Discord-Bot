# Build stage — pip and the wheels it downloads stay here and never reach the
# runtime image. Keeps the shipped image smaller and cuts the CVE surface the
# Trivy scan in .github/workflows/ci.yml has to look at.
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

# Apply Debian security updates on top of the base image. python:3.13-slim is
# rebuilt on its own schedule, so between rebuilds it ships OS packages with
# published fixes. The Trivy gate runs with ignore-unfixed, meaning only CVEs
# the project can actually act on fail the build; upgrading here is that action.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Only the installed packages come across — no pip cache, no build wheels.
COPY --from=builder /install /usr/local

COPY . .

# data/ holds the runtime SQLite files (uploads, feedback, stats) and is a
# mounted volume in docker-compose.yml. The game databases in databases/ are
# read-only content baked into the image and rebuilt by scripts/import_wiki.py.
# Fixed uid/gid 1000, not a system user: data/ and logs/ are bind-mounted from
# the host, and a bind mount keeps the host's ownership. A system account gets
# an arbitrary uid in the 100s, which then cannot write to a directory owned by
# the host's first non-root user — uid 1000 on Ubuntu, which is what Oracle
# Cloud and Hetzner images ship. Matching it means the mount just works.
RUN mkdir -p data logs \
    && addgroup --gid 1000 botuser \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" botuser \
    && chown -R botuser:botuser /app

USER botuser

# Cosmetic only — publishing is docker-compose.yml's job. Documents the
# keep-alive/health port the app listens on.
EXPOSE 8080

# `exec` replaces the shell with the Python process (same PID) so SIGTERM from
# `docker stop` / `compose down` reaches it directly instead of being swallowed
# by dash. discord.py closes the gateway cleanly on that signal.
CMD ["sh", "-c", "exec python main.py"]

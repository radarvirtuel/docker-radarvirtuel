# ─────────────────────────────────────────────────────────────
# Dockerfile — docker-radarvirtuel v2
# Version     : v1.2 — 2026-06-08
# Description : RadarVirtuel Docker feeder
#               Beast TCP input → radarvirtuel.com:30004
#               Base: python:3.11-slim + readsb from sdr-enthusiasts repo
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL maintainer="laurent.duval@adsbnetwork.com"

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        netcat-openbsd && \
    curl -fsSL https://pkg.sdr-enthusiasts.com/repo/apt/sdr-e.gpg \
        | gpg --dearmor -o /usr/share/keyrings/sdr-e.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/sdr-e.gpg] https://pkg.sdr-enthusiasts.com/repo/apt bookworm main" \
        > /etc/apt/sources.list.d/sdr-e.list && \
    apt-get update -q && \
    apt-get install -y --no-install-recommends readsb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /data

COPY docker-entrypoint.py /entrypoint.py

VOLUME ["/data"]

ENV SOURCE_HOST=localhost:30005
ENV RV_ALT_M=0

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD nc -z radarvirtuel.com 30004 || exit 1

CMD ["python3", "-u", "/entrypoint.py"]

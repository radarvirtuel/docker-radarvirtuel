# ─────────────────────────────────────────────────────────────
# Dockerfile — docker-radarvirtuel v2
# Version     : v1.3 — 2026-06-08
# Description : RadarVirtuel Docker feeder
#               Beast TCP pipe via socat
#               SOURCE_HOST:30005 → radarvirtuel.com:30004
#               Base: python:3.11-slim-bookworm (no s6-overlay)
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL maintainer="laurent.duval@adsbnetwork.com"
LABEL org.opencontainers.image.title="docker-radarvirtuel v2"
LABEL org.opencontainers.image.description="RadarVirtuel ADS-B feeder — Beast TCP pipe"
LABEL org.opencontainers.image.url="https://radarvirtuel.com"
LABEL org.opencontainers.image.version="2.0"

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends \
        socat \
        netcat-openbsd && \
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

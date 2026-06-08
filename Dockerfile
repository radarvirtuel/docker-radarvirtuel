# ─────────────────────────────────────────────────────────────
# Dockerfile — docker-radarvirtuel v2.0
# Version     : v2.0 — 2026-06-08
# Description : RadarVirtuel Docker feeder v2.0
#               feeder_radarvirtuel.py — POST /api/feed avec tagging station
#               Base: python:3.11-slim-bookworm
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL maintainer="laurent.duval@adsbnetwork.com"
LABEL org.opencontainers.image.title="docker-radarvirtuel v2"
LABEL org.opencontainers.image.description="RadarVirtuel ADS-B feeder v2.0"
LABEL org.opencontainers.image.url="https://radarvirtuel.com"
LABEL org.opencontainers.image.version="2.0"

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends \
        python3-requests \
        netcat-openbsd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /data /opt/feeder_rv

COPY docker-entrypoint.py /entrypoint.py
COPY feeder_radarvirtuel.py /opt/feeder_rv/feeder_radarvirtuel.py

VOLUME ["/data"]

ENV RV_ALT_M=0
ENV RV_INTERVAL=5
ENV RV_AIRCRAFT_URL=http://localhost/tar1090/data/aircraft.json

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD grep -q "OK" /var/log/feeder_rv.log 2>/dev/null || exit 1

CMD ["python3", "-u", "/entrypoint.py"]

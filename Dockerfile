# ─────────────────────────────────────────────────────────────
# Dockerfile — docker-radarvirtuel v2
# Version     : v1.0 — 2026-06-08
# Description : RadarVirtuel Docker feeder
#               Beast TCP input → radarvirtuel.com:30004 Beast TCP output
#               Auto-registration via /api/station/register
#               Multi-arch: linux/amd64, linux/arm64, linux/arm/v7
# ─────────────────────────────────────────────────────────────
FROM ghcr.io/sdr-enthusiasts/docker-baseimage:base

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends \
        readsb \
        python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /data

COPY docker-entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py

# Persistent storage for station UID
VOLUME ["/data"]

# Environment defaults
ENV RV_SERVER=radarvirtuel.com
ENV SOURCE_HOST=ultrafeeder:30005
ENV RV_ALT_M=0

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD nc -z radarvirtuel.com 30004 || exit 1

CMD ["python3", "-u", "/entrypoint.py"]

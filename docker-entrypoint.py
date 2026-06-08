#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# File        : docker-entrypoint.py
# Version     : v1.0 — 2026-06-08
# Deploy      : /entrypoint.py (inside Docker image)
# Description : RadarVirtuel Docker feeder entrypoint
#               1. Get or generate station UID (persisted in /data)
#               2. Detect lat/lon from environment or existing configs
#               3. Find nearest airport via radarvirtuel.com API
#               4. Register station via /api/station/register
#               5. Launch readsb --net-connector → radarvirtuel.com:30004
# ─────────────────────────────────────────────────────────────

import os
import sys
import json
import uuid
import urllib.request
import urllib.error
import subprocess
import time

RV_REGISTER   = 'https://radarvirtuel.com/api/station/register'
RV_AIRPORT    = 'https://radarvirtuel.com/api/nearest_airport'
UID_FILE      = '/data/station_uid.txt'
RV_HOST       = 'radarvirtuel.com'
RV_PORT       = '30004'

def log(msg):
    print(f"[RV] {msg}", flush=True)

# ── Station UID ───────────────────────────────────────────────
def get_or_create_uid():
    env_uid = os.environ.get('RV_STATION_UID', '').strip()
    if env_uid and len(env_uid) >= 8:
        log(f"UID from environment: {env_uid}")
        return env_uid
    os.makedirs('/data', exist_ok=True)
    if os.path.exists(UID_FILE):
        uid = open(UID_FILE).read().strip()
        if uid and len(uid) >= 8:
            log(f"UID loaded from {UID_FILE}: {uid}")
            return uid
    uid = uuid.uuid4().hex
    open(UID_FILE, 'w').write(uid)
    log(f"UID generated: {uid} → saved to {UID_FILE}")
    return uid

# ── Coordinates ───────────────────────────────────────────────
def get_coords():
    lat = os.environ.get('RV_LAT', '').strip()
    lon = os.environ.get('RV_LON', '').strip()
    alt = os.environ.get('RV_ALT_M', '0').strip()
    if not lat or not lon:
        log("ERROR: RV_LAT and RV_LON must be set in environment")
        sys.exit(1)
    try:
        return float(lat), float(lon), float(alt)
    except ValueError:
        log(f"ERROR: Invalid coordinates: lat={lat} lon={lon}")
        sys.exit(1)

# ── Nearest airport ───────────────────────────────────────────
def get_nearest_airport(lat, lon):
    """Query radarvirtuel.com to find nearest airport — same logic as install_feeder_universal.sh"""
    try:
        url = f"https://radarvirtuel.com/api/nearest_airport?lat={lat}&lon={lon}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        icao = data.get('icao_code', '')
        name = data.get('name', '')
        dist = data.get('distance_km', 0)
        if icao:
            log(f"Nearest airport: {icao} — {name} ({dist:.1f} km)")
            return icao, data
    except Exception as e:
        log(f"Warning: cannot reach nearest_airport API: {e}")
    return None, {}

# ── Station label ─────────────────────────────────────────────
def get_station_label(nearest_icao):
    """Use provided label or derive from nearest airport — add suffix if taken."""
    label = os.environ.get('RV_STATION_LABEL', '').strip().upper()
    if label:
        return label
    if not nearest_icao:
        log("ERROR: RV_STATION_LABEL must be set (no nearest airport found)")
        sys.exit(1)
    # Try ICAO1, ICAO2, ICAO3...
    base = nearest_icao[:4]
    for suffix in range(1, 10):
        candidate = f"{base}{suffix}"
        try:
            url = f"https://radarvirtuel.com/api/station/check_label?label={candidate}"
            with urllib.request.urlopen(url, timeout=8) as r:
                resp = json.loads(r.read().decode())
            if resp.get('available'):
                log(f"Label selected: {candidate}")
                return candidate
        except Exception:
            # API not available — use ICAO1 as default
            log(f"Label check unavailable — using {base}1")
            return f"{base}1"
    return f"{base}1"

# ── Register station ──────────────────────────────────────────
def register_station(uid, label, lat, lon, alt_m):
    payload = json.dumps({
        'station_uid':    uid,
        'station_label':  label,
        'lat':            lat,
        'lon':            lon,
        'alt_m':          alt_m,
        'contrib_name':   os.environ.get('RV_CONTRIB_NAME', ''),
        'contrib_email':  os.environ.get('RV_CONTRIB_EMAIL', ''),
        'description':    f"Docker feeder — {label}",
    }).encode('utf-8')
    req = urllib.request.Request(
        RV_REGISTER,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Station-UID': uid,
            'User-Agent': 'docker-radarvirtuel/2.0'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode())
        status = resp.get('status', '?').upper()
        actual = resp.get('station_label', label)
        log(f"Registration: {status} — station {actual} uid={uid}")
        return resp.get('ok', False), actual
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        log(f"Registration HTTP {e.code}: {body[:200]}")
        # Continue anyway — station may already exist
        return True, label
    except Exception as e:
        log(f"Registration warning: {e} — continuing")
        return True, label

# ── Launch readsb net-connector ───────────────────────────────
def launch_connector(source_host, source_port, label, lat, lon, alt_m):
    """Launch readsb as a pure Beast forwarder:
       Beast input from SOURCE_HOST:source_port
       Beast output to radarvirtuel.com:30004
    """
    cmd = [
        'readsb',
        '--net',
        f'--net-connector={source_host},{source_port},beast_in',
        f'--net-connector={RV_HOST},{RV_PORT},beast_out',
        f'--lat={lat}',
        f'--lon={lon}',
        '--no-fix',
        '--quiet',
        '--net-heartbeat=60',
        '--net-ro-size=0',
        '--net-ro-interval=0',
    ]
    log(f"Launching readsb connector:")
    log(f"  Source : {source_host}:{source_port} (Beast in)")
    log(f"  Target : {RV_HOST}:{RV_PORT} (Beast out)")
    log(f"  Station: {label} lat={lat} lon={lon}")
    log("─" * 50)
    os.execvp('readsb', cmd)   # replace process — readsb takes over

# ── Main ──────────────────────────────────────────────────────
def main():
    log("=" * 50)
    log("RadarVirtuel Docker Feeder v2.0 — 2026-06-08")
    log("=" * 50)

    # 1 — UID
    uid = get_or_create_uid()

    # 2 — Coordinates
    lat, lon, alt_m = get_coords()
    log(f"Position: lat={lat} lon={lon} alt={alt_m}m")

    # 3 — Nearest airport
    nearest_icao, airport_data = get_nearest_airport(lat, lon)

    # 4 — Station label
    label = get_station_label(nearest_icao)

    # 5 — Register
    ok, label = register_station(uid, label, lat, lon, alt_m)

    # 6 — Source Beast host
    source = os.environ.get('SOURCE_HOST', f"{os.environ.get('HOSTNAME', 'localhost')}:30005")
    parts  = source.rsplit(':', 1)
    source_host = parts[0]
    source_port = parts[1] if len(parts) == 2 else '30005'

    # 7 — Launch
    launch_connector(source_host, source_port, label, lat, lon, alt_m)

if __name__ == '__main__':
    main()

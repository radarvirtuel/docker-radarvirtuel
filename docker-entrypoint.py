#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# File        : docker-entrypoint.py
# Version     : v1.4 — 2026-06-08
# Deploy      : /entrypoint.py (inside Docker image)
# Description : RadarVirtuel Docker feeder entrypoint
#               1. Station UID — CPU serial host > volume > UUID généré
#               2. Lat/lon — env vars > /etc/default/mlat-client monté
#               3. Nearest airport via radarvirtuel.com API
#               4. Register station via /api/station/register
#               5. Launch socat Beast pipe → radarvirtuel.com:30004
# v1.4 : fix Cloudflare 403 — User-Agent navigateur sur tous les appels API
# ─────────────────────────────────────────────────────────────

import os
import sys
import json
import uuid
import urllib.request
import urllib.error

RV_REGISTER = 'https://radarvirtuel.com/api/station/register'
UID_FILE    = '/data/station_uid.txt'
RV_HOST     = 'radarvirtuel.com'
RV_PORT     = '30004'
UA          = 'Mozilla/5.0 (compatible; RadarVirtuel-feeder/1.4)'

def log(msg):
    print(f"[RV] {msg}", flush=True)

def api_get(url):
    """HTTP GET avec User-Agent navigateur pour passer Cloudflare."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def api_post(url, payload_dict, uid):
    """HTTP POST JSON avec User-Agent navigateur."""
    payload = json.dumps(payload_dict).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type':  'application/json',
            'X-Station-UID': uid,
            'User-Agent':    UA,
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

# ── Station UID ───────────────────────────────────────────────
# Priority 1 : RV_STATION_UID env var
# Priority 2 : CPU serial from host /proc/cpuinfo (mounted as /host/cpuinfo)
# Priority 3 : persisted UUID in Docker volume /data/station_uid.txt
# Priority 4 : generate new UUID and persist it
def get_or_create_uid():
    env_uid = os.environ.get('RV_STATION_UID', '').strip()
    if env_uid and len(env_uid) >= 8:
        log(f"UID from environment: {env_uid}")
        return env_uid
    try:
        with open('/host/cpuinfo') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip().lstrip('0')
                    if serial and len(serial) >= 8:
                        log(f"UID from CPU serial: {serial}")
                        return serial
    except Exception:
        pass
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
# Priority 1 : RV_LAT / RV_LON env vars
# Priority 2 : /etc/default/mlat-client monté dans le container
def get_coords():
    lat = os.environ.get('RV_LAT', '').strip()
    lon = os.environ.get('RV_LON', '').strip()
    alt = os.environ.get('RV_ALT_M', '0').strip()
    if not lat or not lon:
        try:
            with open('/etc/default/mlat-client') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('LAT='):
                        lat = line.split('=', 1)[1].strip().strip('"')
                    elif line.startswith('LON='):
                        lon = line.split('=', 1)[1].strip().strip('"')
                    elif line.startswith('ALT=') and not alt:
                        alt = line.split('=', 1)[1].strip().strip('"')
            if lat and lon:
                log(f"Coordinates from /etc/default/mlat-client")
        except Exception:
            pass
    if not lat or not lon:
        log("ERROR: RV_LAT and RV_LON must be set (env vars or mount /etc/default/mlat-client)")
        sys.exit(1)
    try:
        return float(lat), float(lon), float(alt or 0)
    except ValueError:
        log(f"ERROR: Invalid coordinates: lat={lat} lon={lon}")
        sys.exit(1)

# ── Nearest airport ───────────────────────────────────────────
def get_nearest_airport(lat, lon):
    """API response: {"airports": [{icao_code, name, distance_km, suggested_label}]}"""
    try:
        url  = f"https://radarvirtuel.com/api/nearest_airport?lat={lat}&lon={lon}"
        data = api_get(url)
        airports = data.get('airports', [])
        if airports:
            first     = airports[0]
            icao      = first.get('icao_code', '')
            name      = first.get('name', '')
            dist      = first.get('distance_km', 0)
            suggested = first.get('suggested_label', f"{icao}1")
            log(f"Nearest airport: {icao} — {name} ({dist:.1f} km) → suggested: {suggested}")
            return suggested, first
    except Exception as e:
        log(f"Warning: nearest_airport API: {e}")
    return None, {}

# ── Station label ─────────────────────────────────────────────
def get_station_label(suggested_label):
    label = os.environ.get('RV_STATION_LABEL', '').strip().upper()
    if label:
        log(f"Label from environment: {label}")
        return label
    if not suggested_label:
        log("ERROR: RV_STATION_LABEL must be set (no nearest airport found)")
        sys.exit(1)
    log(f"Label auto-selected: {suggested_label}")
    return suggested_label

# ── Register station ──────────────────────────────────────────
def register_station(uid, label, lat, lon, alt_m):
    try:
        resp = api_post(RV_REGISTER, {
            'station_uid':   uid,
            'station_label': label,
            'lat':           lat,
            'lon':           lon,
            'alt_m':         alt_m,
            'contrib_name':  os.environ.get('RV_CONTRIB_NAME', ''),
            'contrib_email': os.environ.get('RV_CONTRIB_EMAIL', ''),
            'description':   f"Docker feeder — {label}",
        }, uid)
        status = resp.get('status', '?').upper()
        actual = resp.get('station_label', label)
        log(f"Registration: {status} — station {actual} uid={uid}")
        return resp.get('ok', False), actual
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        log(f"Registration HTTP {e.code}: {body[:200]}")
        return True, label
    except Exception as e:
        log(f"Registration warning: {e} — continuing")
        return True, label

# ── Launch socat Beast pipe ───────────────────────────────────
def launch_connector(source_host, source_port, label, lat, lon):
    """socat TCP pipe: SOURCE_HOST:30005 → radarvirtuel.com:30004"""
    cmd = [
        'socat',
        f'TCP:{source_host}:{source_port},retry=60,interval=5',
        f'TCP:{RV_HOST}:{RV_PORT},retry=60,interval=5',
    ]
    log(f"Launching socat Beast pipe:")
    log(f"  Source : {source_host}:{source_port}")
    log(f"  Target : {RV_HOST}:{RV_PORT}")
    log(f"  Station: {label} lat={lat} lon={lon}")
    log("─" * 50)
    os.execvp('socat', cmd)

# ── Main ──────────────────────────────────────────────────────
def main():
    log("=" * 50)
    log("RadarVirtuel Docker Feeder v1.4 — 2026-06-08")
    log("=" * 50)

    uid             = get_or_create_uid()
    lat, lon, alt_m = get_coords()
    log(f"Position: lat={lat} lon={lon} alt={alt_m}m")

    suggested, _    = get_nearest_airport(lat, lon)
    label           = get_station_label(suggested)
    _, label        = register_station(uid, label, lat, lon, alt_m)

    source      = os.environ.get('SOURCE_HOST', 'localhost:30005')
    parts       = source.rsplit(':', 1)
    source_host = parts[0]
    source_port = parts[1] if len(parts) == 2 else '30005'

    launch_connector(source_host, source_port, label, lat, lon)

if __name__ == '__main__':
    main()

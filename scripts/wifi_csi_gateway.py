#!/usr/bin/env python3
"""Gateway WiFi-CSI agregado: fuente propia -> API multisensor.

La fuente debe devolver JSON con ``position`` o ``measurements`` y nunca debe
incluir identificadores WiFi. El proceso no captura CSI bruto.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from datetime import datetime, timezone

LOG = logging.getLogger("wifi-csi-gateway")
INTERVAL = max(1.0, float(os.getenv("WIFI_CSI_INTERVAL_SECONDS", "3")))
TIMEOUT = max(0.5, float(os.getenv("WIFI_CSI_TIMEOUT_SECONDS", "2")))
SOURCE_URL = os.getenv("WIFI_CSI_SOURCE_URL", "")
TARGET_URL = os.getenv("WIFI_CSI_TARGET_URL", "http://multisensor-api:8000/api/multisensor/wifi-csi")
SENSOR_ID = os.getenv("WIFI_CSI_SENSOR_ID", "wifi-csi-01")
STATUS_FILE = Path(os.getenv("WIFI_CSI_STATUS_FILE", "/data/wifi-csi-gateway.json"))


def _request_json(url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers={"Accept": "application/json", "Content-Type": "application/json"}, method="POST" if body else "GET")
    with urlopen(request, timeout=TIMEOUT) as response:
        parsed = json.loads(response.read().decode())
    if not isinstance(parsed, dict):
        raise ValueError("la fuente WiFi-CSI debe devolver un objeto JSON")
    return parsed


def read_source() -> dict:
    if not SOURCE_URL:
        raise RuntimeError("WIFI_CSI_SOURCE_URL no está configurado")
    source = _request_json(SOURCE_URL)
    allowed = {"position", "measurements", "anchors", "confidence"}
    unknown = set(source) - allowed
    if unknown:
        raise ValueError(f"campos no permitidos en fuente WiFi-CSI: {', '.join(sorted(unknown))}")
    if "position" not in source and "measurements" not in source:
        raise ValueError("la fuente debe devolver position o measurements")
    return source


def publish(source: dict) -> None:
    payload = {"sensor_id": SENSOR_ID, "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), **source}
    _request_json(TARGET_URL, payload)


def write_status(status: str, error: str | None = None, last_hash: str | None = None) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps({"status": status, "updated_at": datetime.now(timezone.utc).isoformat(), "last_error": error, "last_payload_hash": last_hash}, sort_keys=True), encoding="utf-8")


def run_once(previous_hash: str | None) -> str | None:
    source = read_source()
    digest = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    if digest == previous_hash:
        write_status("healthy", last_hash=digest)
        return digest
    publish(source)
    write_status("healthy", last_hash=digest)
    return digest


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    previous_hash: str | None = None
    while True:
        started = time.monotonic()
        try:
            previous_hash = run_once(previous_hash)
            LOG.info("ciclo WiFi-CSI completado; siguiente ciclo en %.1fs", INTERVAL)
        except (OSError, URLError, ValueError, RuntimeError) as exc:
            write_status("degraded", error=str(exc), last_hash=previous_hash)
            LOG.warning("ciclo WiFi-CSI no publicado: %s", exc)
        time.sleep(max(0.0, INTERVAL - (time.monotonic() - started)))


if __name__ == "__main__":
    main()

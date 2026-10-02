from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("wifi_csi_gateway", Path(__file__).with_name("wifi_csi_gateway.py"))
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_run_once_deduplicates_same_source(monkeypatch, tmp_path: Path) -> None:
    payload = {"position": {"x": 1.0, "y": 2.0}, "confidence": 0.8}
    sent: list[dict] = []
    monkeypatch.setattr(module, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(module, "read_source", lambda: payload)
    monkeypatch.setattr(module, "publish", sent.append)
    digest = module.run_once(None)
    assert len(sent) == 1
    assert module.run_once(digest) == digest
    assert len(sent) == 1
    assert json.loads((tmp_path / "status.json").read_text())["status"] == "healthy"


def test_read_source_rejects_identifiers(monkeypatch) -> None:
    monkeypatch.setattr(module, "SOURCE_URL", "http://source")
    monkeypatch.setattr(module, "_request_json", lambda _url: {"bssid": "AA:BB", "position": {"x": 1, "y": 2}})
    try:
        module.read_source()
    except ValueError as exc:
        assert "no permitidos" in str(exc)
    else:
        raise AssertionError("se aceptó un identificador WiFi")

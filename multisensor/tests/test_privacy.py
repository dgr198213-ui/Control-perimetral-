from __future__ import annotations

import pytest

from multisensor.privacy import PrivacyViolation, PublicResourcePolicy, sanitize_public_resource


def test_public_resource_rounds_location_and_keeps_only_safe_fields() -> None:
    result = sanitize_public_resource(
        {"id": "dgt:1", "label": "A-66", "latitude": 43.240021, "longitude": -5.340019, "url": "https://example.test/image.jpg"},
        PublicResourcePolicy("DGT", precision_decimals=3),
    )
    assert result["location"] == {"latitude": 43.24, "longitude": -5.34}
    assert result["public"] is True
    assert result["retention_seconds"] == 3600


def test_public_resource_rejects_personal_or_device_identifiers() -> None:
    with pytest.raises(PrivacyViolation):
        sanitize_public_resource({"id": "wifi", "bssid": "AA:BB:CC:DD:EE:FF"}, PublicResourcePolicy("WiFi"))


def test_public_resource_policy_rejects_unbounded_retention() -> None:
    with pytest.raises(PrivacyViolation):
        PublicResourcePolicy("WiFi", retention_seconds=0)

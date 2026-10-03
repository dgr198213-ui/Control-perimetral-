"""Catálogo conservador de recursos públicos de contexto cartográfico."""
from __future__ import annotations

PUBLIC_SOURCES = (
    {
        "id": "ign-pnoa-orthophotos",
        "title": "Ortofotografía PNOA/IGN",
        "kind": "satellite_or_orthophoto",
        "status": "available_for_config",
        "url": "https://www.ign.es/wmts/pnoa-ma?REQUEST=GetCapabilities&SERVICE=WMTS",
        "refresh": "periodic",
        "personal_tracking": False,
        "notes": "Capa cartográfica; no representa una posición en tiempo real.",
    },
    {
        "id": "openstreetmap-basemap",
        "title": "Mapa base OpenStreetMap",
        "kind": "basemap",
        "status": "policy_restricted",
        "url": "https://www.openstreetmap.org/copyright",
        "refresh": "best_effort",
        "personal_tracking": False,
        "notes": "Usar solo respetando atribución, identificación y límites de teselas.",
    },
)


def list_public_sources() -> list[dict[str, object]]:
    return [dict(source) for source in PUBLIC_SOURCES]

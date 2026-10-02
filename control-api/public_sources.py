"""Catálogo conservador de recursos públicos disponibles para el sistema."""
from __future__ import annotations

PUBLIC_SOURCES = (
    {
        "id": "dgt-traffic-cameras",
        "title": "Cámaras públicas de tráfico DGT",
        "kind": "traffic_camera_catalog",
        "status": "integrated",
        "url": "https://nap.dgt.es/en/dataset/camaras-dgt-datex2-v3-7",
        "refresh": "hourly",
        "personal_tracking": False,
        "notes": "Metadatos e imágenes públicas; no es vídeo privado ni vigilancia del perímetro.",
    },
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
    {
        "id": "local-wifi-csi",
        "title": "WiFi-CSI local autorizado",
        "kind": "sensor_input",
        "status": "experimental",
        "url": None,
        "refresh": "event_driven",
        "personal_tracking": False,
        "notes": "Solo señales agregadas del propio perímetro; no se importan identificadores de red ni de terceros.",
    },
)


def list_public_sources() -> list[dict[str, object]]:
    return [dict(source) for source in PUBLIC_SOURCES]

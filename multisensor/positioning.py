"""Triangulación 2D determinista para tres anclas WiFi-CSI propias."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Mapping


class PositioningError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Anchor:
    id: str
    x: float
    y: float


def triangulate(measurements: Mapping[str, float], anchors: tuple[Anchor, ...]) -> tuple[float, float, float]:
    if len(anchors) != 3 or len({anchor.id for anchor in anchors}) != 3:
        raise PositioningError("se requieren exactamente tres anclas distintas")
    if any(anchor.id not in measurements for anchor in anchors):
        raise PositioningError("faltan mediciones para alguna ancla")
    distances = {anchor.id: float(measurements[anchor.id]) for anchor in anchors}
    if any(value <= 0 for value in distances.values()):
        raise PositioningError("las distancias deben ser positivas")
    first, second, third = anchors
    d1, d2, d3 = (distances[first.id], distances[second.id], distances[third.id])
    a11, a12 = 2 * (second.x - first.x), 2 * (second.y - first.y)
    a21, a22 = 2 * (third.x - first.x), 2 * (third.y - first.y)
    b1 = d1**2 - d2**2 + second.x**2 - first.x**2 + second.y**2 - first.y**2
    b2 = d1**2 - d3**2 + third.x**2 - first.x**2 + third.y**2 - first.y**2
    determinant = a11 * a22 - a12 * a21
    if abs(determinant) < 1e-9:
        raise PositioningError("las anclas no forman una geometría triangulable")
    x = (b1 * a22 - a12 * b2) / determinant
    y = (a11 * b2 - b1 * a21) / determinant
    residual = sum(abs(hypot(x - anchor.x, y - anchor.y) - distances[anchor.id]) for anchor in anchors) / 3
    confidence = max(0.0, min(1.0, 1.0 - residual / max(max(distances.values()), 1.0)))
    return round(x, 4), round(y, 4), round(confidence, 4)

"""Pruebas del motor de correlación temporal y espacial."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from multisensor.contracts import Location, Observation
from multisensor.correlation import CorrelationConfig, CorrelationError, TemporalSpatialCorrelator


UTC = timezone.utc
BASE = datetime(2026, 9, 28, 19, 20, tzinfo=UTC)


def observation(
    identifier: str,
    sensor_type: str,
    seconds: int,
    confidence: float,
    *,
    location: Location | None = None,
    event_type: str = "motion",
    payload: dict | None = None,
) -> Observation:
    return Observation(
        id=identifier,
        sensor_id=f"{sensor_type}-1",
        sensor_type=sensor_type,
        timestamp=BASE + timedelta(seconds=seconds),
        event_type=event_type,
        confidence=confidence,
        location=location,
        payload=payload or {},
        source="test",
    )


class TemporalSpatialCorrelatorTests(unittest.TestCase):
    def test_single_camera_does_not_generate_correlation(self) -> None:
        engine = TemporalSpatialCorrelator()

        result = engine.ingest(
            observation("cam-1", "camera", 0, 0.91, location=Location(43.24, -5.34))
        )

        self.assertIsNone(result)

    def test_camera_pir_and_wifi_are_combined_with_auditable_factors(self) -> None:
        engine = TemporalSpatialCorrelator()
        camera = observation("cam-1", "camera", 0, 0.91, location=Location(43.240000, -5.340000), event_type="person_detected")
        pir = observation("pir-1", "pir", 1, 0.78, location=Location(43.240050, -5.340000))
        wifi = observation("wifi-1", "wifi_csi", 2, 0.84, location=Location(43.240020, -5.340010), event_type="human_motion")

        self.assertIsNone(engine.ingest(camera))
        two_sensor_result = engine.ingest(pir)
        result = engine.ingest(wifi)

        self.assertIsNotNone(two_sensor_result)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.event.event_type, "multisensor_motion")
        self.assertEqual(set(result.sensor_types), {"camera", "pir", "wifi_csi"})
        self.assertEqual(set(result.event.observation_ids), {"cam-1", "pir-1", "wifi-1"})
        self.assertGreater(result.event.confidence, 0.0)
        self.assertLessEqual(result.event.confidence, 1.0)
        self.assertEqual(result.event.payload["rule"], "evidence_weight * temporal_factor * spatial_factor * reliability_factor")
        self.assertEqual(result.event.payload["temporal_span_seconds"], 2.0)
        self.assertGreater(result.event.payload["spatial_factor"], 0.9)

    def test_events_outside_temporal_window_do_not_correlate(self) -> None:
        engine = TemporalSpatialCorrelator(CorrelationConfig(temporal_window=timedelta(seconds=3)))
        camera = observation("cam-1", "camera", 0, 0.91)
        pir = observation("pir-1", "pir", 4, 0.78)

        self.assertIsNone(engine.ingest(camera))
        self.assertIsNone(engine.ingest(pir))
        self.assertEqual(engine.recent_observation_ids, ("pir-1",))

    def test_spatially_incompatible_sensors_do_not_correlate(self) -> None:
        engine = TemporalSpatialCorrelator(CorrelationConfig(max_distance_m=50))
        engine.ingest(observation("cam-1", "camera", 0, 0.91, location=Location(43.24, -5.34)))

        with self.assertRaisesRegex(CorrelationError, "espacialmente incompatibles"):
            engine.ingest(observation("pir-1", "pir", 1, 0.78, location=Location(43.25, -5.34)))
        self.assertEqual(engine.recent_observation_ids, ("cam-1",))

    def test_duplicate_observation_does_not_duplicate_correlation(self) -> None:
        engine = TemporalSpatialCorrelator()
        camera = observation("cam-1", "camera", 0, 0.91)
        pir = observation("pir-1", "pir", 1, 0.78)

        engine.ingest(camera)
        result = engine.ingest(pir)
        duplicate = engine.ingest(pir)

        self.assertIsNotNone(result)
        self.assertIsNone(duplicate)

    def test_cleared_pir_is_not_positive_evidence(self) -> None:
        engine = TemporalSpatialCorrelator()
        engine.ingest(observation("cam-1", "camera", 0, 0.91))

        result = engine.ingest(
            observation(
                "pir-clear",
                "pir",
                1,
                0.0,
                event_type="motion_cleared",
                payload={"motion": False},
            )
        )

        self.assertIsNone(result)

    def test_unknown_location_is_penalized_but_not_falsely_rejected(self) -> None:
        engine = TemporalSpatialCorrelator()
        camera = observation("cam-1", "camera", 0, 0.91, location=Location(43.24, -5.34))
        pir = observation("pir-1", "pir", 1, 0.78)

        self.assertIsNone(engine.ingest(camera))
        result = engine.ingest(pir)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertLess(result.spatial_factor, 1.0)


if __name__ == "__main__":
    unittest.main()

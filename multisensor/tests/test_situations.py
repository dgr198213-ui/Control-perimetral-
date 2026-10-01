"""Pruebas del motor puro de situaciones."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from multisensor.contracts import Event
from multisensor.situations import SituationEngine, SituationPolicy


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def event_with_confidence(confidence: float, event_id: str = "event-1") -> Event:
    return Event(
        id=event_id,
        event_type="multisensor_motion",
        timestamp=NOW,
        observation_ids=("observation-camera", "observation-pir"),
        confidence=confidence,
        payload={"temporal_span_seconds": 2.0},
    )


class SituationEngineTests(unittest.TestCase):
    def test_low_confidence_event_creates_activity_detected(self) -> None:
        decision = SituationEngine().evaluate(event_with_confidence(0.49))

        self.assertEqual(decision.reason, "classified")
        self.assertIsNotNone(decision.situation)
        assert decision.situation is not None
        self.assertEqual(decision.situation.situation_type, "activity_detected")
        self.assertEqual(decision.situation.observation_ids, ("observation-camera", "observation-pir"))
        self.assertEqual(decision.situation.payload["source_event_id"], "event-1")

    def test_high_confidence_event_creates_suspicious_activity(self) -> None:
        decision = SituationEngine().evaluate(event_with_confidence(0.5))

        self.assertIsNotNone(decision.situation)
        assert decision.situation is not None
        self.assertEqual(decision.situation.situation_type, "suspicious_activity")
        self.assertEqual(decision.situation.status, "active")

    def test_same_event_is_not_emitted_twice(self) -> None:
        engine = SituationEngine()
        first = engine.evaluate(event_with_confidence(0.8))
        duplicate = engine.evaluate(event_with_confidence(0.8))

        self.assertIsNotNone(first.situation)
        self.assertIsNone(duplicate.situation)
        self.assertEqual(duplicate.reason, "duplicate_event")

    def test_policy_validates_its_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, "entre 0 y 1"):
            SituationPolicy(suspicious_confidence_threshold=1.1)


if __name__ == "__main__":
    unittest.main()

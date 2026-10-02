"""Pruebas de políticas, acciones durables y contexto."""
from datetime import datetime, timezone

from multisensor.actions import ActionQueue, ActionRequest
from multisensor.context import ContextEngine
from multisensor.contracts import Situation
from multisensor.policy import PolicyEngine, ProtectionPolicy


NOW = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)


def suspicious() -> Situation:
    return Situation(
        id="situation:1",
        situation_type="suspicious_activity",
        started_at=NOW,
        updated_at=NOW,
        confidence=0.8,
        observation_ids=("observation:1",),
    )


def test_policy_decision_is_explainable_and_respects_compliance() -> None:
    engine = PolicyEngine(ProtectionPolicy(mode="balanced", cooldown_seconds=30))
    allowed = engine.evaluate(suspicious(), compliance_allowed=True)
    blocked = engine.evaluate(suspicious(), compliance_allowed=False)

    assert allowed.allowed is True
    assert allowed.action_type == "notify_suspicious"
    assert allowed.cooldown_seconds == 30
    assert blocked.allowed is False
    assert "cumplimiento" in blocked.reason


def test_action_queue_deduplicates_and_retries(tmp_path) -> None:
    queue = ActionQueue(tmp_path / "actions.sqlite3", max_attempts=2)
    request = ActionRequest("action:1", "notify", "situation:1", {"text": "aviso"}, NOW)
    assert queue.enqueue(request) is True
    assert queue.enqueue(request) is False

    calls = []
    assert queue.process(lambda item: calls.append(item.id), now=NOW) == 1
    assert queue.get_status("action:1") == "sent"
    assert calls == ["action:1"]


def test_context_engine_explains_night_persistence() -> None:
    context = ContextEngine().enrich(suspicious(), zone="perimetro", persistence_seconds=38)

    assert context.time_bucket == "night"
    assert context.interpretation == "Actividad sospechosa persistente durante la noche."

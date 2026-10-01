"""Motor de políticas determinista y explicable para situaciones."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multisensor.contracts import Situation


@dataclass(frozen=True, slots=True)
class ProtectionPolicy:
    version: str = "v1"
    mode: Literal["quiet", "balanced", "strict"] = "balanced"
    notify_on_suspicious: bool = True
    notify_on_incident: bool = True
    suspicious_threshold: float = 0.5
    cooldown_seconds: int = 60

    def __post_init__(self) -> None:
        if self.mode not in {"quiet", "balanced", "strict"}:
            raise ValueError("mode no reconocido")
        if not 0.0 <= self.suspicious_threshold <= 1.0:
            raise ValueError("suspicious_threshold debe estar entre 0 y 1")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds no puede ser negativo")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    action_type: str | None
    reason: str
    cooldown_seconds: int
    policy_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "action_type": self.action_type,
            "reason": self.reason,
            "cooldown_seconds": self.cooldown_seconds,
            "policy_version": self.policy_version,
        }


class PolicyEngine:
    """Evalúa una Situation sin notificar ni ejecutar acciones."""

    def __init__(self, policy: ProtectionPolicy | None = None) -> None:
        self.policy = policy or ProtectionPolicy()

    def evaluate(
        self,
        situation: Situation,
        *,
        compliance_allowed: bool,
        in_quiet_hours: bool = False,
    ) -> PolicyDecision:
        if not compliance_allowed:
            return self._deny("Operación bloqueada por cumplimiento.")
        if situation.situation_type != "suspicious_activity":
            return self._deny("La situación no es actividad sospechosa.")
        if situation.confidence < self.policy.suspicious_threshold:
            return self._deny("La confianza está por debajo del umbral de la política.")
        if in_quiet_hours and self.policy.mode == "quiet":
            return self._deny("La política tranquila suprime avisos durante las horas configuradas.")
        if not self.policy.notify_on_suspicious:
            return self._deny("Los avisos de actividad sospechosa están desactivados.")
        return PolicyDecision(
            allowed=True,
            action_type="notify_suspicious",
            reason="La situación supera el umbral y la política permite avisarla.",
            cooldown_seconds=self.policy.cooldown_seconds,
            policy_version=self.policy.version,
        )

    def _deny(self, reason: str) -> PolicyDecision:
        return PolicyDecision(
            allowed=False,
            action_type=None,
            reason=reason,
            cooldown_seconds=self.policy.cooldown_seconds,
            policy_version=self.policy.version,
        )

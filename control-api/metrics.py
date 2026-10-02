"""Métricas Prometheus minimalistas para la API local."""
from __future__ import annotations

from collections import Counter
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str]] = Counter()

    def observe_request(self, method: str, path: str, status_code: int) -> None:
        with self._lock:
            self._requests[(method, path, str(status_code))] += 1

    def render(self) -> str:
        lines = [
            "# HELP control_api_requests_total Total de peticiones HTTP atendidas.",
            "# TYPE control_api_requests_total counter",
        ]
        with self._lock:
            items = sorted(self._requests.items())
        for (method, path, status), count in items:
            safe_path = path.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'control_api_requests_total{{method="{method}",path="{safe_path}",status="{status}"}} {count}')
        return "\n".join(lines) + "\n"

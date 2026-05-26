"""Runtime settings and pacing for AI report processing."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("services.ai_runtime")


@dataclass
class AIRuntimeSettings:
    provider: str
    api_key: str
    model: str
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    retry_base_seconds: float = 5.0


@dataclass
class AIProcessingStats:
    calls: int = 0
    succeeded: int = 0
    failed: int = 0
    labels_failed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "labels_failed": self.labels_failed,
        }


def runtime_from_config(cfg: dict[str, Any]) -> AIRuntimeSettings:
    def _float(key: str, default: float) -> float:
        try:
            return max(0.0, float(cfg.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _int(key: str, default: int) -> int:
        try:
            return max(0, int(cfg.get(key, default)))
        except (TypeError, ValueError):
            return default

    return AIRuntimeSettings(
        provider=(cfg.get("provider") or "openrouter").strip(),
        api_key=(cfg.get("api_key") or "").strip(),
        model=(cfg.get("model") or "openai/gpt-4o-mini").strip(),
        request_delay_seconds=_float("ai_request_delay_seconds", 2.0),
        max_retries=_int("ai_max_retries", 3),
        retry_base_seconds=_float("ai_retry_base_seconds", 5.0),
    )


def pause_before_ai_call(delay_seconds: float, *, label: str) -> None:
    if delay_seconds <= 0:
        return
    log.info("AI pause %.1fs before %s", delay_seconds, label)
    time.sleep(delay_seconds)

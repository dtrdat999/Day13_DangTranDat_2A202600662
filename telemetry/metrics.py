"""Per-call metrics tracker (Day 13 Track 2).

Every provider calls tracker.track_request(...) at the end of generate(), so a
LLM_METRIC event lands in the logs for analyze_logs.py to aggregate. Day 13 adds
cost_usd (computed from token usage via telemetry.cost) -- cost becomes a
first-class metric alongside latency and tokens.
"""
from __future__ import annotations

from typing import Any, Optional

from telemetry.cost import cost_from_usage
from telemetry.logger import logger


class PerformanceTracker:
    def track_request(
        self,
        provider: str,
        model: str,
        usage: dict[str, int],
        latency_ms: int,
        event: str = "LLM_METRIC",
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        usage = usage or {}
        data: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_usd": cost_from_usage(model, usage),   # Track 2: cost as a metric
        }
        if extra:
            data.update(extra)
        logger.log_event(event, data)


# Global tracker instance -- imported by every provider.
tracker = PerformanceTracker()

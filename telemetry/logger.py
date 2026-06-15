"""Structured JSON logger -- "the trace is the truth" (Day 13 Track 1).

Every agent step and LLM call is logged as one JSON object per line to
logs/YYYY-MM-DD.log, so scripts/analyze_logs.py can compute aggregate metrics.

Day 13 additions over the Day 3 logger:
  - a correlation_id contextvar, auto-attached to EVERY event (Track 1) so all
    logs of one request share an id (and that id is the seed of trace_id)
  - optional PII redaction of payload strings via telemetry.redact (Track 1)
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

_correlation_id: contextvars.ContextVar = contextvars.ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    return "req-" + uuid.uuid4().hex[:8]


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


class IndustryLogger:
    def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:  # attach once, even if constructed twice
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".log")
            fmt = logging.Formatter("%(message)s")  # raw JSON, no prefix

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(fmt)
            self.logger.addHandler(file_handler)

            if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                console = logging.StreamHandler()
                console.setFormatter(fmt)
                self.logger.addHandler(console)

    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        # Track 1: redact PII out of the payload before it touches disk (default ON).
        from telemetry import redact
        if redact.enabled():
            data = redact.redact_value(data)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "correlation_id": get_correlation_id(),
            "data": data,
        }
        self.logger.info(json.dumps(payload, ensure_ascii=False))


# Global logger instance
logger = IndustryLogger()

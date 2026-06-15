"""Append each trace as one JSON line to traces/traces.jsonl (Track 4 default).

Newline-delimited JSON so scripts/build_dashboard.py and scripts/verify.py can
read traces back without a database. This is the offline 'observability backend'.
"""
from __future__ import annotations
import json
import os
from telemetry.backends.base import Backend


class FileBackend(Backend):
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("OBS_TRACE_FILE", "traces/traces.jsonl")

    def export_trace(self, trace: dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

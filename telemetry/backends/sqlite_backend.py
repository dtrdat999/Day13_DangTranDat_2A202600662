"""Store traces in a local SQLite DB (Track 4 alternative). No external service."""
from __future__ import annotations
import json
import os
import sqlite3
from telemetry.backends.base import Backend


class SqliteBackend(Backend):
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("OBS_TRACE_DB", "traces/traces.db")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS traces "
                "(span_id TEXT, name TEXT, duration_ms INTEGER, status TEXT, json TEXT)"
            )

    def export_trace(self, trace: dict) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO traces VALUES (?,?,?,?,?)",
                (trace["span_id"], trace["name"], trace["duration_ms"],
                 trace["status"], json.dumps(trace, ensure_ascii=False)),
            )

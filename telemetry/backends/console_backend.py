"""Print the trace as an indented span tree -- the zero-setup 'dashboard' (Track 3/4)."""
from __future__ import annotations
from telemetry.backends.base import Backend
from telemetry.tracing import format_tree


class ConsoleBackend(Backend):
    def export_trace(self, trace: dict) -> None:
        print("\n[trace] " + trace.get("attributes", {}).get("correlation_id", trace["span_id"]))
        print(format_tree(trace))

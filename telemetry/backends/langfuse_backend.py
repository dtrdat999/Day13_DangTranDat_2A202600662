"""Send traces to Langfuse (Track 4, real backend) -- activates only with keys.

Uses the CURRENT Langfuse Python SDK v4 (2026), which is OpenTelemetry-based.
Requires `pip install langfuse` and env LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
(+ optional LANGFUSE_HOST for self-host). If the SDK or keys are missing, the
constructor raises so the factory falls back to the file backend -- the zero-key
path is never broken by selecting langfuse without keys.
"""
from __future__ import annotations
import os
from telemetry.backends.base import Backend


class LangfuseBackend(Backend):
    def __init__(self):
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            raise RuntimeError("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
        try:
            from langfuse import get_client  # langfuse v4 SDK
        except ImportError as exc:
            raise RuntimeError("langfuse not installed (pip install langfuse)") from exc
        self._client = get_client()

    def _emit(self, span: dict, parent=None):
        # Recreate the span tree in Langfuse using the v4 context-manager API.
        cm = self._client.start_as_current_observation(
            name=span["name"],
            as_type="generation" if span["name"].startswith("chat") else "span",
            metadata={**span.get("attributes", {}), "duration_ms": span["duration_ms"],
                      "status": span["status"]},
        )
        with cm:
            for child in span.get("children", []):
                self._emit(child)

    def export_trace(self, trace: dict) -> None:
        self._emit(trace)
        self._client.flush()

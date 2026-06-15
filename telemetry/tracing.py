"""Lightweight distributed tracing for the agent loop (Track 3).

A Tracer holds one trace = a tree of Spans. Spans nest via a contextvar stack, so
child spans (LLM call, tool call) auto-attach to the active parent (invoke_agent)
without threading a span object through every call -- the same idea real OTel SDKs
use for context propagation.

Span attribute names follow the OpenTelemetry GenAI semantic conventions
(gen_ai.*) so a trace reads like a real OTel trace. NOTE: those conventions were
still 'Development' (experimental) in 2026 -- names may change.

When the ROOT span closes, the whole trace is handed to the configured backend
(console / file / sqlite / langfuse). Backend failures never crash the app:
observability must not take down the thing it observes.
"""
from __future__ import annotations
import contextvars
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

_current_span: contextvars.ContextVar = contextvars.ContextVar("current_span", default=None)


def _now_ms() -> float:
    return time.time() * 1000.0


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    start_ms: float
    end_ms: Optional[float] = None
    attributes: dict = field(default_factory=dict)
    status: str = "ok"
    children: list = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return 0 if self.end_ms is None else int(self.end_ms - self.start_ms)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "children": [c.to_dict() for c in self.children],
        }


class _SpanCtx:
    """Context manager returned by Tracer.start_span()."""
    def __init__(self, tracer: "Tracer", span: Span, token):
        self.tracer, self.span, self._token = tracer, span, token

    def set(self, **attrs):
        self.span.attributes.update(attrs)
        return self

    def set_status(self, status: str):
        self.span.status = status
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.span.end_ms = _now_ms()
        if exc_type is not None:
            self.span.status = "error"
            self.span.attributes["error.type"] = exc_type.__name__
        _current_span.reset(self._token)
        if self.span.parent_id is None:      # root closed -> export whole trace
            self.tracer.export(self.span)
        return False                          # never swallow exceptions


class Tracer:
    def __init__(self, backend=None, service_name: str = "ecommerce-agent"):
        if backend is None:
            from telemetry.backends.factory import build_backend
            backend = build_backend()
        self.backend = backend
        self.service_name = service_name
        self.trace_id = uuid.uuid4().hex[:16]
        self.last_root: Optional[Span] = None

    def start_span(self, name: str, **attributes) -> _SpanCtx:
        parent = _current_span.get()
        span = Span(
            name=name, trace_id=self.trace_id, span_id=uuid.uuid4().hex[:8],
            parent_id=parent.span_id if parent else None,
            start_ms=_now_ms(), attributes=dict(attributes),
        )
        if parent is not None:
            parent.children.append(span)
        token = _current_span.set(span)
        return _SpanCtx(self, span, token)

    def export(self, root: Span) -> None:
        self.last_root = root
        try:
            self.backend.export_trace(root.to_dict())
        except Exception as exc:       # observability must never crash the app
            print(f"[tracing] backend export failed (non-fatal): {exc}")


def format_tree(trace: dict, indent: int = 0) -> str:
    """Pretty-print a trace dict as an indented span tree (used by console backend)."""
    pad = "  " * indent
    flag = "" if trace.get("status") == "ok" else f"  [{trace.get('status')}]"
    line = f"{pad}{trace['name']:<42} {trace['duration_ms']:>6}ms{flag}"
    lines = [line]
    for child in trace.get("children", []):
        lines.append(format_tree(child, indent + 1))
    return "\n".join(lines)

"""Pick a backend from OBS_BACKEND (console | file | sqlite | langfuse | multi).

Default = 'file' (traces/traces.jsonl) so traces persist for grading/analysis with
zero setup. 'multi' = console + file (see the tree AND persist it). Selecting
'langfuse' without keys/SDK falls back to file with a printed note.
"""
from __future__ import annotations
import os
from telemetry.backends.base import Backend, MultiBackend
from telemetry.backends.console_backend import ConsoleBackend
from telemetry.backends.file_backend import FileBackend
from telemetry.backends.sqlite_backend import SqliteBackend


def build_backend(name: str | None = None) -> Backend:
    name = (name or os.getenv("OBS_BACKEND", "file")).lower()
    if name == "console":
        return ConsoleBackend()
    if name == "file":
        return FileBackend()
    if name == "sqlite":
        return SqliteBackend()
    if name == "multi":
        return MultiBackend([ConsoleBackend(), FileBackend()])
    if name == "langfuse":
        try:
            from telemetry.backends.langfuse_backend import LangfuseBackend
            return LangfuseBackend()
        except Exception as exc:
            print(f"[backends] langfuse unavailable ({exc}); falling back to file backend")
            return FileBackend()
    return FileBackend()

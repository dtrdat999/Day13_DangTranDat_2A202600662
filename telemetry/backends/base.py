"""Backend interface + a Multi backend that fans out to several."""
from __future__ import annotations
from abc import ABC, abstractmethod


class Backend(ABC):
    @abstractmethod
    def export_trace(self, trace: dict) -> None:
        """Persist/send one finished trace (a nested span dict)."""
        raise NotImplementedError


class MultiBackend(Backend):
    """Send each trace to several backends (e.g. console + file)."""
    def __init__(self, backends: list[Backend]):
        self.backends = backends

    def export_trace(self, trace: dict) -> None:
        for b in self.backends:
            try:
                b.export_trace(trace)
            except Exception as exc:
                print(f"[backends] {type(b).__name__} failed (non-fatal): {exc}")

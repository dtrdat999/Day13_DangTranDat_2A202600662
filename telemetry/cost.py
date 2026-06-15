"""Token -> cost conversion for AI-specific cost metrics (Track 2).

The single most important AI-era observability lesson: an HTTP 200 tells you
nothing about money. Cost is a first-class metric, computed from the token usage
every provider already returns:

    cost = prompt_tokens * input_price + completion_tokens * output_price

Prices are USD per 1,000,000 tokens. Input and output are priced SEPARATELY on
purpose: output is typically 3-6x more expensive than input, so a chatty agent
costs far more than its prompt length suggests. (Day 13, Section 10.)

2026 list prices, for teaching -- verify against the provider pricing page before
quoting real numbers. The mock model gets a small nominal price so the zero-key
path still produces non-trivial cost metrics.
"""
from __future__ import annotations
from typing import Optional

# (input_usd_per_1M, output_usd_per_1M). Matched by longest-prefix, case-insensitive.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-4":    (5.00, 25.00),
    "claude-sonnet-4":  (3.00, 15.00),
    "claude-haiku-4":   (1.00, 5.00),
    "gpt-4o-mini":      (0.15, 0.60),
    "gpt-4o":           (2.50, 10.00),
    "gpt-5":            (5.00, 30.00),
    "gemini-2.5-pro":   (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3":         (2.00, 12.00),
    "gpt-5.4-mini":     (0.40, 1.60),
    "gpt-5.4-nano":     (0.10, 0.40),
    "local":            (0.0, 0.0),     # llama.cpp: no API cost
    "mock":             (0.50, 1.50),   # nominal, so offline cost metrics are non-zero
}
_DEFAULT_PRICE: tuple[float, float] = (1.00, 3.00)


def price_for(model: str) -> tuple[float, float]:
    """Return (input_per_1M, output_per_1M) via longest-prefix match."""
    if not model:
        return _DEFAULT_PRICE
    m = model.lower()
    best: Optional[str] = None
    for key in PRICE_TABLE:
        if m.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return PRICE_TABLE[best] if best else _DEFAULT_PRICE


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD cost for one LLM call from its token usage (often tiny, e.g. 0.000123)."""
    in_price, out_price = price_for(model)
    cost = (prompt_tokens / 1_000_000.0) * in_price + (completion_tokens / 1_000_000.0) * out_price
    return round(cost, 8)


def cost_from_usage(model: str, usage: dict) -> float:
    """Wrapper for the {'prompt_tokens','completion_tokens'} dict on every LLMResponse."""
    usage = usage or {}
    return cost_usd(model, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))

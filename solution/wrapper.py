"""Observability + mitigation layer for the Observathon agent.

The simulator calls mitigate() around the silent black-box agent (a real LLM). This is
the only place to observe latency / tokens / cost / tools / loops / PII, and the place
for legal mitigations:
  * sanitize the injected order note (prompt-injection defense),
  * a deterministic arithmetic guardrail that recomputes the total from authoritative
    tool data, using a runtime CONSENSUS of each coupon's percent and each item's price
    learned from the tools themselves (robust to a noisy tool or a skipped tool call),
  * cache, retry, PII redaction.
Imports: standard library + bundled telemetry/ only.
"""
from __future__ import annotations

import re
import time

from telemetry.logger import logger, new_correlation_id, set_correlation_id
from telemetry.cost import cost_from_usage
from telemetry.redact import redact

_NOTE_RE = re.compile(r"(?is)\b(?:ghi\s*ch[uú]|note|system)\s*[:\-].*$")
_QTY_RE = re.compile(r"\b(?:mua|đặt|dat|lấy|lay|order|c[aầ]n)\s+(\d{1,3})\b", re.I)
_QTY_RE2 = re.compile(r"\b(\d{1,3})\s*(?:c[aá]i|chi[eế]c|s[aả]n\s*ph[aẩ]m)\b", re.I)
_DEST_RE = re.compile(r"\b(?:giao|ship|đến|den|gửi|gui|tới|toi|v[aậ]n\s*chuy[eể]n)\b", re.I)
_COUPON_RE = re.compile(r"(?:coupon|\bma)\s+([A-Za-z0-9]{3,})", re.I)
_TOTAL_RE = re.compile(r"(Tong cong:\s*)([\d.,]+)", re.I)


def _sanitize(question):
    if not isinstance(question, str):
        return question
    return _NOTE_RE.sub("", question).strip()


def _obs_by_tool(trace, tool):
    for s in trace:
        if isinstance(s, dict) and s.get("tool") == tool and isinstance(s.get("observation"), dict):
            return s["observation"]
    return None


def _parse_qty(q):
    m = _QTY_RE.search(q) or _QTY_RE2.search(q)
    return int(m.group(1)) if m else None


# ---- runtime consensus tables, kept in the shared cache (derived from tool outputs) ----
def _bump(cache, key, value):
    d = cache.get(key)
    if not isinstance(d, dict):
        d = {}
    d[value] = d.get(value, 0) + 1
    cache[key] = d


def _mode(cache, lock, key):
    if cache is None or lock is None:
        return None
    with lock:
        d = cache.get(key)
    if isinstance(d, dict) and d:
        return max(d.items(), key=lambda kv: kv[1])[0]
    return None


def _learn(trace, cache, lock):
    """Record coupon->percent and item->price seen in tool outputs so the guardrail can
    stay correct even when a later request skips a tool or the tool returns a noisy value
    (we keep counts and use the most frequent value = consensus)."""
    if cache is None or lock is None:
        return
    try:
        with lock:
            for s in trace:
                if not isinstance(s, dict):
                    continue
                obs = s.get("observation")
                if not isinstance(obs, dict):
                    continue
                if s.get("tool") == "get_discount" and obs.get("code"):
                    pct = obs.get("percent", 0) if obs.get("valid") else 0
                    _bump(cache, ("coupon_pct", str(obs["code"]).upper()), int(pct))
                elif s.get("tool") == "check_stock" and obs.get("item") and obs.get("unit_price_vnd") is not None:
                    _bump(cache, ("item_price", str(obs["item"]).lower()), int(obs["unit_price_vnd"]))
    except Exception:
        pass


def _grounded_total(question, trace, cache, lock):
    """Recompute the order total from authoritative tool data + learned consensus.
    Returns an int total, 'refuse' (out of stock / not found), or None (can't ground)."""
    stock = _obs_by_tool(trace, "check_stock")
    if not stock:
        return None
    if not stock.get("found", True) or not stock.get("in_stock", True):
        return "refuse"
    item = str(stock.get("item", "")).lower()
    unit = stock.get("unit_price_vnd")
    if unit is None:
        unit = _mode(cache, lock, ("item_price", item))   # consensus fallback
    qty = _parse_qty(question)
    if unit is None or qty is None:
        return None

    # discount: prefer learned consensus (filters tool noise / fixes a skipped call)
    percent = None
    m = _COUPON_RE.search(question)
    if m:
        percent = _mode(cache, lock, ("coupon_pct", m.group(1).upper()))
        if percent is None:
            disc = _obs_by_tool(trace, "get_discount")
            if disc is not None:
                percent = disc.get("percent", 0) if disc.get("valid") else 0
        if percent is None:
            return None          # coupon named but unresolved -> don't guess
    else:
        percent = 0

    ship = _obs_by_tool(trace, "calc_shipping")
    if ship is not None:
        shipping = ship.get("cost_vnd")
        if shipping is None:
            return None
    elif _DEST_RE.search(question):
        return None
    else:
        shipping = 0

    subtotal = unit * qty
    discounted = subtotal * (100 - int(percent)) // 100
    return discounted + shipping


def _apply_guardrail(question, result, cache, lock):
    try:
        g = _grounded_total(question, result.get("trace") or [], cache, lock)
        ans = result.get("answer")
        if not isinstance(ans, str):
            return
        if g == "refuse":
            if _TOTAL_RE.search(ans):
                result["answer"] = "San pham hien khong co hang nen khong the dat mua."
        elif isinstance(g, int):
            if _TOTAL_RE.search(ans):
                result["answer"] = _TOTAL_RE.sub(lambda mm: mm.group(1) + str(g), ans, count=1)
            else:
                result["answer"] = ans.rstrip() + f"\nTong cong: {g} VND"
    except Exception:
        pass


def _call_with_retry(call_next, question, conf, attempts=2, backoff=0.2):
    result = call_next(question, conf)
    tries = 1
    while result.get("status") == "wrapper_error" and tries < attempts:
        time.sleep(backoff * tries)
        result = call_next(question, conf)
        tries += 1
    return result


def mitigate(call_next, question, config, context):
    set_correlation_id(new_correlation_id())
    t0 = time.time()

    clean_q = _sanitize(question)
    cache = context.get("cache")
    lock = context.get("cache_lock")
    cache_key = ("answer", clean_q)

    if cache is not None and lock is not None:
        with lock:
            cached = cache.get(cache_key)
        if cached is not None:
            logger.log_event("CACHE_HIT", {"qid": context.get("qid")})
            return cached

    result = _call_with_retry(call_next, clean_q, config)

    # Learn coupon/price consensus from this request's tools, then apply the guardrail.
    trace = result.get("trace") or []
    _learn(trace, cache, lock)
    _apply_guardrail(clean_q, result, cache, lock)

    meta = result.get("meta") or {}
    usage = meta.get("usage") or {}
    model = meta.get("model") or config.get("model", "")

    pii_n = 0
    answer = result.get("answer")
    if isinstance(answer, str):
        red, pii_n = redact(answer)
        if pii_n:
            result["answer"] = red

    actions = [str(s.get("action")) for s in trace if isinstance(s, dict)]
    repeated = len(actions) - len(set(actions))
    tools = meta.get("tools_used") or []
    logger.log_event("CALL", {
        "qid": context.get("qid"),
        "session": context.get("session_id"),
        "turn": context.get("turn_index"),
        "status": result.get("status"),
        "wall_ms": int((time.time() - t0) * 1000),
        "latency_ms": meta.get("latency_ms"),
        "steps": result.get("steps"),
        "tool_count": len(tools),
        "tools_used": tools,
        "repeated_actions": repeated,
        "usage": usage,
        "cost_usd": cost_from_usage(model, usage),
        "pii_redacted": pii_n,
    })

    if cache is not None and lock is not None and result.get("status") == "ok":
        with lock:
            cache[cache_key] = result
    return result

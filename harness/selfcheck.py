"""Self-check your submission BEFORE you push (pure stdlib, no agent/key needed).
  python harness/selfcheck.py
Validates solution/config.json + wrapper.py + prompt.txt + examples.json + findings.json."""
from __future__ import annotations
import json
import os
import re
import sys

ALLOWED = {"provider", "model", "model_price_tier", "max_steps", "loop_guard", "temperature",
           "context_size", "verbose_system", "timeout_ms", "max_completion_tokens", "retry", "cache",
           "normalize_unicode", "redact_pii", "session_drift_rate", "context_reset_every",
           "tool_error_rate", "catalog_override", "route_rules", "session_id", "turn_index",
           "system_prompt", "prompt_file", "examples_file", "examples",
           "planner", "verify", "self_consistency", "tool_budget"}
VOCAB = {"error_spike", "latency_spike", "cost_blowup", "quality_drift", "infinite_loop",
         "tool_failure", "pii_leak", "prompt_injection", "fabrication", "arithmetic_error", "tool_overuse"}
ILLEGAL = [r"observathon_sim\._", r"observathon_score", r"open\(\s*['\"].*instructor", r"__import__",
           r"\bsocket\b", r"urllib", r"requests\."]
PROMPT_MAX = 3000


def _scan_prompt(text, label):
    assert len(text) <= PROMPT_MAX, f"{label} too long ({len(text)} > {PROMPT_MAX})"
    bigs = {re.sub(r'[.,\s]', '', m) for m in re.findall(r"\d[\d.,]{5,}\d", text)}
    bigs = {b for b in bigs if b.isdigit() and int(b) >= 1_000_000}
    assert len(bigs) < 4, f"{label} looks like a hardcoded price/answer table"
    assert not re.search(r"\b(?:pub|prv|prac)-\d{2,}\b", text), f"{label} references question IDs"


def main(sol="solution"):
    ok = True
    try:
        c = json.load(open(f"{sol}/config.json", encoding="utf-8"))
        bad = set(c) - ALLOWED
        print("[PASS] config.json" if not bad else f"[FAIL] config.json unknown keys: {bad}")
        ok &= not bad
    except Exception as e:
        print(f"[FAIL] config.json: {e}"); ok = False
    try:
        src = open(f"{sol}/wrapper.py", encoding="utf-8").read()
        bad = [p for p in ILLEGAL if re.search(p, src)]
        has = "def mitigate" in src
        print("[PASS] wrapper.py" if (has and not bad) else f"[FAIL] wrapper.py mitigate={has} illegal={bad}")
        ok &= has and not bad
    except Exception as e:
        print(f"[FAIL] wrapper.py: {e}"); ok = False
    for fn, label in [("prompt.txt", "prompt.txt"), ("examples.json", "examples.json")]:
        p = f"{sol}/{fn}"
        if not os.path.exists(p):
            print(f"[ ok ] {label} absent ({'write one!' if fn=='prompt.txt' else 'optional'})")
            continue
        try:
            txt = open(p, encoding="utf-8").read() if fn.endswith(".txt") else \
                json.dumps(json.load(open(p, encoding="utf-8")), ensure_ascii=False)
            _scan_prompt(txt, label)
            print(f"[PASS] {label}")
        except Exception as e:
            print(f"[FAIL] {label}: {e}"); ok = False
    try:
        f = json.load(open(f"{sol}/findings.json", encoding="utf-8"))
        items = f.get("findings", [])
        good = items and all(i.get("fault_class") in VOCAB and i.get("evidence") for i in items)
        print(f"[PASS] findings.json ({len(items)})" if good else "[FAIL] findings.json: need >=1 finding w/ class+evidence")
        ok &= bool(good)
    except Exception as e:
        print(f"[FAIL] findings.json: {e}"); ok = False
    print("\nREADY to run the scorer + push." if ok else "\nFIX the above before submitting.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "solution")

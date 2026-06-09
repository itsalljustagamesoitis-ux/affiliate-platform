"""cost_logger.py — append per-run Haiku cost records to a persistent JSONL log.

Usage:
    from tools.cost_logger import log_haiku_run
    log_haiku_run(site="strengthmill", script="generate-product-pros-cons",
                  input_tokens=12000, output_tokens=3400)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Haiku 4.5 pricing (USD per million tokens, as of 2025)
HAIKU_INPUT_RATE  = 0.80   # $/M input tokens
HAIKU_OUTPUT_RATE = 4.00   # $/M output tokens

_LOG_PATH = Path.home() / "affiliate-platform" / "logs" / "haiku_cost.jsonl"


def log_haiku_run(
    site: str,
    script: str,
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-haiku-4-5-20251001",
    input_rate: float = HAIKU_INPUT_RATE,
    output_rate: float = HAIKU_OUTPUT_RATE,
) -> float:
    """Append a cost record and return the total cost in USD."""
    cost_usd = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
    record = {
        "ts":            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site":          site,
        "script":        script,
        "model":         model,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cost_usd":      round(cost_usd, 6),
    }
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return cost_usd

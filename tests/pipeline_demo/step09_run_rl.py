from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_jsonl, log_path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step09_rl")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def score_token(features: Dict[str, Any]) -> float:
    score = 0.0
    kal = features.get("kalman") or {}
    jd = features.get("jumpdiff") or {}
    rb = features.get("rbergomi") or {}
    if kal:
        score += 0.5 * float(kal.get("kalman_last") or 0.0)
    if jd:
        score += 1.0 * float(jd.get("mean_return") or 0.0)
        score -= 0.3 * float(jd.get("std_return") or 0.0)
    if rb:
        score -= 0.2 * abs(float(rb.get("rough_skew") or 0.0))
    return score


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simple RL-style scoring and emit trading orders.")
    parser.add_argument("--input", type=Path, default=log_path("step08_combined_features.log"))
    parser.add_argument("--output", type=Path, default=log_path("step09_orders.log"))
    args = parser.parse_args()

    logger = setup_logger()
    combined = load_jsonl(args.input)
    if not combined:
        logger.warning("No combined features at %s", args.input)
        return

    orders: List[Dict[str, Any]] = []
    for feat in combined:
        tok = feat.get("token")
        sc = score_token(feat)
        action = "buy" if sc > 0 else "sell" if sc < 0 else "hold"
        orders.append(
            {
                "token": tok,
                "score": sc,
                "action": action,
                "size": 1.0,
                "reason": "rule-based RL proxy (no live trading)",
            }
        )

    dump_jsonl(args.output, orders)
    logger.info("Wrote %d orders to %s", len(orders), args.output)


if __name__ == "__main__":
    main()

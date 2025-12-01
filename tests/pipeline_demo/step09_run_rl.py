from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_with_fallback, log_path, ensure_empty


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step09_rl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def decide_action(feat: Dict[str, Any]) -> Dict[str, Any]:
    sentiment = float(feat.get("sentiment_score") or 0.0)
    kal_last = feat.get("kalman_last")
    jump_std = feat.get("jump_std")

    score = sentiment
    if kal_last is not None:
        score += 0.1 * float(kal_last)
    if jump_std is not None:
        score -= 0.2 * float(jump_std)

    if score > 0.1:
        action = "BUY"
    elif score < -0.1:
        action = "SELL"
    else:
        action = "AVOID"

    confidence = min(1.0, max(0.0, abs(score)))
    notional = round(100 * (0.5 + confidence), 2)
    reasoning = f"score={score:.3f} from sentiment/kalman/jump"

    return {
        "token": feat.get("token"),
        "action": action,
        "confidence": confidence,
        "recommended_notional": notional,
        "reasoning": reasoning,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simple RL-style decisioning and emit trading orders.")
    parser.add_argument("--input", type=Path, default=log_path("step08_combined_features.log"))
    parser.add_argument("--output", type=Path, default=log_path("step09_orders.log"))
    args = parser.parse_args()

    logger = setup_logger()
    out_path = args.output
    try:
        combined = load_with_fallback(Path(args.input).name)
        if not combined:
            logger.error("No combined features at %s; leaving output empty.", args.input)
            ensure_empty(out_path)
            return

        orders: List[Dict[str, Any]] = [decide_action(f) for f in combined if f.get("token")]
        dump_jsonl(out_path, orders)
        logger.info("Wrote %d orders to %s", len(orders), out_path)
    except Exception as exc:
        logger.error("ERROR: step09 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

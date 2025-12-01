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
from trade_order_schema import TradeOrder, build_dummy_trade_order


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step09_rl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def decide_action(feat: Dict[str, Any]) -> TradeOrder:
    # Placeholder: build a dummy TradeOrder. In a real RL, map feat to size/side/etc.
    return build_dummy_trade_order()


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

        orders: List[Dict[str, Any]] = []
        for feat in combined:
            if feat.get("token"):
                order = decide_action(feat)
                orders.append(order.to_dict())

        dump_jsonl(out_path, orders)
        logger.info("Wrote %d orders to %s", len(orders), out_path)
    except Exception as exc:
        logger.error("ERROR: step09 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

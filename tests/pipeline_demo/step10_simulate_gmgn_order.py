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
    logger = logging.getLogger("step10_simulate_gmgn")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate GMGN order placement without real execution.")
    parser.add_argument("--input", type=Path, default=log_path("step09_orders.log"))
    parser.add_argument("--output", type=Path, default=log_path("step10_simulated_calls.log"))
    args = parser.parse_args()

    logger = setup_logger()
    orders: List[Dict[str, Any]] = load_jsonl(args.input)
    if not orders:
        logger.error("No orders found at %s", args.input)
        return

    simulated: List[Dict[str, Any]] = []
    for order in orders:
        simulated.append(
            {
                "token": order.get("token"),
                "action": order.get("action"),
                "size": order.get("recommended_notional"),
                "status": "simulated",
                "api_endpoint": "/token/order/simulated",
                "notes": "Dry-run; no live order sent.",
            }
        )

    dump_jsonl(args.output, simulated)
    logger.info("Logged %d simulated API calls to %s", len(simulated), args.output)


if __name__ == "__main__":
    main()

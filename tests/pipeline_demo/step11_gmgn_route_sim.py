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
from trade_order_schema import TradeOrder


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step11_gmgn_route_sim")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def simulate_route(order: TradeOrder) -> Dict[str, Any]:
    base_url = "https://gmgn.ai/defi/router/v1/sol/tx/get_swap_route"
    params = {
        "token_in_address": order.token_in_mint,
        "token_out_address": order.token_out_mint,
        "in_amount": str(order.in_amount_lamports),
        "from_address": order.wallet,
        "slippage": order.max_slippage_pct,
        "swap_mode": order.mode,
        "is_anti_mev": str(order.is_anti_mev).lower(),
        "partner": order.partner,
    }
    return {
        "order_id": order.order_id,
        "simulated_route_url": base_url,
        "simulated_params": params,
        "note": "Simulated route (no live GMGN call).",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate GMGN route inputs from TradeOrder records (no live call).")
    parser.add_argument("--input", type=Path, default=log_path("step09_orders.log"))
    parser.add_argument("--output", type=Path, default=log_path("step11_gmgn_route.log"))
    args = parser.parse_args()

    logger = setup_logger()
    out_path = args.output
    try:
        rows: List[Dict[str, Any]] = load_with_fallback(Path(args.input).name)
        if not rows:
            logger.error("No orders found at %s; leaving output empty.", args.input)
            ensure_empty(out_path)
            return
        simulated: List[Dict[str, Any]] = []
        for row in rows:
            try:
                order = TradeOrder.from_dict(row)
                simulated.append(simulate_route(order))
            except Exception as exc:
                logger.error("Failed to parse order row (%s); skipping.", exc)
        dump_jsonl(out_path, simulated)
        logger.info("Wrote %d simulated GMGN route entries to %s", len(simulated), out_path)
    except Exception as exc:
        logger.error("ERROR: step11 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

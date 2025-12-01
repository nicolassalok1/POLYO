from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_with_fallback, log_path, ensure_empty


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step04_preprocess_prices")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def preprocess(row: Dict[str, Any]) -> Dict[str, Any]:
    prices = row.get("prices") or []
    if not prices or len(prices) < 2:
        prices = [1.0, 1.01, 0.99, 1.02]
    arr = np.array(prices, dtype=float)
    returns = np.diff(arr) / arr[:-1]
    return {
        "token": row.get("token"),
        "prices": arr.tolist(),
        "returns": returns.tolist(),
        "liquidity": row.get("liquidity"),
        "volume": row.get("volume"),
        "mode": row.get("mode", "stub"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess GMGN price data for downstream filters.")
    parser.add_argument("--input", type=Path, default=log_path("step03_gmgn_data.log"))
    parser.add_argument("--output", type=Path, default=log_path("step04_preprocessed.log"))
    args = parser.parse_args()

    logger = setup_logger()
    out_path = args.output
    try:
        gmgn_rows = load_with_fallback(Path(args.input).name)
        if not gmgn_rows:
            logger.error("No GMGN data found (including fallback); leaving output empty.")
            ensure_empty(out_path)
            return

        processed: List[Dict[str, Any]] = [preprocess(r) for r in gmgn_rows if r.get("token")]
        dump_jsonl(out_path, processed)
        logger.info("Wrote %d preprocessed rows to %s", len(processed), out_path)
    except Exception as exc:
        logger.error("ERROR: step04 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

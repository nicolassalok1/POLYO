from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_jsonl, log_path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step03_fetch_gmgn")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def make_stub_gmgn(token: str) -> Dict[str, Any]:
    prices = [round(1 + random.uniform(-0.05, 0.05) + 0.01 * i, 4) for i in range(50)]
    return {
        "token": token,
        "mode": "test",
        "prices": prices,
        "volume": round(random.uniform(1000, 5000), 2),
        "liquidity": round(random.uniform(20000, 80000), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GMGN data for tokens from sentiment output.")
    parser.add_argument("--input", type=Path, default=log_path("step02_sentiment.log"))
    parser.add_argument("--output", type=Path, default=log_path("step03_gmgn_data.log"))
    args = parser.parse_args()

    logger = setup_logger()
    preds = load_jsonl(args.input)
    tokens = sorted({p.get("token") for p in preds if p.get("token")})
    if not tokens:
        logger.warning("No tokens found in %s; exiting.", args.input)
        return

    rows: List[Dict[str, Any]] = []
    for tok in tokens:
        data = make_stub_gmgn(tok)
        data["source"] = "stub_gmgn"
        rows.append(data)
    dump_jsonl(args.output, rows)
    logger.info("Wrote GMGN stub data for %d tokens to %s", len(rows), args.output)


if __name__ == "__main__":
    main()

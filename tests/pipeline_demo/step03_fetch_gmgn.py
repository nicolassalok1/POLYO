from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_jsonl, log_path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step03_fetch_gmgn")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def make_stub_gmgn(token: str) -> Dict[str, Any]:
    base = random.uniform(0.5, 2.0)
    prices = [round(base * (1 + random.uniform(-0.03, 0.03)), 6) for _ in range(60)]
    return {
        "token": token,
        "prices": prices,
        "volume": round(random.uniform(1_000, 10_000), 2),
        "liquidity": round(random.uniform(20_000, 100_000), 2),
        "mode": "stub",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GMGN data for tokens from sentiment output.")
    parser.add_argument("--input", type=Path, default=log_path("step02_sentiment.log"))
    parser.add_argument("--output", type=Path, default=log_path("step03_gmgn_data.log"))
    args = parser.parse_args()

    logger = setup_logger()
    sentiments = load_jsonl(args.input)
    tokens: Set[str] = set()
    for row in sentiments:
        toks = row.get("tokens_mentioned") or []
        tokens.update([t for t in toks if t])
    if not tokens:
        logger.error("No tokens found in %s; exiting.", args.input)
        return

    rows: List[Dict[str, Any]] = []
    for tok in sorted(tokens):
        rows.append(make_stub_gmgn(tok))

    dump_jsonl(args.output, rows)
    logger.info("Wrote GMGN stub data for %d tokens to %s", len(rows), args.output)


if __name__ == "__main__":
    main()

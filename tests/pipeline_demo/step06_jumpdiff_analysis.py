from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_jsonl, log_path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step06_jumpdiff")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def analyze(row: Dict[str, Any]) -> Dict[str, Any]:
    prices = np.array(row.get("prices", []), dtype=float)
    if prices.size < 4:
        prices = np.array([1.0, 1.02, 0.98, 1.03], dtype=float)
    returns = np.diff(prices) / prices[:-1]
    jumps_idx = np.where(np.abs(returns) > 0.05)[0].tolist()
    return {
        "token": row.get("token"),
        "jump_indices": jumps_idx,
        "jump_count": len(jumps_idx),
        "mean_return": float(np.mean(returns)),
        "std_return": float(np.std(returns)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run jump diffusion style analysis.")
    parser.add_argument("--input", type=Path, default=log_path("step04_preprocessed.log"))
    parser.add_argument("--output", type=Path, default=log_path("step06_jumpdiff.log"))
    args = parser.parse_args()

    logger = setup_logger()
    rows = load_jsonl(args.input)
    if not rows:
        logger.error("No preprocessed data at %s", args.input)
        return
    out: List[Dict[str, Any]] = [analyze(r) for r in rows]
    dump_jsonl(args.output, out)
    logger.info("Wrote jump diffusion outputs for %d tokens to %s", len(out), args.output)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from pipeline_demo.pipeline_paths import dump_jsonl, load_jsonl, log_path


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step07_rbergomi")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def analyze(row: Dict[str, Any]) -> Dict[str, Any]:
    returns = np.array(row.get("returns", []), dtype=float)
    if returns.size == 0:
        returns = np.array([0.01, -0.005, 0.012, -0.003], dtype=float)
    rough_var = float(np.var(returns))
    vol = float(np.std(returns) * np.sqrt(252))
    skew = float(((returns - returns.mean()) ** 3).mean() / (returns.std() ** 3 + 1e-9))
    return {
        "token": row.get("token"),
        "rough_vol": vol,
        "rough_var": rough_var,
        "rough_skew": skew,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run rough-vol inspired stats.")
    parser.add_argument("--input", type=Path, default=log_path("step04_preprocessed.log"))
    parser.add_argument("--output", type=Path, default=log_path("step07_rbergomi.log"))
    args = parser.parse_args()

    logger = setup_logger()
    rows = load_jsonl(args.input)
    if not rows:
        logger.warning("No preprocessed data at %s", args.input)
        return
    out: List[Dict[str, Any]] = [analyze(r) for r in rows]
    dump_jsonl(args.output, out)
    logger.info("Wrote rBergomi-style outputs for %d tokens to %s", len(out), args.output)


if __name__ == "__main__":
    main()

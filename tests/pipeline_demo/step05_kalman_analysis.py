from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from pipeline_demo.pipeline_paths import dump_jsonl, load_jsonl, log_path

try:
    from pykalman import KalmanFilter  # type: ignore
except Exception:
    KalmanFilter = None  # type: ignore


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step05_kalman")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def analyze(row: Dict[str, Any]) -> Dict[str, Any]:
    prices = np.array(row.get("prices", []), dtype=float)
    if prices.size < 2:
        prices = np.array([1.0, 1.01, 0.99, 1.02], dtype=float)
    if KalmanFilter:
        kf = KalmanFilter(transition_matrices=[1], observation_matrices=[1], initial_state_mean=prices[0])
        state_means, _ = kf.filter(prices)
        smoothed = state_means.flatten().tolist()
    else:
        smoothed = np.convolve(prices, np.ones(3) / 3, mode="same").tolist()
    return {
        "token": row.get("token"),
        "kalman_smoothed": smoothed,
        "kalman_last": smoothed[-1] if smoothed else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Kalman analysis on preprocessed data.")
    parser.add_argument("--input", type=Path, default=log_path("step04_preprocessed.log"))
    parser.add_argument("--output", type=Path, default=log_path("step05_kalman.log"))
    args = parser.parse_args()

    logger = setup_logger()
    rows = load_jsonl(args.input)
    if not rows:
        logger.warning("No preprocessed data at %s", args.input)
        return
    out: List[Dict[str, Any]] = [analyze(r) for r in rows]
    dump_jsonl(args.output, out)
    logger.info("Wrote Kalman outputs for %d tokens to %s", len(out), args.output)


if __name__ == "__main__":
    main()

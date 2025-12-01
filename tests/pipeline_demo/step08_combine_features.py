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
    logger = logging.getLogger("step08_combine")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine Kalman, jumpdiff, and rough-vol outputs.")
    parser.add_argument("--kalman", type=Path, default=log_path("step05_kalman.log"))
    parser.add_argument("--jumpdiff", type=Path, default=log_path("step06_jumpdiff.log"))
    parser.add_argument("--rbergomi", type=Path, default=log_path("step07_rbergomi.log"))
    parser.add_argument("--output", type=Path, default=log_path("step08_combined_features.log"))
    args = parser.parse_args()

    logger = setup_logger()
    k_rows = {r.get("token"): r for r in load_jsonl(args.kalman)}
    j_rows = {r.get("token"): r for r in load_jsonl(args.jumpdiff)}
    r_rows = {r.get("token"): r for r in load_jsonl(args.rbergomi)}

    tokens = sorted(set(k_rows) | set(j_rows) | set(r_rows))
    combined: List[Dict[str, Any]] = []
    for tok in tokens:
        combined.append(
            {
                "token": tok,
                "kalman": k_rows.get(tok),
                "jumpdiff": j_rows.get(tok),
                "rbergomi": r_rows.get(tok),
            }
        )

    dump_jsonl(args.output, combined)
    logger.info("Combined features for %d tokens into %s", len(combined), args.output)


if __name__ == "__main__":
    main()

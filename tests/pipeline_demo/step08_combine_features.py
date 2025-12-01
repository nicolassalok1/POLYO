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


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step08_combine")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def aggregate_sentiment(sent_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for row in sent_rows:
        toks = row.get("tokens_mentioned") or []
        for tok in toks:
            entry = agg.setdefault(tok, {"sentiment_score": 0.0, "confidence": 0.0, "count": 0})
            entry["sentiment_score"] += float(row.get("sentiment_score", 0.0))
            entry["confidence"] = max(entry["confidence"], float(row.get("confidence", 0.0)))
            entry["count"] += 1
    for tok, entry in agg.items():
        cnt = max(1, entry.pop("count", 1))
        entry["sentiment_score"] = entry["sentiment_score"] / cnt
    return agg


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine Kalman, jumpdiff, rBergomi, and sentiment features.")
    parser.add_argument("--sentiment", type=Path, default=log_path("step02_sentiment.log"))
    parser.add_argument("--kalman", type=Path, default=log_path("step05_kalman.log"))
    parser.add_argument("--jumpdiff", type=Path, default=log_path("step06_jumpdiff.log"))
    parser.add_argument("--rbergomi", type=Path, default=log_path("step07_rbergomi.log"))
    parser.add_argument("--output", type=Path, default=log_path("step08_combined_features.log"))
    args = parser.parse_args()

    logger = setup_logger()
    out_path = args.output
    try:
        sent_rows = load_with_fallback(Path(args.sentiment).name)
        k_rows = {r.get("token"): r for r in load_with_fallback(Path(args.kalman).name)}
        j_rows = {r.get("token"): r for r in load_with_fallback(Path(args.jumpdiff).name)}
        r_rows = {r.get("token"): r for r in load_with_fallback(Path(args.rbergomi).name)}
        sent_map = aggregate_sentiment(sent_rows)

        tokens = sorted(set(sent_map) | set(k_rows) | set(j_rows) | set(r_rows))
        if not tokens:
            logger.error("No features to combine; leaving output empty.")
            ensure_empty(out_path)
            return

        combined: List[Dict[str, Any]] = []
        for tok in tokens:
            s = sent_map.get(tok, {})
            k = k_rows.get(tok, {})
            j = j_rows.get(tok, {})
            r = r_rows.get(tok, {})
            combined.append(
                {
                    "token": tok,
                    "sentiment_score": s.get("sentiment_score"),
                    "sentiment_confidence": s.get("confidence"),
                    "kalman_last": k.get("kalman_last"),
                    "jump_mean": j.get("mean_return"),
                    "jump_std": j.get("std_return"),
                    "jump_count": j.get("jump_count"),
                    "rough_vol": r.get("rough_vol"),
                    "rough_var": r.get("rough_var"),
                    "rough_skew": r.get("rough_skew"),
                }
            )

        dump_jsonl(out_path, combined)
        logger.info("Combined features for %d tokens into %s", len(combined), out_path)
    except Exception as exc:
        logger.error("ERROR: step08 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

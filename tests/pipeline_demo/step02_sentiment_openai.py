from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, load_jsonl, log_path

try:
    from telegram_signal_pipeline import OpenAISentimentClient, TelegramMessage
except Exception:
    OpenAISentimentClient = None  # type: ignore
    TelegramMessage = None  # type: ignore


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step02_sentiment_openai")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def heuristic_sentiment(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preds: List[Dict[str, Any]] = []
    for msg in messages:
        text = msg.get("text", "")
        tokens = []
        for part in text.split():
            cleaned = part.strip("$").upper()
            if cleaned.isalpha() and 2 <= len(cleaned) <= 10:
                tokens.append(cleaned)
        for tok in tokens:
            preds.append(
                {
                    "token": tok,
                    "stance": "buy" if "LONG" in text.upper() or "BUY" in text.upper() else "hold",
                    "confidence": 0.35,
                    "sentiment_score": 0.2,
                    "source": msg.get("channel"),
                    "source_type": msg.get("source_type", "channel"),
                    "reason": "heuristic keyword",
                    "message_excerpt": text[:160],
                }
            )
    return preds


def run_sentiment(messages: List[Dict[str, Any]], logger: logging.Logger) -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAISentimentClient(api_key=api_key) if OpenAISentimentClient else None
    if not client:
        logger.info("OpenAI client unavailable; using heuristic sentiment.")
        return heuristic_sentiment(messages)

    preds: List[Dict[str, Any]] = []
    for msg in messages:
        tmsg = TelegramMessage(
            channel=msg.get("channel", "unknown"),
            message_id=int(msg.get("message_id", 0)),
            text=str(msg.get("text", "")),
            timestamp=msg.get("timestamp"),
            source_type=msg.get("source_type", "channel"),
        )
        try:
            results = client.analyze(tmsg)
            for r in results:
                preds.append(
                    {
                        "token": r.token,
                        "stance": r.stance,
                        "confidence": r.confidence,
                        "sentiment_score": r.sentiment_score,
                        "source": r.source,
                        "source_type": r.source_type,
                        "reason": r.reason,
                        "message_excerpt": r.message_excerpt,
                    }
                )
        except Exception as exc:
            logger.warning("OpenAI analyze failed for message %s (%s); using heuristic.", msg.get("message_id"), exc)
            preds.extend(heuristic_sentiment([msg]))
    return preds


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sentiment on messages and log token predictions.")
    parser.add_argument("--input", type=Path, default=log_path("step01_telegram_messages.log"))
    parser.add_argument("--output", type=Path, default=log_path("step02_sentiment.log"))
    args = parser.parse_args()

    logger = setup_logger()
    messages = load_jsonl(args.input)
    if not messages:
        logger.warning("No input messages found at %s; exiting.", args.input)
        return

    preds = run_sentiment(messages, logger)
    dump_jsonl(args.output, preds)
    logger.info("Wrote %d sentiment rows to %s", len(preds), args.output)


if __name__ == "__main__":
    main()

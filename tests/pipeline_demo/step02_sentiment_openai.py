from __future__ import annotations

import argparse
import logging
import os
import re
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

TOKEN_RE = re.compile(r"\$?[A-Za-z]{2,10}")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step02_sentiment_openai")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def extract_tokens(text: str) -> List[str]:
    tokens = set()
    for m in TOKEN_RE.findall(text or ""):
        cleaned = m.replace("$", "").upper()
        if cleaned and cleaned.isalpha() and cleaned not in {"USD", "USDT", "USDC"}:
            tokens.add(cleaned)
    return list(tokens)


def heuristic_sentiment(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for msg in messages:
        text = str(msg.get("text", ""))
        tokens = extract_tokens(text)
        sentiment = "positive" if any(k in text.lower() for k in ["long", "buy", "bull"]) else "neutral"
        sentiment_score = 0.3 if sentiment == "positive" else 0.0
        confidence = 0.35
        reasoning = "heuristic keywords" if sentiment == "positive" else "no strong signal"
        rows.append(
            {
                "message_id": msg.get("message_id"),
                "channel": msg.get("channel"),
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "tokens_mentioned": tokens,
                "confidence": confidence,
                "reasoning": reasoning,
                "message_excerpt": text[:200],
            }
        )
    return rows


def run_sentiment(messages: List[Dict[str, Any]], logger: logging.Logger) -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAISentimentClient(api_key=api_key) if OpenAISentimentClient else None
    if not client:
        logger.info("OpenAI client unavailable; using heuristic sentiment.")
        return heuristic_sentiment(messages)

    outputs: List[Dict[str, Any]] = []
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
            tokens = [getattr(r, "token", None) for r in results if getattr(r, "token", None)]
            sentiment_score = sum(getattr(r, "sentiment_score", 0.0) for r in results)
            confidence = max((getattr(r, "confidence", 0.0) for r in results), default=0.0)
            sentiment = "positive" if sentiment_score > 0 else "negative" if sentiment_score < 0 else "neutral"
            reasoning = "; ".join([getattr(r, "reason", "") for r in results if getattr(r, "reason", "")]) or "model"
            outputs.append(
                {
                    "message_id": msg.get("message_id"),
                    "channel": msg.get("channel"),
                    "sentiment": sentiment,
                    "sentiment_score": sentiment_score,
                    "tokens_mentioned": tokens,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "message_excerpt": tmsg.text[:200],
                }
            )
        except Exception as exc:
            logger.error("ERROR: OpenAI analyze failed for message %s (%s); using heuristic.", msg.get("message_id"), exc)
            outputs.extend(heuristic_sentiment([msg]))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sentiment on messages and log results.")
    parser.add_argument("--input", type=Path, default=log_path("step01_telegram_messages.log"))
    parser.add_argument("--output", type=Path, default=log_path("step02_sentiment.log"))
    args = parser.parse_args()

    logger = setup_logger()
    messages = load_jsonl(args.input)
    if not messages:
        logger.error("No input messages found at %s; exiting.", args.input)
        return

    preds = run_sentiment(messages, logger)
    dump_jsonl(args.output, preds)
    logger.info("Wrote %d sentiment rows to %s", len(preds), args.output)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_paths import dump_jsonl, log_path, ensure_empty

try:
    from telegram_signal_pipeline import TelegramScraperAdapter
except Exception:
    TelegramScraperAdapter = None  # type: ignore


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("step01_fetch_telegram")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def fetch_messages(channel: str, limit: int, export_root: Path | None, logger: logging.Logger) -> List[Dict[str, Any]]:
    channel = channel.lstrip("@").strip()
    if TelegramScraperAdapter:
        try:
            msgs = TelegramScraperAdapter(export_root=export_root).fetch_messages([channel], limit=limit)
            if msgs:
                return [
                    {
                        "channel": m.channel,
                        "message_id": m.message_id,
                        "text": m.text,
                        "timestamp": m.timestamp,
                        "sender": getattr(m, "sender", None) or getattr(m, "source", None) or m.channel,
                        "source_type": getattr(m, "source_type", "channel"),
                    }
                    for m in msgs
                ]
        except Exception as exc:
            logger.error("ERROR: fetch failed for %s (%s).", channel or "<empty>", exc)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Telegram messages and log them to a JSONL file.")
    parser.add_argument("--channel", required=True, help="Telegram channel handle or t.me link.")
    parser.add_argument("--limit", type=int, default=100, help="Max messages to fetch.")
    parser.add_argument("--export-root", type=Path, default=None, help="Path to telegram-scraper exports.")
    args = parser.parse_args()

    logger = setup_logger()
    out_path = log_path("step01_telegram_messages.log")

    try:
        messages = fetch_messages(args.channel, args.limit, args.export_root, logger)
        if not messages:
            ensure_empty(out_path)
            logger.warning("No messages captured; log left empty.")
        else:
            dump_jsonl(out_path, messages)
            logger.info("Wrote %d messages to %s", len(messages), out_path)
    except Exception as exc:
        logger.error("ERROR: step01 failed (%s). Leaving log empty.", exc)
        ensure_empty(out_path)


if __name__ == "__main__":
    main()

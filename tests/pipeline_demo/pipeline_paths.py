from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Dict

LOG_DIR = Path(__file__).resolve().parent / "pipeline_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_path(name: str) -> Path:
    """Return a path inside the shared pipeline log directory."""
    return LOG_DIR / name


def fallback_path(log_name: str) -> Path:
    """
    Return the path to a constant fallback file for a given log.
    Example: step01_telegram_messages.log -> step01_telegram_messages_fallback.jsonl
    """
    stem = Path(log_name).stem
    return Path(__file__).resolve().parent / f"{stem}_fallback.jsonl"


def dump_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Write iterable of dicts to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file; returns empty list if missing."""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def ensure_empty(path: Path) -> None:
    """Truncate a file to empty (create if missing)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def load_with_fallback(log_name: str) -> List[Dict[str, Any]]:
    """
    Load a log by name from LOG_DIR; if empty or missing, load its fallback file.
    """
    primary = log_path(log_name)
    data = load_jsonl(primary)
    if data:
        return data
    fb = fallback_path(log_name)
    return load_jsonl(fb)


def clear_logs() -> None:
    """Empty all .log files under the shared log directory."""
    for log_file in LOG_DIR.glob("*.log"):
        ensure_empty(log_file)

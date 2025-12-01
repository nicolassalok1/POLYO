from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Dict


LOG_DIR = Path(__file__).resolve().parent / "pipeline_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_path(name: str) -> Path:
    """Return a path inside the shared pipeline log directory."""
    return LOG_DIR / name


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

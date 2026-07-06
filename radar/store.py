"""Hourly history archive on the filesystem (committed to the data branch).

No database: each run writes data/history/YYYY-MM-DD/HH.json (UTC), and
prune_history drops day directories older than the retention window.
"""
from __future__ import annotations

import dataclasses
import json
import re
import time
from pathlib import Path

from radar.models import FundingSnapshot

_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def write_history(
    snapshots: list[FundingSnapshot], *, root: str = "data", now: float | None = None
) -> Path:
    """Write snapshots to data/history/<date>/<hour>.json (UTC), overwriting."""
    ts = time.gmtime(time.time() if now is None else now)
    day = time.strftime("%Y-%m-%d", ts)
    hour = time.strftime("%H", ts)
    out_dir = Path(root) / "history" / day
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{hour}.json"
    payload = {
        "captured_at": int(time.time() if now is None else now),
        "snapshots": [dataclasses.asdict(s) for s in snapshots],
    }
    path.write_text(json.dumps(payload, indent=1))
    return path


def load_history_window(*, root: str = "data", days: int = 7, now: float | None = None) -> dict:
    """Aggregate recent hourly archives into {symbol: [{"t", "rates": {venue: apr}}]}.

    Points are sorted ascending by capture time; each point maps venue -> APR
    for that symbol at that hour. Used by the site generator's coin pages.
    """
    history = Path(root) / "history"
    if not history.exists():
        return {}
    cutoff = (time.time() if now is None else now) - days * 86400
    cutoff_day = time.strftime("%Y-%m-%d", time.gmtime(cutoff))

    points: dict[str, dict[int, dict[str, float]]] = {}
    for day_dir in sorted(history.iterdir()):
        if not day_dir.is_dir() or not _DATE_DIR.match(day_dir.name) or day_dir.name < cutoff_day:
            continue
        for hour_file in sorted(day_dir.glob("*.json")):
            try:
                data = json.loads(hour_file.read_text())
            except (ValueError, OSError):
                continue
            t = int(data.get("captured_at", 0))
            for snap in data.get("snapshots", []):
                points.setdefault(snap["symbol"], {}).setdefault(t, {})[snap["venue"]] = snap["apr"]

    result: dict[str, list[dict]] = {}
    for symbol, by_t in points.items():
        result[symbol] = [{"t": t, "rates": by_t[t]} for t in sorted(by_t)]
    return result


def prune_history(*, root: str = "data", keep_days: int = 90, now: float | None = None) -> int:
    """Delete day directories older than keep_days. Returns count removed."""
    history = Path(root) / "history"
    if not history.exists():
        return 0
    cutoff = (time.time() if now is None else now) - keep_days * 86400
    cutoff_day = time.strftime("%Y-%m-%d", time.gmtime(cutoff))
    removed = 0
    for child in history.iterdir():
        if not child.is_dir() or not _DATE_DIR.match(child.name):
            continue
        if child.name < cutoff_day:
            for f in child.iterdir():
                f.unlink()
            child.rmdir()
            removed += 1
    return removed

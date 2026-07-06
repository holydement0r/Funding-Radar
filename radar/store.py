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
from radar.paper import ClosedTrade, PaperPosition

_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_CLOSED_TRADES = 500  # keep the track record bounded


def load_paper(root: str = "data") -> tuple[list[PaperPosition], list[ClosedTrade]]:
    """Load open paper positions and closed track record from data/paper/."""
    paper = Path(root) / "paper"
    open_path = paper / "open.json"
    closed_path = paper / "closed.json"
    open_now = [PaperPosition(**d) for d in _read_list(open_path)]
    closed = [ClosedTrade(**d) for d in _read_list(closed_path)]
    return open_now, closed


def save_paper(
    open_now: list[PaperPosition], closed: list[ClosedTrade], root: str = "data"
) -> None:
    """Persist open positions and (bounded, newest-last) closed trades."""
    paper = Path(root) / "paper"
    paper.mkdir(parents=True, exist_ok=True)
    (paper / "open.json").write_text(
        json.dumps([dataclasses.asdict(p) for p in open_now], indent=1)
    )
    trimmed = closed[-MAX_CLOSED_TRADES:]
    (paper / "closed.json").write_text(
        json.dumps([dataclasses.asdict(c) for c in trimmed], indent=1)
    )


def _read_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return []


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

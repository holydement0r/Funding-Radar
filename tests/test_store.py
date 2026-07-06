import json
import time
from pathlib import Path

from radar.models import FundingSnapshot
from radar.store import prune_history, write_history


def snap(venue="hyperliquid", symbol="BTC"):
    return FundingSnapshot(
        venue=venue, symbol=symbol, rate=0.0001, interval_hours=8.0,
        apr=0.1095, mark_price=100.0, open_interest_usd=None,
        next_funding_ts=None, fetched_at=1783326670,
    )


def test_write_history_lands_at_hour_path(tmp_path):
    path = write_history([snap()], root=str(tmp_path), now=1783326670)
    # 1783326670 -> 2026-07-06 16:31 UTC
    assert path.exists()
    assert path.parent.parent.name == "history"
    parts = path.relative_to(tmp_path / "history").parts
    assert len(parts) == 2  # YYYY-MM-DD/HH.json
    assert parts[1].endswith(".json")
    data = json.loads(path.read_text())
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["venue"] == "hyperliquid"


def test_second_write_same_hour_overwrites(tmp_path):
    now = 1783326670
    write_history([snap()], root=str(tmp_path), now=now)
    path = write_history([snap(), snap(symbol="ETH")], root=str(tmp_path), now=now)
    data = json.loads(path.read_text())
    assert len(data["snapshots"]) == 2


def test_prune_deletes_old_day_dirs_only(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    # today and 30d ago survive; 100d ago pruned
    now = time.time()
    keep_recent = time.strftime("%Y-%m-%d", time.gmtime(now))
    keep_edge = time.strftime("%Y-%m-%d", time.gmtime(now - 30 * 86400))
    drop_old = time.strftime("%Y-%m-%d", time.gmtime(now - 100 * 86400))
    for d in (keep_recent, keep_edge, drop_old):
        (history / d).mkdir()
        (history / d / "00.json").write_text("{}")
    removed = prune_history(root=str(tmp_path), keep_days=90, now=now)
    assert removed == 1
    assert (history / keep_recent).exists()
    assert (history / keep_edge).exists()
    assert not (history / drop_old).exists()


def test_prune_ignores_non_date_dirs(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    (history / "not-a-date").mkdir()
    (history / "not-a-date" / "x.json").write_text("{}")
    removed = prune_history(root=str(tmp_path), keep_days=90, now=time.time())
    assert removed == 0
    assert (history / "not-a-date").exists()


def test_prune_missing_history_dir_is_noop(tmp_path):
    assert prune_history(root=str(tmp_path), keep_days=90, now=time.time()) == 0

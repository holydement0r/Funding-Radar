import json
from pathlib import Path

from radar.models import FundingSnapshot
from radar.run import main
from radar.venues.base import VenueAdapter


class BrokenAdapter(VenueAdapter):
    name = "broken"

    def fetch(self):
        raise RuntimeError("down")


class TinyAdapter(VenueAdapter):
    name = "tiny"

    def fetch(self):
        return [FundingSnapshot(
            venue="tiny", symbol="BTC", rate=0.0001, interval_hours=8.0,
            apr=0.1095, mark_price=1.0, open_interest_usd=None,
            next_funding_ts=None, fetched_at=1,
        )]


def test_dry_run_writes_latest_and_state(tmp_path):
    code = main(["--dry-run", "--data-dir", str(tmp_path)])
    assert code == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert len(latest["snapshots"]) >= 40  # four fixture venues
    assert "opportunities" in latest
    assert "generated_at" in latest
    assert latest["failed_venues"] == []
    assert (tmp_path / "alert_state.json").exists()


def test_dry_run_snapshot_shape(tmp_path):
    main(["--dry-run", "--data-dir", str(tmp_path)])
    latest = json.loads((tmp_path / "latest.json").read_text())
    snap = latest["snapshots"][0]
    for field in ("venue", "symbol", "rate", "interval_hours", "apr", "fetched_at"):
        assert field in snap
    venues = {s["venue"] for s in latest["snapshots"]}
    assert venues == {"hyperliquid", "aster", "paradex", "lighter"}


def test_all_failed_keeps_old_latest_and_exits_1(tmp_path):
    sentinel = {"generated_at": 1, "snapshots": [{"old": True}],
                "failed_venues": [], "opportunities": []}
    (tmp_path / "latest.json").write_text(json.dumps(sentinel))
    code = main(["--skip-telegram", "--data-dir", str(tmp_path)],
                adapters=[BrokenAdapter()])
    assert code == 1
    assert json.loads((tmp_path / "latest.json").read_text()) == sentinel


def test_partial_failure_still_writes(tmp_path):
    code = main(["--skip-telegram", "--data-dir", str(tmp_path)],
                adapters=[TinyAdapter(), BrokenAdapter()])
    assert code == 0
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["failed_venues"] == ["broken"]
    assert len(latest["snapshots"]) == 1

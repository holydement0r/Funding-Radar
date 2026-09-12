"""v1 and v2 paper records must stay separated and separately reported."""
from radar.arb import find_opportunities
from radar.models import ArbOpportunity, FundingSnapshot
from radar.paper import (LEGACY_VERSION, STRATEGY_VERSION, ClosedTrade, PaperPosition,
                         open_positions, summarize_by_version, update_positions)
from radar.store import MAX_CLOSED_TRADES, load_paper, save_paper

DAY = 86400


def _opp(symbol="BTC"):
    return ArbOpportunity(symbol=symbol, long_venue="a", short_venue="b",
                          long_apr=0.0, short_apr=0.2, spread_apr=0.2,
                          net_apr=0.2, min_oi_usd=1e6)


def _pos(version, entry_ts=0):
    return PaperPosition(symbol="BTC", long_venue="a", short_venue="b",
                         entry_ts=entry_ts, predicted_net_apr=0.2,
                         round_trip_fees=0.001, accumulated_return=0.0,
                         last_update_ts=entry_ts, version=version)


def _snap(venue, apr):
    return FundingSnapshot(venue=venue, symbol="BTC", rate=0.0, interval_hours=1.0,
                           apr=apr, mark_price=1.0, open_interest_usd=1e6,
                           next_funding_ts=None, fetched_at=0)


def test_new_positions_carry_the_current_version():
    opened = open_positions([_opp()], [], now=0, fees={}, max_open=10)
    assert opened[0].version == STRATEGY_VERSION


def test_legacy_positions_close_on_the_legacy_horizon():
    """A v1 position must not be re-horizoned to 21 days mid-flight."""
    snaps = [_snap("a", 0.0), _snap("b", 0.2)]
    v1, v2 = _pos(LEGACY_VERSION), _pos(STRATEGY_VERSION)
    still_open, closed = update_positions(
        [v1, v2], snaps, now=int(8 * DAY), holding_days=21.0, legacy_holding_days=7.0)
    assert [c.version for c in closed] == [LEGACY_VERSION]
    assert [p.version for p in still_open] == [STRATEGY_VERSION]


def test_closed_trade_inherits_the_position_version():
    snaps = [_snap("a", 0.0), _snap("b", 0.2)]
    _, closed = update_positions([_pos(LEGACY_VERSION)], snaps, now=int(8 * DAY),
                                 holding_days=21.0, legacy_holding_days=7.0)
    assert closed[0].version == LEGACY_VERSION


def test_summary_is_reported_per_version():
    closed = [
        ClosedTrade("BTC", "a", "b", 0, DAY, 0.20, -0.05, LEGACY_VERSION),
        ClosedTrade("ETH", "a", "b", 0, DAY, 0.20, -0.03, LEGACY_VERSION),
        ClosedTrade("SOL", "a", "b", 0, DAY, 0.10, +0.04, STRATEGY_VERSION),
    ]
    by_version = summarize_by_version(closed)
    assert by_version[LEGACY_VERSION]["count"] == 2
    assert by_version[LEGACY_VERSION]["avg_realized_apr"] < 0
    assert by_version[STRATEGY_VERSION]["count"] == 1
    assert by_version[STRATEGY_VERSION]["avg_realized_apr"] > 0


def test_a_flood_of_v2_trades_cannot_evict_the_v1_record(tmp_path):
    v1 = [ClosedTrade("BTC", "a", "b", 0, DAY, 0.2, -0.05, LEGACY_VERSION)
          for _ in range(10)]
    v2 = [ClosedTrade("ETH", "a", "b", 0, DAY, 0.1, 0.03, STRATEGY_VERSION)
          for _ in range(MAX_CLOSED_TRADES + 50)]
    save_paper([], v1 + v2, root=str(tmp_path))
    _, reloaded = load_paper(root=str(tmp_path))
    counts = {v: s["count"] for v, s in summarize_by_version(reloaded).items()}
    assert counts[LEGACY_VERSION] == 10
    assert counts[STRATEGY_VERSION] == MAX_CLOSED_TRADES


def test_records_written_before_versioning_load_as_v1(tmp_path):
    """Old closed.json rows have no `version` key at all."""
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "closed.json").write_text(
        '[{"symbol":"BTC","long_venue":"a","short_venue":"b","entry_ts":0,'
        '"exit_ts":86400,"predicted_net_apr":0.2,"realized_net_apr":-0.04}]')
    _, closed = load_paper(root=str(tmp_path))
    assert closed[0].version == LEGACY_VERSION

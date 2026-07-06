import pytest

from radar.models import ArbOpportunity, FundingSnapshot
from radar.paper import (
    PaperPosition,
    open_positions,
    summarize,
    update_positions,
)

DAY = 86400


def opp(symbol="BTC", long_v="lighter", short_v="hyperliquid", net=0.20):
    return ArbOpportunity(
        symbol=symbol, long_venue=long_v, short_venue=short_v,
        long_apr=0.0, short_apr=net, spread_apr=net, net_apr=net,
        min_oi_usd=1_000_000.0,
    )


def snap(venue, symbol="BTC", apr=0.10):
    return FundingSnapshot(
        venue=venue, symbol=symbol, rate=apr / 1095, interval_hours=8.0,
        apr=apr, mark_price=100.0, open_interest_usd=1_000_000.0,
        next_funding_ts=None, fetched_at=0,
    )


FEES = {"hyperliquid": 0.0, "lighter": 0.0}


class TestOpen:
    def test_opens_new_position(self):
        out = open_positions([opp(net=0.20)], [], now=1000, fees=FEES, max_open=10)
        assert len(out) == 1
        p = out[0]
        assert p.symbol == "BTC"
        assert p.short_venue == "hyperliquid"
        assert p.predicted_net_apr == pytest.approx(0.20)
        assert p.entry_ts == 1000
        assert p.accumulated_return == 0.0

    def test_no_duplicate_of_open_position(self):
        first = open_positions([opp()], [], now=1000, fees=FEES, max_open=10)
        again = open_positions([opp()], first, now=2000, fees=FEES, max_open=10)
        assert len(again) == 1
        assert again[0].entry_ts == 1000  # unchanged

    def test_respects_max_open(self):
        opps = [opp(symbol=s) for s in ("BTC", "ETH", "SOL")]
        out = open_positions(opps, [], now=1000, fees=FEES, max_open=2)
        assert len(out) == 2

    def test_records_round_trip_fees(self):
        fees = {"hyperliquid": 0.0005, "lighter": 0.0003}
        out = open_positions([opp()], [], now=1000, fees=fees, max_open=10)
        assert out[0].round_trip_fees == pytest.approx(2 * (0.0005 + 0.0003))


class TestUpdate:
    def test_accrues_funding_over_time(self):
        pos = PaperPosition(
            symbol="BTC", long_venue="lighter", short_venue="hyperliquid",
            entry_ts=0, predicted_net_apr=0.20, round_trip_fees=0.0,
            accumulated_return=0.0, last_update_ts=0,
        )
        snaps = [snap("hyperliquid", apr=0.30), snap("lighter", apr=0.10)]
        # 1 day later, spread 0.20 annualized -> 0.20 * (1/365) accrued
        still_open, closed = update_positions([pos], snaps, now=DAY, holding_days=7.0)
        assert closed == []
        assert still_open[0].accumulated_return == pytest.approx(0.20 * (1 / 365), rel=1e-3)
        assert still_open[0].last_update_ts == DAY

    def test_closes_after_holding_period(self):
        pos = PaperPosition(
            symbol="BTC", long_venue="lighter", short_venue="hyperliquid",
            entry_ts=0, predicted_net_apr=0.20, round_trip_fees=0.001,
            accumulated_return=0.20 * (6 / 365), last_update_ts=6 * DAY,
        )
        snaps = [snap("hyperliquid", apr=0.20), snap("lighter", apr=0.0)]
        still_open, closed = update_positions([pos], snaps, now=7 * DAY, holding_days=7.0)
        assert still_open == []
        assert len(closed) == 1
        c = closed[0]
        assert c.symbol == "BTC"
        assert c.exit_ts == 7 * DAY
        # realized ~ accrued (7 days of 0.20 apr) minus fees, annualized back
        assert c.realized_net_apr < c.predicted_net_apr  # fees drag it down
        assert c.realized_net_apr > 0

    def test_missing_leg_skips_accrual_but_advances(self):
        pos = PaperPosition(
            symbol="BTC", long_venue="lighter", short_venue="hyperliquid",
            entry_ts=0, predicted_net_apr=0.20, round_trip_fees=0.0,
            accumulated_return=0.05, last_update_ts=0,
        )
        snaps = [snap("hyperliquid", apr=0.30)]  # lighter missing
        still_open, closed = update_positions([pos], snaps, now=DAY, holding_days=7.0)
        assert still_open[0].accumulated_return == pytest.approx(0.05)  # unchanged
        assert still_open[0].last_update_ts == DAY

    def test_negative_spread_reduces_return(self):
        # funding flipped: short leg now lower than long -> realized goes negative
        pos = PaperPosition(
            symbol="BTC", long_venue="lighter", short_venue="hyperliquid",
            entry_ts=0, predicted_net_apr=0.20, round_trip_fees=0.0,
            accumulated_return=0.0, last_update_ts=0,
        )
        snaps = [snap("hyperliquid", apr=0.0), snap("lighter", apr=0.40)]
        still_open, _ = update_positions([pos], snaps, now=DAY, holding_days=7.0)
        assert still_open[0].accumulated_return < 0


class TestSummarize:
    def test_empty(self):
        s = summarize([])
        assert s["count"] == 0

    def test_stats(self):
        from radar.paper import ClosedTrade
        closed = [
            ClosedTrade("BTC", "lighter", "hyperliquid", 0, 7 * DAY, 0.20, 0.15),
            ClosedTrade("ETH", "lighter", "hyperliquid", 0, 7 * DAY, 0.30, -0.05),
        ]
        s = summarize(closed)
        assert s["count"] == 2
        assert s["avg_predicted_apr"] == pytest.approx(0.25)
        assert s["avg_realized_apr"] == pytest.approx(0.05)
        assert s["win_rate"] == pytest.approx(0.5)  # 1 of 2 positive

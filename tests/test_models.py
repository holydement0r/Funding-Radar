import dataclasses

import pytest

from radar.models import ArbOpportunity, FundingSnapshot


def make_snapshot(**overrides):
    base = dict(
        venue="hyperliquid",
        symbol="BTC",
        rate=0.0000125,
        interval_hours=1.0,
        apr=0.1095,
        mark_price=100000.0,
        open_interest_usd=2_000_000.0,
        next_funding_ts=1783330000,
        fetched_at=1783326670,
    )
    base.update(overrides)
    return FundingSnapshot(**base)


def test_funding_snapshot_fields():
    snap = make_snapshot()
    assert snap.venue == "hyperliquid"
    assert snap.symbol == "BTC"
    assert snap.rate == pytest.approx(0.0000125)
    assert snap.interval_hours == 1.0


def test_funding_snapshot_optional_fields_accept_none():
    snap = make_snapshot(mark_price=None, open_interest_usd=None, next_funding_ts=None)
    assert snap.mark_price is None
    assert snap.open_interest_usd is None
    assert snap.next_funding_ts is None


def test_funding_snapshot_is_frozen():
    snap = make_snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.rate = 1.0


def test_arb_opportunity_fields():
    opp = ArbOpportunity(
        symbol="BTC",
        long_venue="paradex",
        short_venue="hyperliquid",
        long_apr=-0.05,
        short_apr=0.30,
        spread_apr=0.35,
        net_apr=0.20,
        min_oi_usd=1_000_000.0,
    )
    assert opp.short_apr > opp.long_apr
    assert opp.spread_apr == pytest.approx(0.35)


def test_arb_opportunity_is_frozen():
    opp = ArbOpportunity(
        symbol="BTC",
        long_venue="a",
        short_venue="b",
        long_apr=0.0,
        short_apr=0.1,
        spread_apr=0.1,
        net_apr=0.05,
        min_oi_usd=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        opp.net_apr = 9.9

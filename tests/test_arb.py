import pytest

from radar.arb import find_opportunities
from radar.fees import TAKER_FEES
from radar.models import FundingSnapshot


def snap(venue, symbol="BTC", apr=0.1, oi=5_000_000.0):
    return FundingSnapshot(
        venue=venue, symbol=symbol, rate=apr / 1095, interval_hours=8.0,
        apr=apr, mark_price=100.0, open_interest_usd=oi,
        next_funding_ts=None, fetched_at=1783326670,
    )


ZERO_FEES = {"a": 0.0, "b": 0.0, "c": 0.0}


class TestDirection:
    def test_short_high_long_low(self):
        opps = find_opportunities(
            [snap("a", apr=0.5), snap("b", apr=-0.1)], fees=ZERO_FEES
        )
        assert len(opps) == 1
        opp = opps[0]
        assert opp.short_venue == "a"
        assert opp.long_venue == "b"
        assert opp.spread_apr == pytest.approx(0.6)
        assert opp.net_apr == pytest.approx(0.6)  # zero fees

    def test_same_venue_never_paired(self):
        opps = find_opportunities(
            [snap("a", apr=0.5), snap("a", apr=-0.1)], fees=ZERO_FEES
        )
        assert opps == []

    def test_symbols_never_mixed(self):
        opps = find_opportunities(
            [snap("a", "BTC", apr=0.5), snap("b", "ETH", apr=-0.1)], fees=ZERO_FEES
        )
        assert opps == []


class TestFees:
    def test_fee_deduction_exact(self):
        # round trip both legs: 2 * (fee_a + fee_b), annualized over holding_days
        fees = {"a": 0.0005, "b": 0.0003}
        opps = find_opportunities(
            [snap("a", apr=0.5), snap("b", apr=0.0)],
            fees=fees, holding_days=7.0, min_net_apr=-10.0,
        )
        cost = 2 * (0.0005 + 0.0003) * (365 / 7.0)
        assert opps[0].net_apr == pytest.approx(0.5 - cost)

    def test_unknown_venue_uses_default_fee(self):
        opps = find_opportunities(
            [snap("mystery1", apr=3.0), snap("mystery2", apr=0.0)],
            fees={}, min_net_apr=-10.0,
        )
        assert len(opps) == 1
        assert opps[0].net_apr < opps[0].spread_apr  # some default cost applied

    def test_default_fees_table_has_all_p0_venues(self):
        for venue in ("hyperliquid", "aster", "paradex", "lighter"):
            assert venue in TAKER_FEES


class TestFilters:
    def test_min_net_apr_filters(self):
        opps = find_opportunities(
            [snap("a", apr=0.10), snap("b", apr=0.0)],
            fees=ZERO_FEES, min_net_apr=0.15,
        )
        assert opps == []

    def test_numeric_oi_below_threshold_dropped(self):
        opps = find_opportunities(
            [snap("a", apr=0.5, oi=100_000.0), snap("b", apr=0.0)],
            fees=ZERO_FEES, min_oi_usd=500_000.0,
        )
        assert opps == []

    def test_none_oi_passes_by_default(self):
        # aster/lighter endpoints carry no OI; None means unknown, not zero
        opps = find_opportunities(
            [snap("a", apr=0.5, oi=None), snap("b", apr=0.0)], fees=ZERO_FEES
        )
        assert len(opps) == 1
        assert opps[0].min_oi_usd is None

    def test_none_oi_dropped_when_require_oi(self):
        opps = find_opportunities(
            [snap("a", apr=0.5, oi=None), snap("b", apr=0.0)],
            fees=ZERO_FEES, require_oi=True,
        )
        assert opps == []

    def test_min_oi_reported_as_smaller_leg(self):
        opps = find_opportunities(
            [snap("a", apr=0.5, oi=9_000_000.0), snap("b", apr=0.0, oi=600_000.0)],
            fees=ZERO_FEES,
        )
        assert opps[0].min_oi_usd == pytest.approx(600_000.0)


class TestOrderingAndShape:
    def test_sorted_desc_by_net_apr(self):
        snaps = [
            snap("a", "BTC", apr=0.2), snap("b", "BTC", apr=0.0),
            snap("a", "ETH", apr=0.9), snap("b", "ETH", apr=0.0),
        ]
        opps = find_opportunities(snaps, fees=ZERO_FEES)
        assert [o.symbol for o in opps] == ["ETH", "BTC"]

    def test_three_venues_yield_best_pair_per_symbol(self):
        snaps = [snap("a", apr=0.5), snap("b", apr=0.1), snap("c", apr=-0.2)]
        opps = find_opportunities(snaps, fees=ZERO_FEES)
        # one opportunity per symbol: the widest spread (a short, c long)
        assert len(opps) == 1
        assert (opps[0].short_venue, opps[0].long_venue) == ("a", "c")
        assert opps[0].spread_apr == pytest.approx(0.7)

    def test_empty_input(self):
        assert find_opportunities([], fees=ZERO_FEES) == []

    def test_duplicate_venue_symbol_uses_first(self):
        opps = find_opportunities(
            [snap("a", apr=0.5), snap("a", apr=0.4), snap("b", apr=0.0)],
            fees=ZERO_FEES,
        )
        assert len(opps) == 1
        assert opps[0].short_apr == pytest.approx(0.5)

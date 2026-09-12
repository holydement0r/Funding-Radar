"""Trailing-mean signal and its effect on ranking."""
from radar.arb import find_opportunities
from radar.models import FundingSnapshot
from radar.signal import trailing_mean_apr

HOUR = 3600


def _history(symbol, series, *, start=1_000_000):
    """series: {venue: [apr, ...]} sampled hourly from `start`."""
    n = max(len(v) for v in series.values())
    return {symbol: [
        {"t": start + i * HOUR,
         "rates": {v: s[i] for v, s in series.items() if i < len(s)}}
        for i in range(n)
    ]}


def _snap(venue, symbol, apr, oi=1_000_000.0):
    return FundingSnapshot(venue=venue, symbol=symbol, rate=apr / 8760,
                           interval_hours=1.0, apr=apr, mark_price=100.0,
                           open_interest_usd=oi, next_funding_ts=None, fetched_at=0)


def test_mean_over_window():
    hist = _history("BTC", {"a": [0.1] * 10, "b": [0.2] * 10})
    sig = trailing_mean_apr(hist, days=4.5, now=1_000_000 + 9 * HOUR)
    assert abs(sig[("BTC", "a")] - 0.1) < 1e-12
    assert abs(sig[("BTC", "b")] - 0.2) < 1e-12


def test_points_outside_window_are_excluded():
    # 5 old points at 1.0, 10 recent at 0.0; only the recent ones count.
    hist = {"BTC": [{"t": 0 + i * HOUR, "rates": {"a": 1.0}} for i in range(5)]
                   + [{"t": 10_000_000 + i * HOUR, "rates": {"a": 0.0}} for i in range(10)]}
    sig = trailing_mean_apr(hist, days=1.0, now=10_000_000 + 9 * HOUR)
    assert sig[("BTC", "a")] == 0.0


def test_thin_series_gets_no_signal():
    hist = _history("BTC", {"a": [0.5] * 3})
    assert trailing_mean_apr(hist, days=4.5, now=1_000_000 + 2 * HOUR, min_points=8) == {}


def test_signal_ignores_a_transient_spike():
    """The whole point: one 500% print must not out-rank a steady 10%."""
    hist = _history("BTC", {"spiker": [0.0] * 9 + [5.0], "steady": [0.10] * 10})
    now = 1_000_000 + 9 * HOUR
    sig = trailing_mean_apr(hist, days=4.5, now=now)
    assert sig[("BTC", "spiker")] == 0.5  # mean of nine 0s and one 5.0
    snaps = [_snap("spiker", "BTC", 5.0), _snap("steady", "BTC", 0.10)]

    spot = find_opportunities(snaps, holding_days=21.0, fees={})[0]
    assert spot.spread_apr == 4.9  # spot ranking believes the spike

    signalled = find_opportunities(snaps, holding_days=21.0, fees={}, signal=sig)[0]
    assert abs(signalled.spread_apr - 0.4) < 1e-9  # 0.5 - 0.10
    assert signalled.spot_spread_apr == 4.9  # spot still reported for display


def test_leg_without_signal_is_not_tradeable():
    hist = _history("BTC", {"a": [0.1] * 10, "b": [0.3] * 10})
    sig = trailing_mean_apr(hist, days=4.5, now=1_000_000 + 9 * HOUR)
    # "c" has no history at all -> symbol falls back to the two signalled venues
    snaps = [_snap("a", "BTC", 0.1), _snap("b", "BTC", 0.3), _snap("c", "BTC", 9.0)]
    opp = find_opportunities(snaps, holding_days=21.0, fees={}, signal=sig)[0]
    assert {opp.long_venue, opp.short_venue} == {"a", "b"}


def test_symbol_with_one_signalled_venue_is_skipped():
    hist = _history("BTC", {"a": [0.1] * 10})
    sig = trailing_mean_apr(hist, days=4.5, now=1_000_000 + 9 * HOUR)
    snaps = [_snap("a", "BTC", 0.1), _snap("b", "BTC", 0.9)]
    assert find_opportunities(snaps, holding_days=21.0, fees={}, signal=sig) == []


def test_holding_period_sets_the_fee_hurdle():
    """A 7-day hold charges 3x the annualized fee of a 21-day hold."""
    snaps = [_snap("a", "BTC", 0.0), _snap("b", "BTC", 0.20)]
    fees = {"a": 0.0005, "b": 0.0005}
    short_hold = find_opportunities(snaps, holding_days=7.0, fees=fees)[0]
    long_hold = find_opportunities(snaps, holding_days=21.0, fees=fees)[0]
    assert short_hold.spread_apr == long_hold.spread_apr == 0.20
    assert long_hold.net_apr > short_hold.net_apr
    # round trip = 2*(0.0005+0.0005) = 0.002; over 7d that is 0.002*365/7
    assert abs(short_hold.net_apr - (0.20 - 0.002 * 365 / 7)) < 1e-9

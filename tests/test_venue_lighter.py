import json
from pathlib import Path

import pytest

from radar.venues.lighter import LighterAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "lighter.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    snaps = LighterAdapter._parse(FIXTURE, NOW)
    assert len(snaps) >= 10


def test_only_lighter_exchange_rows_kept():
    for s in LighterAdapter._parse(FIXTURE, NOW):
        assert s.venue == "lighter"
    # fixture contains binance/bybit/hyperliquid rows for BTC; exactly one BTC must survive
    btc = [s for s in LighterAdapter._parse(FIXTURE, NOW) if s.symbol == "BTC"]
    assert len(btc) == 1


def test_rates_are_8h_normalized():
    # Evidence (probed 2026-07-06): this endpoint reports hyperliquid BTC as
    # 0.0001 while HL's native hourly rate was 0.0000125 = 0.0001/8, so the
    # endpoint normalizes all venues to an 8h basis.
    snaps = {s.symbol: s for s in LighterAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.interval_hours == 8.0
    assert btc.rate == pytest.approx(9.6e-05)
    assert btc.apr == pytest.approx(9.6e-05 * 8760 / 8)


def test_no_mark_price_or_oi():
    snaps = LighterAdapter._parse(FIXTURE, NOW)
    assert all(s.mark_price is None and s.open_interest_usd is None for s in snaps)

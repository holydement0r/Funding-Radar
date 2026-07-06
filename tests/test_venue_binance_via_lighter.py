import json
from pathlib import Path

import pytest

from radar.venues.binance_via_lighter import BinanceViaLighterAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "lighter.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    snaps = BinanceViaLighterAdapter._parse(FIXTURE, NOW)
    assert len(snaps) >= 3


def test_only_binance_rows_kept():
    snaps = BinanceViaLighterAdapter._parse(FIXTURE, NOW)
    for s in snaps:
        assert s.venue == "binance_via_lighter"
    btc = [s for s in snaps if s.symbol == "BTC"]
    assert len(btc) == 1
    # fixture binance BTC rate 7.144e-05 on 8h basis
    assert btc[0].rate == pytest.approx(7.144e-05)
    assert btc[0].interval_hours == 8.0


def test_no_mark_or_oi():
    snaps = BinanceViaLighterAdapter._parse(FIXTURE, NOW)
    assert all(s.mark_price is None and s.open_interest_usd is None for s in snaps)

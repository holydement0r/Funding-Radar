import json
from pathlib import Path

import pytest

from radar.venues.hyperliquid import HyperliquidAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "hyperliquid.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    snaps = HyperliquidAdapter._parse(FIXTURE, NOW)
    assert len(snaps) >= 10


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in HyperliquidAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.venue == "hyperliquid"
    assert btc.interval_hours == 1.0
    # fixture: funding=0.0000125 hourly -> 10.95% APR
    assert btc.rate == pytest.approx(0.0000125)
    assert btc.apr == pytest.approx(0.1095)
    # openInterest is coin-denominated: 35549.62804 BTC * markPx 62903.0
    assert btc.mark_price == pytest.approx(62903.0)
    assert btc.open_interest_usd == pytest.approx(35549.62804 * 62903.0, rel=1e-6)
    assert btc.fetched_at == NOW


def test_delisted_markets_skipped():
    snaps = {s.symbol for s in HyperliquidAdapter._parse(FIXTURE, NOW)}
    assert "MATIC" not in snaps  # isDelisted in fixture


def test_all_aprs_plausible():
    for s in HyperliquidAdapter._parse(FIXTURE, NOW):
        assert abs(s.apr) <= 10.0

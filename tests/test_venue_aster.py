import json
from pathlib import Path

import pytest

from radar.venues.aster import AsterAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "aster.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    snaps = AsterAdapter._parse(FIXTURE, NOW, interval_overrides={})
    assert len(snaps) >= 10


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in AsterAdapter._parse(FIXTURE, NOW, interval_overrides={})}
    btc = snaps["BTC"]
    assert btc.venue == "aster"
    assert btc.interval_hours == 8.0  # Binance-compatible default
    assert btc.mark_price is not None and btc.mark_price > 1000
    assert btc.next_funding_ts is not None and btc.next_funding_ts > 1_700_000_000


def test_duplicate_usd_usdt_markets_prefer_usdt():
    payload = [
        {"symbol": "FOOUSD", "markPrice": "1.0", "lastFundingRate": "0.0005",
         "nextFundingTime": 1783353600000, "time": 1783326670000},
        {"symbol": "FOOUSDT", "markPrice": "2.0", "lastFundingRate": "0.0001",
         "nextFundingTime": 1783353600000, "time": 1783326670000},
    ]
    snaps = AsterAdapter._parse(payload, NOW, interval_overrides={})
    assert len(snaps) == 1
    assert snaps[0].symbol == "FOO"
    assert snaps[0].rate == pytest.approx(0.0001)  # the USDT market won


def test_interval_override_applied():
    payload = [
        {"symbol": "BARUSDT", "markPrice": "1.0", "lastFundingRate": "0.0001",
         "nextFundingTime": 1783353600000, "time": 1783326670000},
    ]
    snaps = AsterAdapter._parse(payload, NOW, interval_overrides={"BARUSDT": 4.0})
    assert snaps[0].interval_hours == 4.0
    assert snaps[0].apr == pytest.approx(0.219)

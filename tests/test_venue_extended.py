import json
from pathlib import Path

import pytest

from radar.venues.extended import ExtendedAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "extended.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    assert len(ExtendedAdapter._parse(FIXTURE, NOW)) >= 5


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in ExtendedAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.venue == "extended"
    assert btc.interval_hours == 1.0
    assert btc.rate == pytest.approx(0.000013)
    assert btc.mark_price == pytest.approx(62048.331716124994)
    # openInterest already USD-denominated in extended marketStats
    assert btc.open_interest_usd == pytest.approx(68091679.321683, rel=1e-6)


def test_inactive_markets_skipped():
    payload = {"data": [
        {"name": "DEAD-USD", "status": "DELISTED",
         "marketStats": {"fundingRate": "0.0001", "markPrice": "1.0", "openInterest": "0"}},
    ]}
    assert ExtendedAdapter._parse(payload, NOW) == []

import json
from pathlib import Path

import pytest

from radar.venues.dydx import DydxAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "dydx.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    assert len(DydxAdapter._parse(FIXTURE, NOW)) >= 5


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in DydxAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.venue == "dydx"
    assert btc.interval_hours == 1.0  # nextFundingRate is the hourly rate
    assert btc.rate == pytest.approx(0.00001936538461538462)
    # openInterest is base-denominated: 306.7816 BTC * oraclePrice 62075.3238
    assert btc.mark_price == pytest.approx(62075.3238)
    assert btc.open_interest_usd == pytest.approx(306.7816 * 62075.3238, rel=1e-6)


def test_all_aprs_plausible():
    for s in DydxAdapter._parse(FIXTURE, NOW):
        assert abs(s.apr) <= 10.0

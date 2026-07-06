import json
from pathlib import Path

import pytest

from radar.venues.paradex import ParadexAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "paradex.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    snaps = ParadexAdapter._parse(FIXTURE, NOW)
    assert len(snaps) >= 10


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in ParadexAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.venue == "paradex"
    assert btc.interval_hours == 8.0
    # fixture: funding_rate=0.00009094240654 (8h) -> ~9.96% APR
    assert btc.rate == pytest.approx(0.00009094240654)
    assert btc.apr == pytest.approx(0.00009094240654 * 8760 / 8)
    # open_interest=56.0444 BTC * mark_price
    assert btc.open_interest_usd == pytest.approx(56.0444 * 62822.62432928, rel=1e-6)


def test_option_symbols_skipped():
    # fixture deliberately contains option rows like HYPE-USD-17JUL26-84-C
    for s in ParadexAdapter._parse(FIXTURE, NOW):
        assert "-" not in s.symbol


def test_missing_funding_rate_row_skipped():
    payload = {"results": [{"symbol": "XYZ-USD-PERP", "mark_price": "1.0",
                            "open_interest": "0", "funding_rate": ""}]}
    assert ParadexAdapter._parse(payload, NOW) == []

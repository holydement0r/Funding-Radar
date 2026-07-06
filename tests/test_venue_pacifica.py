import json
from pathlib import Path

import pytest

from radar.venues.pacifica import PacificaAdapter

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "pacifica.json").read_text())
NOW = 1783326670


def test_parse_returns_snapshots():
    assert len(PacificaAdapter._parse(FIXTURE, NOW)) >= 5


def test_btc_snapshot_values():
    snaps = {s.symbol: s for s in PacificaAdapter._parse(FIXTURE, NOW)}
    btc = snaps["BTC"]
    assert btc.venue == "pacifica"
    assert btc.interval_hours == 1.0
    assert btc.rate == pytest.approx(0.0000125)
    assert btc.mark_price == pytest.approx(62006.0)
    # open_interest is base-denominated: 501.12965 BTC * mark
    assert btc.open_interest_usd == pytest.approx(501.12965 * 62006.0, rel=1e-6)


def test_all_aprs_plausible():
    for s in PacificaAdapter._parse(FIXTURE, NOW):
        assert abs(s.apr) <= 10.0

import pytest

from radar.normalize import annualize, make_snapshot, normalize_symbol

NOW = 1783326670


class TestAnnualize:
    def test_hourly_rate(self):
        # Hyperliquid-style hourly funding: 0.0000125/h -> ~10.95% APR
        assert annualize(0.0000125, 1.0) == pytest.approx(0.1095)

    def test_eight_hour_rate(self):
        # Binance/Aster-style 8h funding: 0.0001/8h -> ~10.95% APR
        assert annualize(0.0001, 8.0) == pytest.approx(0.1095)

    def test_four_hour_rate(self):
        assert annualize(0.0001, 4.0) == pytest.approx(0.219)

    def test_negative_rate(self):
        assert annualize(-0.0001, 8.0) == pytest.approx(-0.1095)

    def test_zero_rate(self):
        assert annualize(0.0, 8.0) == 0.0


class TestNormalizeSymbol:
    @pytest.mark.parametrize(
        "raw,venue,expected",
        [
            ("BTC", "hyperliquid", "BTC"),                # already bare
            ("SUSHIUSDT", "aster", "SUSHI"),              # USDT quote suffix
            ("GNSUSD", "aster", "GNS"),                   # USD quote suffix
            ("BTCUSDT", "aster", "BTC"),
            ("SOLUSDC", "aster", "SOL"),
            ("BTC-USD-PERP", "paradex", "BTC"),           # dash-separated perp
            ("ETH-PERP", "vest", "ETH"),
            ("1000PEPE", "lighter", "PEPE"),              # multiplier prefix
            ("1000000MOG", "lighter", "MOG"),
            ("kSHIB", "hyperliquid", "SHIB"),             # k-multiplier prefix
            ("kPEPE", "hyperliquid", "PEPE"),
            ("btc", "hyperliquid", "BTC"),                # lowercase input
        ],
    )
    def test_mappings(self, raw, venue, expected):
        assert normalize_symbol(raw, venue) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",                            # empty
            "HYPE-USD-17JUL26-84-C",       # option symbol leaks through (Paradex)
            "BTC-USD-17JUL26-90000-P",     # option
            "???",                         # garbage
        ],
    )
    def test_unmappable_returns_none(self, raw):
        assert normalize_symbol(raw, "any") is None

    def test_usdt_itself_not_stripped_to_empty(self):
        # A market literally named USDT-something must not normalize to ""
        assert normalize_symbol("USDT", "x") in (None, "USDT")


class TestMakeSnapshot:
    def kwargs(self, **over):
        base = dict(
            venue="aster",
            raw_symbol="BTCUSDT",
            rate=0.0001,
            interval_hours=8.0,
            mark_price=100000.0,
            oi_usd=5_000_000.0,
            next_ts=1783328400,
            now=NOW,
        )
        base.update(over)
        return base

    def test_builds_normalized_snapshot(self):
        snap = make_snapshot(**self.kwargs())
        assert snap.symbol == "BTC"
        assert snap.venue == "aster"
        assert snap.apr == pytest.approx(0.1095)
        assert snap.fetched_at == NOW

    def test_unmappable_symbol_returns_none(self):
        assert make_snapshot(**self.kwargs(raw_symbol="BTC-USD-17JUL26-90000-P")) is None

    def test_dirty_apr_above_1000_percent_returns_none(self):
        # |apr| > 10.0 (1000%) is treated as dirty data (spec section 4)
        assert make_snapshot(**self.kwargs(rate=0.01, interval_hours=1.0)) is None

    def test_negative_dirty_apr_returns_none(self):
        assert make_snapshot(**self.kwargs(rate=-0.01, interval_hours=1.0)) is None

    def test_large_but_legal_apr_kept(self):
        snap = make_snapshot(**self.kwargs(rate=0.0009, interval_hours=1.0))
        assert snap is not None
        assert snap.apr == pytest.approx(7.884)

    def test_non_finite_rate_returns_none(self):
        assert make_snapshot(**self.kwargs(rate=float("nan"))) is None
        assert make_snapshot(**self.kwargs(rate=float("inf"))) is None

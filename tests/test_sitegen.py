import pytest

from radar.sitegen import build_site

SITE_URL = "https://funding-radar.example"

LATEST = {
    "generated_at": 1783326670,
    "failed_venues": ["drift"],
    "snapshots": [
        {"venue": "hyperliquid", "symbol": "BTC", "rate": 0.0000125, "interval_hours": 1.0,
         "apr": 0.1095, "mark_price": 62000.0, "open_interest_usd": 2_000_000.0,
         "next_funding_ts": None, "fetched_at": 1783326670},
        {"venue": "paradex", "symbol": "BTC", "rate": 0.00009, "interval_hours": 8.0,
         "apr": 0.0985, "mark_price": 62010.0, "open_interest_usd": 1_500_000.0,
         "next_funding_ts": None, "fetched_at": 1783326670},
        {"venue": "hyperliquid", "symbol": "ETH", "rate": 0.00002, "interval_hours": 1.0,
         "apr": 0.1752, "mark_price": 3400.0, "open_interest_usd": 900_000.0,
         "next_funding_ts": None, "fetched_at": 1783326670},
    ],
    "opportunities": [
        {"symbol": "BTC", "long_venue": "paradex", "short_venue": "hyperliquid",
         "long_apr": 0.0985, "short_apr": 0.1095, "spread_apr": 0.011,
         "net_apr": 0.20, "min_oi_usd": 1_500_000.0},
        {"symbol": "ETH", "long_venue": "lighter", "short_venue": "aster",
         "long_apr": -1.62, "short_apr": 1.10, "spread_apr": 2.72,
         "net_apr": 2.68, "min_oi_usd": None},
    ],
}

HISTORY_7D = {
    "BTC": [
        {"t": 1783240000, "rates": {"hyperliquid": 0.10, "paradex": 0.09}},
        {"t": 1783250000, "rates": {"hyperliquid": 0.11, "paradex": 0.098}},
    ],
}


def build(tmp_path):
    return build_site(LATEST, HISTORY_7D, tmp_path, SITE_URL)


def test_returns_page_count_and_writes_index(tmp_path):
    count = build(tmp_path)
    assert count >= 4
    assert (tmp_path / "index.html").exists()


def test_index_lists_opportunity(tmp_path):
    build(tmp_path)
    html = (tmp_path / "index.html").read_text()
    assert "BTC" in html
    assert "20.0%" in html  # net apr
    assert "hyperliquid" in html and "paradex" in html


def test_index_separates_unverified_liquidity(tmp_path):
    build(tmp_path)
    html = (tmp_path / "index.html").read_text()
    verified_pos = html.find("Liquidity-verified")
    unverified_pos = html.find("Unverified liquidity")
    assert 0 < verified_pos < unverified_pos
    # the no-OI ETH opportunity renders only after the unverified heading
    assert "268" in html[unverified_pos:]  # 2.68 net apr -> 268%
    assert "268" not in html[:unverified_pos]


def test_coin_page_mark_price_not_compressed(tmp_path):
    build(tmp_path)
    page = (tmp_path / "funding-rates" / "BTC" / "index.html").read_text()
    assert "$62,000" in page       # full price, not $62.0K
    assert "$62.0K" not in page


def test_coin_page_has_venues_and_history(tmp_path):
    build(tmp_path)
    page = (tmp_path / "funding-rates" / "BTC" / "index.html").read_text()
    assert "hyperliquid" in page and "paradex" in page
    assert "10.95%" in page or "10.9" in page  # an apr string
    # 7d history rendered
    assert "History" in page or "history" in page


def test_coin_page_unique_title_and_meta(tmp_path):
    build(tmp_path)
    page = (tmp_path / "funding-rates" / "BTC" / "index.html").read_text()
    assert "<title>" in page
    assert "BTC" in page.split("<title>")[1].split("</title>")[0]
    assert 'name="description"' in page


def test_venue_page_lists_symbols(tmp_path):
    build(tmp_path)
    page = (tmp_path / "exchanges" / "hyperliquid" / "index.html").read_text()
    assert "BTC" in page and "ETH" in page


def test_compare_page_generated(tmp_path):
    build(tmp_path)
    # hyperliquid vs paradex share BTC
    p = tmp_path / "compare" / "hyperliquid-vs-paradex" / "index.html"
    assert p.exists()
    assert "BTC" in p.read_text()


def test_sitemap_and_robots(tmp_path):
    build(tmp_path)
    sitemap = (tmp_path / "sitemap.xml").read_text()
    assert SITE_URL in sitemap
    assert "funding-rates/BTC" in sitemap
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap:" in robots


def test_cta_present_on_every_page(tmp_path):
    build(tmp_path)
    for p in ("index.html", "funding-rates/BTC/index.html", "exchanges/hyperliquid/index.html"):
        html = (tmp_path / p).read_text()
        assert "Telegram" in html
        assert "Apify" in html


def test_no_javascript(tmp_path):
    build(tmp_path)
    html = (tmp_path / "index.html").read_text()
    assert "<script" not in html.lower()

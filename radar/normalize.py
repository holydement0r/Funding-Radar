"""Symbol normalization and APR math.

Money-correctness core: every venue's raw market id is mapped to a bare
coin symbol here, and every per-interval rate is annualized here. If two
venues disagree on a symbol's identity, the arb engine emits garbage —
so unmappable or suspicious inputs return None (drop, never guess).
"""
from __future__ import annotations

import math
import re

from radar.models import FundingSnapshot

HOURS_PER_YEAR = 8760.0

# |APR| above 1000% is treated as dirty data (glitched feed), spec section 4.
MAX_ABS_APR = 10.0

_QUOTE_SUFFIXES = ("USDT", "USDC", "USD")
_PERP_SUFFIXES = ("-USD-PERP", "-USDT-PERP", "-USDC-PERP", "-PERP")
_MULTIPLIER_PREFIX = re.compile(r"^(?:1(?:0{3,9})|k)(?=[A-Za-z0-9])")
_BARE_SYMBOL = re.compile(r"^[A-Z][A-Z0-9]{0,14}$")


def annualize(rate: float, interval_hours: float) -> float:
    """Annualize a per-interval funding rate."""
    return rate * (HOURS_PER_YEAR / interval_hours)


def normalize_symbol(raw: str, venue: str) -> str | None:
    """Map a venue-specific market id to a bare coin symbol, or None.

    Handles dash-separated perp names (BTC-USD-PERP), quote-currency
    suffixes (SUSHIUSDT), and multiplier prefixes (1000PEPE, kSHIB).
    Anything still containing separators after suffix stripping (e.g.
    option symbols like HYPE-USD-17JUL26-84-C) is rejected.
    """
    s = raw.strip()
    if not s:
        return None

    for suffix in _PERP_SUFFIXES:
        if s.upper().endswith(suffix):
            s = s[: -len(suffix)]
            break

    if "-" in s or "/" in s or ":" in s:
        return None  # option/expiry symbol or unknown separator format

    s = _MULTIPLIER_PREFIX.sub("", s)
    s = s.upper()

    for suffix in _QUOTE_SUFFIXES:
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)]
            break

    if not _BARE_SYMBOL.match(s):
        return None
    return s


def make_snapshot(
    venue: str,
    raw_symbol: str,
    rate: float,
    interval_hours: float,
    mark_price: float | None,
    oi_usd: float | None,
    next_ts: int | None,
    now: int,
) -> FundingSnapshot | None:
    """Build a normalized snapshot; None if the symbol or rate is unusable."""
    symbol = normalize_symbol(raw_symbol, venue)
    if symbol is None:
        return None
    if not math.isfinite(rate):
        return None
    apr = annualize(rate, interval_hours)
    if abs(apr) > MAX_ABS_APR:
        return None
    return FundingSnapshot(
        venue=venue,
        symbol=symbol,
        rate=rate,
        interval_hours=interval_hours,
        apr=apr,
        mark_price=mark_price,
        open_interest_usd=oi_usd,
        next_funding_ts=next_ts,
        fetched_at=now,
    )

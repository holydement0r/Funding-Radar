"""Core data models shared by every pipeline stage."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundingSnapshot:
    """One venue's funding state for one normalized symbol at one instant.

    ``rate`` is the per-interval funding rate as a decimal (not percent).
    ``apr`` is the annualized rate: rate * (8760 / interval_hours).
    """

    venue: str
    symbol: str
    rate: float
    interval_hours: float
    apr: float
    mark_price: float | None
    open_interest_usd: float | None
    next_funding_ts: int | None
    fetched_at: int


@dataclass(frozen=True)
class ArbOpportunity:
    """A funding-rate arbitrage pair: short the high-funding venue, long the low one.

    ``long_apr``/``short_apr`` are the live spot rates, shown to readers.
    ``spread_apr = short_apr - long_apr`` is the spread the ranking used
    (always >= 0 by construction) -- the trailing-mean spread when a signal
    is supplied, otherwise the spot spread. ``net_apr`` is that spread minus
    annualized round-trip taker fees, and is the number we publish.
    ``spot_spread_apr`` is always the instantaneous spread, kept for display
    so a reader can see how far the current print sits from its own mean.
    ``min_oi_usd`` is the smaller open interest of the two legs, None if unknown.
    """

    symbol: str
    long_venue: str
    short_venue: str
    long_apr: float
    short_apr: float
    spread_apr: float
    net_apr: float
    min_oi_usd: float | None
    spot_spread_apr: float | None = None

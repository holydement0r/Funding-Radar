"""Fee-adjusted funding-rate arbitrage engine.

Positive funding means longs pay shorts, so the carry trade is:
short the venue with the HIGHER funding APR (collect it), long the venue
with the LOWER (pay less, or collect if negative). Spread is therefore
``short_apr - long_apr`` and is always >= 0 by construction.

Cost model: entering and exiting both legs crosses the spread four times,
2 * (fee_long_venue + fee_short_venue), amortized over ``holding_days``
and annualized. Unknown venues get DEFAULT_TAKER_FEE (conservative).
"""
from __future__ import annotations

from radar.fees import DEFAULT_TAKER_FEE, TAKER_FEES
from radar.models import ArbOpportunity, FundingSnapshot

DAYS_PER_YEAR = 365.0


def find_opportunities(
    snapshots: list[FundingSnapshot],
    *,
    fees: dict[str, float] | None = None,
    min_oi_usd: float = 500_000.0,
    holding_days: float = 7.0,
    min_net_apr: float = 0.0,
    require_oi: bool = False,
) -> list[ArbOpportunity]:
    """Best opportunity per symbol, sorted by net APR descending.

    OI semantics: a numeric open interest below ``min_oi_usd`` drops the
    leg; ``None`` means the venue's API doesn't report OI (aster, lighter)
    and passes unless ``require_oi`` is set.
    """
    fee_table = TAKER_FEES if fees is None else fees

    by_symbol: dict[str, dict[str, FundingSnapshot]] = {}
    for snap in snapshots:
        if snap.open_interest_usd is None:
            if require_oi:
                continue
        elif snap.open_interest_usd < min_oi_usd:
            continue
        by_symbol.setdefault(snap.symbol, {}).setdefault(snap.venue, snap)

    opportunities = []
    for symbol, venues in by_symbol.items():
        if len(venues) < 2:
            continue
        legs = list(venues.values())
        short = max(legs, key=lambda s: s.apr)
        long = min(legs, key=lambda s: s.apr)
        if short.venue == long.venue:
            continue

        spread_apr = short.apr - long.apr
        round_trip_fees = 2 * (
            fee_table.get(long.venue, DEFAULT_TAKER_FEE)
            + fee_table.get(short.venue, DEFAULT_TAKER_FEE)
        )
        net_apr = spread_apr - round_trip_fees * (DAYS_PER_YEAR / holding_days)
        if net_apr < min_net_apr:
            continue

        ois = [s.open_interest_usd for s in (long, short)]
        min_oi = None if None in ois else min(ois)  # type: ignore[type-var]
        opportunities.append(
            ArbOpportunity(
                symbol=symbol,
                long_venue=long.venue,
                short_venue=short.venue,
                long_apr=long.apr,
                short_apr=short.apr,
                spread_apr=spread_apr,
                net_apr=net_apr,
                min_oi_usd=min_oi,
            )
        )

    opportunities.sort(key=lambda o: o.net_apr, reverse=True)
    return opportunities

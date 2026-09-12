"""Fee-adjusted funding-rate arbitrage engine.

Positive funding means longs pay shorts, so the carry trade is:
short the venue with the HIGHER funding (collect it), long the venue
with the LOWER (pay less, or collect if negative). Spread is therefore
``short - long`` and is always >= 0 by construction.

Ranking rate: when a ``signal`` is supplied, legs are chosen and scored on
each venue's trailing-mean APR rather than its latest print. The spot
spread is 5x too optimistic as a forecast -- only ~19% of it survives the
holding period -- because funding spikes mean-revert within hours. See
``radar/signal.py``. The spot rates still ride along for display.

Cost model: entering and exiting both legs crosses the spread four times,
2 * (fee_long_venue + fee_short_venue), amortized over ``holding_days``
and annualized. Unknown venues get DEFAULT_TAKER_FEE (conservative).

``holding_days`` therefore sets the fee hurdle, and it dominates: a 7-day
hold charges the trade ~7.6% APR in fees against a realized carry that
measured ~5-6% APR, which is why the v1 record was negative. Longer holds
amortize the same round trip over more carry.
"""
from __future__ import annotations

from radar.fees import DEFAULT_TAKER_FEE, TAKER_FEES
from radar.models import ArbOpportunity, FundingSnapshot

DAYS_PER_YEAR = 365.0
DEFAULT_HOLDING_DAYS = 21.0


def find_opportunities(
    snapshots: list[FundingSnapshot],
    *,
    fees: dict[str, float] | None = None,
    min_oi_usd: float = 500_000.0,
    holding_days: float = DEFAULT_HOLDING_DAYS,
    min_net_apr: float = 0.0,
    require_oi: bool = False,
    signal: dict[tuple[str, str], float] | None = None,
) -> list[ArbOpportunity]:
    """Best opportunity per symbol, sorted by net APR descending.

    OI semantics: a numeric open interest below ``min_oi_usd`` drops the
    leg; ``None`` means the venue's API doesn't report OI (aster, lighter)
    and passes unless ``require_oi`` is set.

    Signal semantics: with ``signal`` supplied, a leg is only tradeable if
    it has a trailing-mean entry, so a venue that just started reporting a
    symbol sits out until it has history. Symbols left with fewer than two
    signalled venues are skipped rather than silently falling back to spot.
    """
    fee_table = TAKER_FEES if fees is None else fees

    by_symbol: dict[str, dict[str, FundingSnapshot]] = {}
    for snap in snapshots:
        if snap.open_interest_usd is None:
            if require_oi:
                continue
        elif snap.open_interest_usd < min_oi_usd:
            continue
        if signal is not None and (snap.symbol, snap.venue) not in signal:
            continue
        by_symbol.setdefault(snap.symbol, {}).setdefault(snap.venue, snap)

    def rank_apr(snap: FundingSnapshot) -> float:
        if signal is None:
            return snap.apr
        return signal[(snap.symbol, snap.venue)]

    opportunities = []
    for symbol, venues in by_symbol.items():
        if len(venues) < 2:
            continue
        legs = list(venues.values())
        short = max(legs, key=rank_apr)
        long = min(legs, key=rank_apr)
        if short.venue == long.venue:
            continue

        spread_apr = rank_apr(short) - rank_apr(long)
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
                spot_spread_apr=short.apr - long.apr,
            )
        )

    opportunities.sort(key=lambda o: o.net_apr, reverse=True)
    return opportunities

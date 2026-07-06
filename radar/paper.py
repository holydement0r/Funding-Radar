"""Paper-trading tracker: simulate holding each verified arb opportunity.

When an opportunity appears, we open a paper position and, on every
subsequent run, accrue the *actual* funding spread realized since the
last tick (using live rates). After the holding period the position
closes with a realized net APR, which we compare against what was
predicted at entry. The resulting track record is the site's proof and
the premium tier's sales material.

Accounting: rates are annualized (APR). Over a slice dt (years), the
realized carry fraction is spread_apr_now * dt. At close, realized
fraction = accumulated_return - round_trip_fees, annualized over the
actual elapsed time. This is an approximation sampled at run cadence;
if a leg's rate is missing on a tick, that slice is skipped.
"""
from __future__ import annotations

from dataclasses import dataclass

from radar.fees import DEFAULT_TAKER_FEE
from radar.models import ArbOpportunity, FundingSnapshot

SECONDS_PER_YEAR = 365 * 86400
DAYS_PER_YEAR = 365.0


@dataclass
class PaperPosition:
    symbol: str
    long_venue: str
    short_venue: str
    entry_ts: int
    predicted_net_apr: float
    round_trip_fees: float
    accumulated_return: float
    last_update_ts: int


@dataclass
class ClosedTrade:
    symbol: str
    long_venue: str
    short_venue: str
    entry_ts: int
    exit_ts: int
    predicted_net_apr: float
    realized_net_apr: float


def _key(symbol: str, long_venue: str, short_venue: str) -> str:
    return f"{symbol}:{long_venue}:{short_venue}"


def open_positions(
    opportunities: list[ArbOpportunity],
    open_now: list[PaperPosition],
    *,
    now: int,
    fees: dict[str, float],
    max_open: int,
) -> list[PaperPosition]:
    """Open paper positions for opportunities not already tracked."""
    result = list(open_now)
    existing = {_key(p.symbol, p.long_venue, p.short_venue) for p in result}
    for opp in opportunities:
        if len(result) >= max_open:
            break
        key = _key(opp.symbol, opp.long_venue, opp.short_venue)
        if key in existing:
            continue
        round_trip = 2 * (
            fees.get(opp.long_venue, DEFAULT_TAKER_FEE)
            + fees.get(opp.short_venue, DEFAULT_TAKER_FEE)
        )
        result.append(PaperPosition(
            symbol=opp.symbol, long_venue=opp.long_venue, short_venue=opp.short_venue,
            entry_ts=now, predicted_net_apr=opp.net_apr, round_trip_fees=round_trip,
            accumulated_return=0.0, last_update_ts=now,
        ))
        existing.add(key)
    return result


def update_positions(
    open_now: list[PaperPosition],
    snapshots: list[FundingSnapshot],
    *,
    now: int,
    holding_days: float,
) -> tuple[list[PaperPosition], list[ClosedTrade]]:
    """Accrue realized funding, then close positions past the holding period."""
    apr_by: dict[tuple[str, str], float] = {
        (s.symbol, s.venue): s.apr for s in snapshots
    }
    still_open: list[PaperPosition] = []
    closed: list[ClosedTrade] = []

    for pos in open_now:
        short_apr = apr_by.get((pos.symbol, pos.short_venue))
        long_apr = apr_by.get((pos.symbol, pos.long_venue))
        if short_apr is not None and long_apr is not None:
            dt_years = (now - pos.last_update_ts) / SECONDS_PER_YEAR
            pos.accumulated_return += (short_apr - long_apr) * dt_years
        pos.last_update_ts = now

        elapsed_days = (now - pos.entry_ts) / 86400
        if elapsed_days >= holding_days:
            realized_fraction = pos.accumulated_return - pos.round_trip_fees
            realized_net_apr = (
                realized_fraction * (DAYS_PER_YEAR / elapsed_days)
                if elapsed_days > 0 else 0.0
            )
            closed.append(ClosedTrade(
                symbol=pos.symbol, long_venue=pos.long_venue, short_venue=pos.short_venue,
                entry_ts=pos.entry_ts, exit_ts=now,
                predicted_net_apr=pos.predicted_net_apr, realized_net_apr=realized_net_apr,
            ))
        else:
            still_open.append(pos)

    return still_open, closed


def summarize(closed: list[ClosedTrade]) -> dict:
    """Track-record stats over closed paper trades."""
    n = len(closed)
    if n == 0:
        return {"count": 0, "avg_predicted_apr": 0.0, "avg_realized_apr": 0.0,
                "win_rate": 0.0, "realized_vs_predicted": 0.0}
    avg_pred = sum(c.predicted_net_apr for c in closed) / n
    avg_real = sum(c.realized_net_apr for c in closed) / n
    wins = sum(1 for c in closed if c.realized_net_apr > 0)
    return {
        "count": n,
        "avg_predicted_apr": avg_pred,
        "avg_realized_apr": avg_real,
        "win_rate": wins / n,
        "realized_vs_predicted": (avg_real / avg_pred) if avg_pred else 0.0,
    }

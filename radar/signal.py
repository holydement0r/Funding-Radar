"""Trailing-mean funding signal.

The v1 engine ranked opportunities by the *instantaneous* funding spread
and extrapolated it across the whole holding period. Measured against 68
days of stored history (900 hourly snapshots, ~1.8h effective cadence),
only ~19% of that spread actually survived to be earned: funding spikes
mean-revert within hours, so the snapshot is mostly transient noise.

Ranking on a trailing mean instead targets the persistent component. Over
the same history the surviving fraction rises to ~49% and the published
prediction becomes roughly calibrated rather than 5x optimistic. See
``tools/backtest.py`` for the sweep that picked the default window.

A useful side effect: the v1 record's worst systematic bias -- picking
hyperliquid as the long leg, whose deeply negative funding reverted fast
(-8.74% mean realized) -- disappears without a venue blacklist, because a
multi-day mean simply does not see a transient spike as a good leg.
"""
from __future__ import annotations

DEFAULT_SIGNAL_DAYS = 4.5
DEFAULT_MIN_POINTS = 8


def trailing_mean_apr(
    history: dict[str, list[dict]],
    *,
    days: float = DEFAULT_SIGNAL_DAYS,
    now: float,
    min_points: int = DEFAULT_MIN_POINTS,
) -> dict[tuple[str, str], float]:
    """Mean APR per (symbol, venue) over the trailing ``days`` window.

    ``history`` is ``store.load_history_window`` output:
    ``{symbol: [{"t": ts, "rates": {venue: apr}}, ...]}`` sorted ascending.

    A (symbol, venue) pair needs at least ``min_points`` observations in the
    window to get a signal; thinner series are omitted, and callers treat a
    missing signal as "not tradeable this run" rather than falling back to
    the spot rate, which is exactly the noise the signal exists to reject.
    """
    cutoff = now - days * 86400
    sums: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], int] = {}
    for symbol, points in history.items():
        for point in points:
            if point["t"] < cutoff:
                continue
            for venue, apr in point["rates"].items():
                if apr is None:
                    continue
                key = (symbol, venue)
                sums[key] = sums.get(key, 0.0) + apr
                counts[key] = counts.get(key, 0) + 1
    return {k: sums[k] / counts[k] for k in sums if counts[k] >= min_points}

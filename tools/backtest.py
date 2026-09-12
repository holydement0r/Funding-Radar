"""Offline backtest over the stored funding history.

Replays every entry the engine would have taken and settles it against the
funding that actually printed afterwards, so a config change can be judged
without waiting a holding period per iteration.

Accrual matches ``radar/paper.py`` exactly: over each slice (t_{k-1}, t_k]
carry accrues at the spread observed AT t_k, so backtest numbers and the
live paper record are the same measurement.

    pip install -e ".[research]"
    python -m tools.backtest --data-dir data              # headline configs
    python -m tools.backtest --data-dir data --sweep hold

The history lives on the repo's `data` branch:

    git clone --depth 1 --branch data <repo> /tmp/fr-data
    python -m tools.backtest --data-dir /tmp/fr-data

Caveat that governs every number this prints: costs are taker fees only.
Slippage is not modelled, so read the breakeven-slippage column, not the
headline APR -- on the liquid universe the whole edge fits inside a few
basis points of spread crossing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

from radar.arb import DAYS_PER_YEAR, DEFAULT_HOLDING_DAYS
from radar.fees import DEFAULT_TAKER_FEE, TAKER_FEES
from radar.signal import DEFAULT_SIGNAL_DAYS

SECONDS_PER_YEAR = 365 * 86400
MIN_OI_USD = 500_000.0


def load_history(data_dir: str) -> pd.DataFrame:
    """Flatten data/history/*/*.json into (ts, venue, symbol, apr, oi)."""
    rows = []
    for path in sorted(glob.glob(os.path.join(data_dir, "history", "*", "*.json"))):
        try:
            blob = json.load(open(path))
        except (ValueError, OSError):
            continue
        ts = blob.get("captured_at")
        for snap in blob.get("snapshots", []):
            rows.append((ts, snap["venue"], snap["symbol"], snap["apr"],
                         snap.get("open_interest_usd")))
    frame = pd.DataFrame(rows, columns=["ts", "venue", "symbol", "apr", "oi"])
    return frame.dropna(subset=["apr", "ts"]).sort_values("ts").reset_index(drop=True)


class Grid:
    """History as dense (venue, time, symbol) arrays, plus prefix sums."""

    def __init__(self, frame: pd.DataFrame, ffill_limit: int = 3):
        self.ts = np.sort(frame.ts.unique())
        # Seconds per slice, as a fraction of a year. Slice 0 accrues nothing.
        dt = np.diff(self.ts, prepend=self.ts[0]) / SECONDS_PER_YEAR

        apr = frame.pivot_table(index="ts", columns=["venue", "symbol"],
                                values="apr", aggfunc="last").reindex(self.ts)
        oi = frame.pivot_table(index="ts", columns=["venue", "symbol"],
                               values="oi", aggfunc="last").reindex(self.ts)
        # Venues that never report OI drop out of the pivot entirely.
        oi = oi.reindex(columns=apr.columns)
        apr, oi = apr.ffill(limit=ffill_limit), oi.ffill(limit=ffill_limit)

        self.venues = sorted(frame.venue.unique())
        self.symbols = sorted(frame.symbol.unique())
        stack = lambda df: np.stack(  # noqa: E731
            [df[v].reindex(columns=self.symbols).values for v in self.venues])

        self.apr = stack(apr)
        self.oi = stack(oi)
        # carry[v, k, s] = sum_{j<=k} apr*dt  ->  accrual(a..b) = carry[b]-carry[a]
        self.carry = np.nan_to_num(self.apr * dt[None, :, None]).cumsum(axis=1)
        # observed[v, k, s] counts slices with a real print, for coverage checks
        self.observed = np.isfinite(self.apr).astype(float).cumsum(axis=1)
        self.fee = np.array([TAKER_FEES.get(v, DEFAULT_TAKER_FEE) for v in self.venues])
        self.n_venues, self.n_ts, self.n_symbols = self.apr.shape

    def trailing_mean(self, days: float) -> np.ndarray:
        """NaN-aware trailing mean of apr over `days`, matching radar.signal."""
        if days <= 0:
            return self.apr
        value = np.nan_to_num(self.apr)
        present = np.isfinite(self.apr).astype(float)
        cum_v, cum_p = value.cumsum(axis=1), present.cumsum(axis=1)
        start = np.searchsorted(self.ts, self.ts - days * 86400, side="left")
        pad = lambda c: np.concatenate(  # noqa: E731
            [np.zeros((self.n_venues, 1, self.n_symbols)), c], axis=1)[:, start, :]
        total, count = cum_v - pad(cum_v), cum_p - pad(cum_p)
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def backtest(grid: Grid, *, hold_days: float = DEFAULT_HOLDING_DAYS,
             signal_days: float = DEFAULT_SIGNAL_DAYS, min_net: float = 0.0,
             require_oi: bool = True, entry_every: int = 6, top_n: int = 10,
             min_coverage: float = 0.8, min_points: int = 8) -> pd.DataFrame:
    rank = grid.trailing_mean(signal_days)
    points = (grid.observed - np.concatenate(
        [np.zeros((grid.n_venues, 1, grid.n_symbols)), grid.observed], axis=1)[
        :, np.searchsorted(grid.ts, grid.ts - signal_days * 86400, side="left"), :]
    ) if signal_days > 0 else np.full_like(grid.observed, min_points)

    eligible = np.isfinite(grid.apr) & np.isfinite(rank) & (points >= min_points)
    if require_oi:
        eligible &= np.nan_to_num(grid.oi, nan=-1.0) >= MIN_OI_USD
    else:
        eligible &= np.nan_to_num(grid.oi, nan=MIN_OI_USD) >= MIN_OI_USD

    cols = np.arange(grid.n_symbols)
    trades = []
    for i in range(grid.n_ts):
        if i % entry_every:
            continue
        exit_i = np.searchsorted(grid.ts, grid.ts[i] + hold_days * 86400)
        if exit_i >= grid.n_ts:
            break
        live = eligible[:, i, :]
        scored = np.where(live, rank[:, i, :], np.nan)
        highs = np.where(live, scored, -np.inf)
        lows = np.where(live, scored, np.inf)
        short_i, long_i = np.argmax(highs, axis=0), np.argmin(lows, axis=0)
        short_r, long_r = highs[short_i, cols], lows[long_i, cols]

        ok = np.isfinite(short_r) & np.isfinite(long_r) & (short_i != long_i)
        spread = short_r - long_r
        round_trip = 2 * (grid.fee[long_i] + grid.fee[short_i])
        predicted = spread - round_trip * (DAYS_PER_YEAR / hold_days)
        ok &= predicted >= min_net
        if not ok.any():
            continue
        picks = np.where(ok)[0]
        picks = picks[np.argsort(-predicted[picks])][:top_n]

        slices = exit_i - i
        elapsed_days = (grid.ts[exit_i] - grid.ts[i]) / 86400
        for s in picks:
            long_v, short_v = long_i[s], short_i[s]
            seen = min(grid.observed[short_v, exit_i, s] - grid.observed[short_v, i, s],
                       grid.observed[long_v, exit_i, s] - grid.observed[long_v, i, s])
            if not slices or seen / slices < min_coverage:
                continue
            accrued = ((grid.carry[short_v, exit_i, s] - grid.carry[short_v, i, s])
                       - (grid.carry[long_v, exit_i, s] - grid.carry[long_v, i, s]))
            annualize = DAYS_PER_YEAR / elapsed_days
            trades.append((grid.ts[i], grid.symbols[s], grid.venues[long_v],
                           grid.venues[short_v], spread[s], predicted[s],
                           accrued * annualize,
                           (accrued - round_trip[s]) * annualize, hold_days))
    return pd.DataFrame(trades, columns=["ts", "symbol", "long", "short", "spread",
                                         "predicted", "gross", "net", "hold_days"])


def describe(label: str, trades: pd.DataFrame) -> str:
    if trades.empty:
        return f"{label:38} no trades"
    mid = trades.ts.min() + (trades.ts.max() - trades.ts.min()) / 2
    first, second = trades[trades.ts < mid], trades[trades.ts >= mid]
    hold = trades.hold_days.iloc[0]
    # Slippage that would zero the mean: 4 spread crossings per round trip.
    breakeven_bps = trades.net.mean() / (4 * DAYS_PER_YEAR / hold) * 1e4
    return (f"{label:38} n={len(trades):5d} pred {trades.predicted.mean():+7.2%} "
            f"gross {trades.gross.mean():+7.2%} net {trades.net.mean():+7.2%} "
            f"win {(trades.net > 0).mean():5.1%} "
            f"sharpe {trades.net.mean() / trades.net.std():+5.2f} "
            f"| halves {first.net.mean():+6.2%}/{second.net.mean():+6.2%} "
            f"| breakeven {breakeven_bps:5.1f}bps")


HEADLINE = [
    ("v1 spot signal, 7d hold", dict(signal_days=0, hold_days=7)),
    ("v1 signal, 21d hold", dict(signal_days=0, hold_days=21)),
    ("v2 trailing signal, 7d hold", dict(hold_days=7)),
    ("v2 trailing signal, 14d hold", dict(hold_days=14)),
    ("v2 trailing signal, 21d hold", dict(hold_days=21)),
    ("v2 + unverified OI, 21d hold", dict(hold_days=21, require_oi=False)),
]
SWEEPS = {
    "hold": [(f"hold={h}d", dict(hold_days=h)) for h in (3, 5, 7, 10, 14, 21, 30)],
    "signal": [(f"signal={d}d", dict(signal_days=d))
               for d in (0, 0.5, 1, 2, 3, 4.5, 7, 9)],
    "threshold": [(f"min_net={t:.0%}", dict(min_net=t))
                  for t in (0, 0.05, 0.10, 0.20, 0.30)],
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.backtest")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--sweep", choices=sorted(SWEEPS))
    args = parser.parse_args(argv)

    frame = load_history(args.data_dir)
    if frame.empty:
        print(f"no history under {args.data_dir}/history/")
        return 1
    span = (frame.ts.max() - frame.ts.min()) / 86400
    print(f"{len(frame):,} rows, {frame.ts.nunique()} snapshots, {span:.1f} days, "
          f"{frame.venue.nunique()} venues, {frame.symbol.nunique()} symbols\n")

    grid = Grid(frame)
    print("Costs are taker fees only. `breakeven` is the per-leg, per-side "
          "slippage in bps\nthat would erase the mean -- the number that "
          "decides whether a row is tradeable.\n")
    for label, kwargs in (SWEEPS[args.sweep] if args.sweep else HEADLINE):
        print(describe(label, backtest(grid, **kwargs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

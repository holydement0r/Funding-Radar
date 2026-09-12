# Why v1 lost money, and what v2 changes

Measured 2026-09-12 against 475 closed paper trades (2026-07-06 → 2026-09-12) and
68 days of stored history (900 snapshots, ~1.8h effective cadence, 8 venues,
801 symbols). Everything here is reproducible from the `data` branch:

```
git clone --depth 1 --branch data <repo> /tmp/fr-data
pip install -e ".[research]"
python -m tools.backtest --data-dir /tmp/fr-data
python -m tools.backtest --data-dir /tmp/fr-data --sweep hold
```

## The v1 result

| | |
|---|---|
| Closed trades | 475 |
| Avg predicted net APR | **+21.11%** |
| Avg realized net APR | **−4.21%** |
| Win rate | 27.79% |
| Median realized | −4.54% |

The loss was not caused by a few blowups. The median (−4.54%) and the 5%-trimmed
mean (−4.27%) sit on top of the mean, so this was a constant drag on nearly every
trade.

## Decomposition

Splitting realized net APR into what was earned and what was paid:

| Component | Mean APR |
|---|---|
| Predicted spread at entry (gross) | +28.68% |
| Realized gross carry | **+3.37%** |
| Fee drag (7-day hold, annualized) | **−7.58%** |
| = Realized net | −4.21% |

Two independent failures, and either one alone was nearly fatal.

**1. The spread does not survive.** Realized carry was 17% of the predicted spread
(median 12.9%). Funding spikes mean-revert within hours, so an instantaneous
snapshot is mostly transient noise, and ranking by the largest current spread is
close to ranking by the largest current noise. Gross carry was still positive on
66.9% of trades — the direction was right, the magnitude was off by 5x.

**2. The holding period could not carry the fees.** Four spread crossings
(2 × (fee_long + fee_short)) amortized over 7 days cost 7.58% APR against a carry
that realized 3.37%. Only 27.8% of trades earned enough gross carry to clear their
own fees.

A third effect fell out of the first: because v1 chased extremes, it systematically
picked hyperliquid as the long leg (deeply negative funding, which reverted fastest)
and realized **−8.74%** there, against **+1.40%** with dydx as the long leg.

## What v2 changes

Rank on the trailing multi-day mean of each venue's funding instead of its latest
print, and hold longer so the same round trip is amortized over more carry.

Backtest over the same 68 days, liquidity-verified universe, top 10 per entry:

| Config | Predicted | Gross | Net | Win | Sharpe | Halves |
|---|---|---|---|---|---|---|
| v1 spot, 7d hold | +23.16% | +5.94% | **−1.59%** | 39.7% | −0.16 | −1.86 / −1.37 |
| v1 spot, 21d hold | +27.31% | +4.06% | +1.53% | 62.0% | +0.22 | +1.49 / +1.56 |
| v2 trailing, 7d hold | +10.34% | +7.60% | +0.04% | 49.8% | +0.01 | +0.13 / −0.02 |
| v2 trailing, 14d hold | +13.48% | +6.46% | +2.60% | 68.0% | +0.39 | +2.92 / +2.38 |
| **v2 trailing, 21d hold** | +12.71% | +5.75% | **+3.16%** | 71.0% | +0.50 | +3.46 / +2.95 |

Both halves of the sample agree, and on non-overlapping entries only (n=20) the
21-day config still returns +4.31% at a 80% win rate. The prediction also becomes
roughly calibrated: the earned fraction of the predicted spread rises from ~19% to
~49%, so the published number stops being a five-times-optimistic advertisement.

The hyperliquid-long bias disappears without a venue blacklist (−8.74% → +1.20%),
which is the useful confirmation that the diagnosis was right: it was never about
that venue, it was about reacting to transient prints.

## The honest limit

**Slippage is not modelled anywhere above.** Costs are taker fees only. The number
that decides whether any of this is tradeable is the breakeven slippage — how wide
you can cross the book per leg per side before the mean goes to zero:

| Universe | Hold | Breakeven |
|---|---|---|
| Liquidity-verified | 21d | **4.6 bps** |
| Liquidity-verified | 30d | 8.3 bps |
| Unverified-OI (alts on 0-fee venues) | 21d | 19.7 bps |
| Unverified-OI | 30d | 29.8 bps |

On majors the entire edge fits inside a few basis points of spread crossing. That is
the real product boundary, and it is why the site and the store listing describe
this as a screen rather than a signal to fill blindly.

The unverified-OI universe backtests far better (+16.14% net, 81.4% win, 23.2 bps of
cushion) because it reaches aster and lighter, whose taker fees are 0% and which are
excluded from the verified universe only because their APIs report no open interest.
That result is **not** promoted to the alert channel or the verified table: no OI
means no way to check that the size exists, the cushion is measured against fees we
can verify rather than books we can see, and the names driving it are small caps
where 20-30 bps of slippage is entirely plausible. It is recorded here as the most
promising lead, pending a liquidity check that does not depend on an OI endpoint.

## Reporting

v1 and v2 paper records are stored and displayed separately (`version` on every
position and closed trade, `summarize_by_version`, per-version retention in
`store._trim_per_version`). v1 positions keep closing on their original 7-day rule.
The v1 record stays on the public track-record page. Merging the two would launder
a published loss into a new average, and the point of keeping a paper record is
that it can say the strategy did not work.

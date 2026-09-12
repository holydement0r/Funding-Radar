# Funding Rate API — Perp DEX Funding & Arbitrage Scanner

Get **live funding rates** and **ready-to-trade funding-arbitrage opportunities** across 8 decentralized perp DEXs in a single call. No monthly subscription — you pay only for the rows you pull.

Comparable data feeds charge $29–699/month. Here, a typical query costs a few cents.

## What can you do with it?

- **Find funding-arb trades**: see which coin to short on which venue and long on another, ranked by net APR *after* round-trip taker fees — and ranked on the funding each venue has *sustained over days*, not the latest print, which mostly evaporates before you can earn it.
- **Feed your trading bot**: pull normalized funding rates across venues on your own schedule instead of integrating 8 different exchange APIs with 8 different formats and funding intervals.
- **Monitor a single venue**: filter to just the exchanges or coins you trade.

## Supported exchanges (8)

Hyperliquid · Aster · Paradex · Lighter · Binance (via Lighter) · dYdX v4 · Extended · Pacifica

All rates are normalized to a common annualized APR, so a 1h-funding venue and an 8h-funding venue are directly comparable.

## How to use

Run the Actor with JSON input (via the Apify Console, API, or any Apify client):

```json
{
  "mode": "arb",
  "symbols": [],
  "venues": [],
  "minNetApr": "0.10",
  "requireOi": true
}
```

| Field | What it does |
|-------|--------------|
| `mode` | `arb` = ranked arbitrage opportunities · `rates` = raw funding rates per venue per coin |
| `symbols` | Only these coins, e.g. `["BTC", "ETH"]`. Empty = all (~600 coins) |
| `venues` | Only these exchanges, e.g. `["hyperliquid", "paradex"]`. Empty = all 8 |
| `minNetApr` | Arb mode: minimum net APR as a decimal (`"0.10"` = 10%) |
| `requireOi` | Arb mode: drop opportunities where a leg's open interest is unknown — filters thin markets that show absurd, unfillable APRs. Keep `true` |

Results land in the run's dataset — download as JSON, CSV, or Excel, or read them via the Apify API.

### Example output — `arb` mode

```json
{
  "symbol": "ETH",
  "short_venue": "hyperliquid",
  "short_apr": 0.1095,
  "long_venue": "dydx",
  "long_apr": -0.0219,
  "spread_apr": 0.1828,
  "spot_spread_apr": 0.1314,
  "net_apr": 0.1498,
  "min_oi_usd": 4528851,
  "ranking": "trailing-mean"
}
```

Read it as: short ETH on Hyperliquid, long ETH on dYdX. `spot_spread_apr` (13.14%) is
the gap between the two venues' funding *right now*; `spread_apr` (18.28%) is the gap
between their multi-day averages, which is what the ranking uses and what has actually
tended to persist. After round-trip taker fees over the assumed hold you keep an
estimated **14.98% APR**, with at least $4.5M open interest on the thinner leg.

When `ranking` reads `spot-fallback`, the published signal was unreachable and that row
was ranked on the current print alone — the method described below as retired. Treat
those rows as a raw screen, not a ranking.

### Example output — `rates` mode

```json
{
  "venue": "hyperliquid",
  "symbol": "BTC",
  "rate": 0.0000125,
  "interval_hours": 1.0,
  "apr": 0.1095,
  "mark_price": 62903.0,
  "open_interest_usd": 2236125876,
  "fetched_at": 1783326670
}
```

### Call it from code

```python
from apify_client import ApifyClient

client = ApifyClient("<YOUR_API_TOKEN>")
run = client.actor("opaline_midge/funding-radar").call(
    run_input={"mode": "arb", "minNetApr": "0.10", "requireOi": True}
)
for row in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(row["symbol"], row["net_apr"])
```

## Why net APR instead of raw spread?

A 30% funding spread means nothing if you pay 4 taker fees to enter and exit both legs.
This Actor subtracts annualized round-trip taker fees (per-venue fee table, verified
against official docs) over an assumed 21-day hold, so the ranking reflects what you
could actually keep.

## Why the multi-day average instead of the current rate?

Because we measured the alternative and published the result. The first version of this
engine ranked on the instantaneous spread and assumed a 7-day hold. Paper-traded over
475 opportunities it predicted **+21.1% APR** and realized **−4.2%**, winning 27.8% of
the time. Two reasons, both structural:

- **Funding spikes mean-revert within hours.** Only about a fifth of the advertised
  spread was ever earned. Ranking on the biggest current spread is close to ranking on
  the biggest current noise.
- **A short hold cannot carry the fees.** Four spread crossings amortized over 7 days
  cost ~7.6% APR against a carry that realized ~5%. The trade started under water.

Ranking on a multi-day mean and holding longer fixes both: over 68 days of stored
history the earned fraction of the predicted spread rises from ~19% to ~49%, and the
published number becomes roughly calibrated rather than five times optimistic. The
sweep is reproducible — `python -m tools.backtest --data-dir <data branch clone>`.

### The number that actually decides a trade

Costs modelled here are taker fees only; slippage is not. On the liquidity-verified
universe the entire edge fits inside roughly **4–5 basis points per leg per side** of
spread crossing. Cross the book wider than that and the strategy is flat to negative.
Funding arbitrage on majors is a thin-margin trade — this feed is a screen that tells
you where to look, and the last word belongs to the book you are about to cross.

Live results, including the losing first generation, are published in full:
https://holydement0r.github.io/Funding-Radar/track-record/

## FAQ

**How fresh is the data?** Fetched live from the venues' public APIs at the moment you run the Actor — not cached.

**Why do some rows have `min_oi_usd: null`?** A few venues don't publish open interest. With `requireOi: true` (default) those pairs are excluded from arb results.

**Is this trading advice?** No. Funding rates flip fast, thin books slip, and DEXs carry smart-contract and counterparty risk. Net APR is an estimate before slippage, not a guarantee. Always verify against the live book before trading.

**A venue is missing from my results.** Single-venue outages are isolated — the Actor returns data from the healthy venues instead of failing the whole run.

## More

- Free web dashboard (updates every 30 min): https://holydement0r.github.io/Funding-Radar/
- Free Telegram alerts: https://t.me/FundingRadarAlerts
- Open source — code, architecture, and development docs: [docs/development.md](docs/development.md)

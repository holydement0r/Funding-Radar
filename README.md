# Funding Rate API — Perp DEX Funding & Arbitrage Scanner

Get **live funding rates** and **ready-to-trade funding-arbitrage opportunities** across 8 decentralized perp DEXs in a single call. No monthly subscription — you pay only for the rows you pull.

Comparable data feeds charge $29–699/month. Here, a typical query costs a few cents.

## What can you do with it?

- **Find funding-arb trades**: see which coin to short on which venue and long on another, ranked by net APR *after* round-trip taker fees — not the raw spread that evaporates once you pay fees.
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
  "symbol": "LIT",
  "short_venue": "hyperliquid",
  "short_apr": 0.1095,
  "long_venue": "extended",
  "long_apr": -0.3767,
  "spread_apr": 0.4862,
  "net_apr": 0.4132,
  "min_oi_usd": 4528851
}
```

Read it as: short LIT on Hyperliquid (funding pays you 10.95% APR), long LIT on Extended (negative funding pays you another 37.67%), and after taker fees on both legs you keep an estimated **41.3% APR**, with at least $4.5M open interest on the thinner leg.

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

A 30% funding spread means nothing if you pay 4 taker fees to enter and exit both legs. This Actor subtracts annualized round-trip taker fees (per-venue fee table, verified against official docs) over an assumed 7-day hold, so the ranking reflects what you could actually keep.

## FAQ

**How fresh is the data?** Fetched live from the venues' public APIs at the moment you run the Actor — not cached.

**Why do some rows have `min_oi_usd: null`?** A few venues don't publish open interest. With `requireOi: true` (default) those pairs are excluded from arb results.

**Is this trading advice?** No. Funding rates flip fast, thin books slip, and DEXs carry smart-contract and counterparty risk. Net APR is an estimate, not a guarantee. Always verify before trading.

**A venue is missing from my results.** Single-venue outages are isolated — the Actor returns data from the healthy venues instead of failing the whole run.

## More

- Free web dashboard (updates every 30 min): https://holydement0r.github.io/Funding-Radar/
- Free Telegram alerts: https://t.me/FundingRadarAlerts
- Open source — code, architecture, and development docs: [docs/development.md](docs/development.md)

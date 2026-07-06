# Funding Rate API — Perp DEX Funding & Arbitrage

Live perpetual **funding rates** and fee-adjusted **funding-arbitrage opportunities** across 8 decentralized perp DEXs, in one call. A cheaper, pay-as-you-go alternative to $29+/month funding-data subscriptions — you pay only for the results you pull.

## What you get

Two modes:

- **`arb`** — ranked funding-arbitrage opportunities. For each coin: which venue to short (high funding), which to long (low/negative funding), the spread, and the **net APR after round-trip taker fees**. Thin/stale markets are filtered out by default.
- **`rates`** — raw funding rate per venue per coin: rate, funding interval, annualized APR, mark price, open interest.

## Tracked venues (8)

hyperliquid · aster · paradex · lighter · binance (via lighter) · dydx · extended · pacifica

## Input

```json
{
  "mode": "arb",
  "symbols": ["BTC", "ETH"],
  "venues": [],
  "minNetApr": "0.10",
  "requireOi": true
}
```

| Field | Meaning |
|-------|---------|
| `mode` | `arb` (opportunities) or `rates` (raw rates) |
| `symbols` | filter to these coins; empty = all |
| `venues` | filter to these exchanges; empty = all 8 |
| `minNetApr` | arb only: minimum net APR (decimal, `0.10` = 10%) |
| `requireOi` | arb only: drop legs with unknown open interest (recommended) |

## Example output (arb)

```json
{
  "symbol": "LIT",
  "short_venue": "hyperliquid", "short_apr": 0.1095,
  "long_venue": "extended", "long_apr": -0.37668,
  "spread_apr": 0.48618, "net_apr": 0.41318,
  "min_oi_usd": 4528851.81
}
```

## Notes

- Data is fetched live on each run from public venue APIs.
- Net APR subtracts annualized round-trip taker fees over a 7-day hold; it is an estimate, not a guarantee. Funding rates change continuously.
- Not financial advice. Funding arbitrage carries execution, liquidation, and counterparty risk.

---

### For the maintainer — publishing checklist

1. Install CLI: `npm i -g apify-cli`, then `apify login`.
2. From the **repo root** (where `.actor/` lives): `apify push`. The build
   installs the radar library from local source — no GitHub clone, no rate limits.
3. In Apify Console → your actor → Publication → Monetization: turn on **Pay per event + usage** (takes 14 days to activate). Both charges use Apify's built-in events — no custom events to define:
   - `apify-actor-start` — auto-charged once per run. Raise its price from the $0.00005 default to ~$0.02 (base compute).
   - `apify-default-dataset-item` — auto-charged per row pushed to the default dataset. Set ~$0.005.
   Undercuts Coinglass's subscription while staying profitable.
4. Local test before publish: `ACTOR_TEST_PAY_PER_EVENT=true apify run` (events default to $1 locally).

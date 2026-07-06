# Venue Notes

Status of every perp-DEX venue considered for Funding Radar. Probed 2026-07-06 from a WSL/US-egress host (same network profile as GitHub Actions / Apify).

## Live adapters (8 venues)

| Venue | Endpoint | Funding interval | OI source |
|-------|----------|-----------------|-----------|
| hyperliquid | POST api.hyperliquid.xyz/info `metaAndAssetCtxs` | 1h | base * markPx |
| aster | GET fapi.asterdex.com/fapi/v1/premiumIndex | 8h | none |
| paradex | GET api.prod.paradex.trade/v1/markets/summary?market=ALL | 8h | base * mark_price |
| lighter | GET mainnet.zklighter.elliot.ai/api/v1/funding-rates | 8h (normalized) | none |
| binance_via_lighter | same Lighter endpoint, `exchange=="binance"` | 8h (normalized) | none |
| dydx | GET indexer.dydx.trade/v4/perpetualMarkets | 1h | base * oraclePrice |
| extended | GET api.starknet.extended.exchange/api/v1/info/markets | 1h | marketStats.openInterest (already USD) |
| pacifica | GET api.pacifica.fi/api/v1/info/prices | 1h | base * mark |

Intervals for dydx/extended/pacifica inferred from rate magnitude + funding cadence; Sonnet to confirm against official docs (plan Task 18).

## Skipped venues (revisit later)

| Venue | Reason (2026-07-06) | Retry idea |
|-------|--------------------|-----------|
| drift | data.api.drift.trade returns 403 Forbidden (Cloudflare); dlob/mainnet-beta hosts unreachable or 404 | Solana on-chain read or gateway/DAS API; needs research >30min |
| vest | serverprod.vest.exchange returns Cloudflare 530/1016; alt hosts DNS-fail | find current API host from app network tab |
| bluefin | dapi.api.sui-prod.bluefin.io returns 503 "no healthy upstream" / connection refused | host likely renamed; check bluefin docs |
| edgex | pro.edgex.exchange getTicker returns empty data[] (needs contractId); metadata is ~460KB and funding is per-contract, no bulk funding endpoint found | iterate contractList ids against a funding endpoint; heavier |
| hibachi | market/exchange-info lists 12 contracts but carries no funding; prices endpoint requires per-symbol `symbol` param, no bulk funding found | 12 per-symbol calls if a funding field exists there |

Each skip stopped at the 30-minute budget per the plan. None are blocked by fundamental auth walls except drift/vest (Cloudflare); edgex/hibachi are just more request-shaped work.

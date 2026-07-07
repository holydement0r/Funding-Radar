# Funding Radar

Cross-exchange **perpetual funding-rate aggregator + funding-arbitrage scanner** for decentralized perp DEXs. One pipeline feeds three channels:

- **Telegram alerts** — live funding-arb opportunities pushed to a free channel
- **SEO static site** — a programmatically generated page per coin, per exchange, and per exchange-pair (GitHub Pages)
- **Apify API** — the same data, queryable programmatically, pay-per-result

No servers. The whole thing runs on a GitHub Actions cron every 30 minutes; git branches are the only storage.

## Links

- **Site:** https://holydement0r.github.io/Funding-Radar/
- **Telegram:** https://t.me/FundingRadarAlerts
- **API (Apify):** https://apify.com/opaline_midge/funding-radar

## How it works

```
GitHub Actions (*/30) → collect 8 perp DEXs → normalize → arb scan (fee-adjusted)
   → write latest.json + hourly history (data branch)
   → Telegram alerts (dedup)
   → build static site → GitHub Pages
```

Arb logic: for each coin, short the highest-funding venue and long the lowest. Net APR subtracts annualized round-trip taker fees over a 7-day hold. Opportunities whose legs have unknown or thin open interest are filtered out, since those show absurd APRs you cannot actually fill.

Every alerted opportunity is also **paper-traded** (held 7 days, funding accrued at live rates, then closed) to build a public realized-vs-predicted track record.

## Tracked venues (8)

hyperliquid · aster · paradex · lighter · binance (via lighter) · dydx · extended · pacifica

See [docs/venue-notes.md](docs/venue-notes.md) for data sources and the venues that were skipped (drift, vest, bluefin, edgex, hibachi) with reasons.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                              # full suite
python -m radar.run --dry-run --data-dir /tmp/fr       # offline pipeline smoke (fixtures)
python -m radar.run --skip-telegram --site-out _site   # live data, build site, no alerts
```

## Configuration

Alert threshold and arb filters:

- Alert threshold: `ALERT_THRESHOLD_APR` env var (default `0.10` = 10%)
- Min open interest / holding days: `find_opportunities(...)` defaults in `radar/arb.py`
- Taker fees per venue: `radar/fees.py`

Runtime secrets (GitHub Actions): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `TELEGRAM_ADMIN_CHAT_ID`. Variables: `SITE_URL`, `TELEGRAM_URL`, `APIFY_URL`.

## Disclaimer

Not financial advice. Funding arbitrage carries execution, liquidation, and counterparty risk. Funding rates change continuously and thin DEX liquidity causes slippage; the displayed net APR is an estimate after fees, not a guarantee. Data can be stale or wrong.

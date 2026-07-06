# Funding Radar

Cross-exchange **perpetual funding-rate aggregator + funding-arbitrage scanner** for decentralized perp DEXs. One pipeline feeds three channels:

- **Telegram alerts** — live funding-arb opportunities pushed to a free channel
- **SEO static site** — a programmatically generated page per coin, per exchange, and per exchange-pair (GitHub Pages)
- **Apify API** — the same data queryable programmatically (P2)

No servers. The whole thing runs on a GitHub Actions cron every 30 minutes; git branches are the only storage.

## How it works

```
GitHub Actions (*/30) → collect 8 perp DEXs → normalize → arb scan (fee-adjusted)
   → write latest.json + hourly history (data branch)
   → Telegram alerts (dedup)
   → build static site → GitHub Pages
```

Arb logic: for each coin, short the highest-funding venue and long the lowest. Net APR subtracts annualized round-trip taker fees over a 7-day hold.

## Tracked venues (8)

hyperliquid · aster · paradex · lighter · binance (via lighter) · dydx · extended · pacifica

See [docs/venue-notes.md](docs/venue-notes.md) for data sources and the venues that were skipped (drift, vest, bluefin, edgex, hibachi) with reasons.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                   # full suite
python -m radar.run --dry-run --data-dir /tmp/fr   # offline pipeline smoke (fixtures)
python -m radar.run --skip-telegram --site-out _site   # live data, build site, no alerts
```

## Launch checklist (one-time, ~1 hour)

Everything below needs your accounts; the code is ready.

1. **Create a public GitHub repo** and push this repository to it.
   (Public repo = free unlimited Actions minutes + free Pages.)
2. **Create the Telegram bot + channel:**
   - Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
   - Create a public channel; add the bot as an administrator.
   - Get the channel id (e.g. `@yourchannel` works directly).
   - For failure DMs: message your bot, then note your own numeric chat id.
3. **Add repo secrets** (Settings → Secrets and variables → Actions → Secrets):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID` (e.g. `@yourchannel`)
   - `TELEGRAM_ADMIN_CHAT_ID` (your numeric id, for failure alerts)
4. **Add repo variables** (same page → Variables):
   - `SITE_URL` (e.g. `https://<user>.github.io/<repo>`)
   - `TELEGRAM_URL` (e.g. `https://t.me/yourchannel`)
   - `APIFY_URL` (leave the default until the Apify actor ships in P2)
5. **Enable Pages:** Settings → Pages → Source = "GitHub Actions".
6. **Test before the schedule runs:** Actions → `cron` → "Run workflow".
   Confirm: green run, `data` branch created, Pages URL live. To force a
   first alert, temporarily lower the threshold (see below), run, then restore.

Record the live URLs here after launch:

- Site: _TBD_
- Telegram channel: _TBD_
- Apify actor: _TBD (P2)_

## Tuning

Alert threshold and arb filters live in code:

- Alert threshold: `select_alerts(..., threshold_apr=0.15)` in `radar/run.py`
- Min open interest / holding days: `find_opportunities(...)` defaults in `radar/arb.py`
- Taker fees per venue: `radar/fees.py`

## Disclaimer

Not financial advice. Funding arbitrage carries execution, liquidation, and counterparty risk. Data can be stale or wrong.

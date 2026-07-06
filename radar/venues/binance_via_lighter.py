"""Binance funding rates, sourced via the Lighter aggregator endpoint.

Lighter's public funding-rates endpoint (see lighter.py) reports several
venues including Binance, on an 8h-normalized basis. Binance's own API is
geo-blocked from US IPs (GitHub Actions / Apify run in the US), but the
Lighter proxy is not — so we surface Binance as a pseudo-venue here for
free, geo-unblocked coverage. Filtered on exchange == "binance".
"""
from __future__ import annotations

import time

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

FUNDING_RATES_URL = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"
INTERVAL_HOURS = 8.0


@register
class BinanceViaLighterAdapter(VenueAdapter):
    name = "binance_via_lighter"

    def fetch(self) -> list[FundingSnapshot]:
        payload = self._get(FUNDING_RATES_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        seen: set[str] = set()
        for row in payload["funding_rates"]:
            if row.get("exchange") != "binance":
                continue
            if row["symbol"] in seen:
                continue
            seen.add(row["symbol"])
            snap = make_snapshot(
                venue="binance_via_lighter",
                raw_symbol=row["symbol"],
                rate=float(row["rate"]),
                interval_hours=INTERVAL_HOURS,
                mark_price=None,
                oi_usd=None,
                next_ts=None,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

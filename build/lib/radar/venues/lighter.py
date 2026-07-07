"""Lighter adapter.

Endpoint (verified 2026-07-06):
GET https://mainnet.zklighter.elliot.ai/api/v1/funding-rates
returns funding_rates[] covering MULTIPLE exchanges (lighter, binance,
bybit, hyperliquid); we keep only ``exchange == "lighter"`` rows here.

Rate basis evidence: the endpoint reported hyperliquid BTC as 0.0001
while Hyperliquid's native hourly rate at the same instant was
0.0000125 (= 0.0001 / 8), so rates here are normalized to an 8h basis.

No mark price or open interest in this payload.
"""
from __future__ import annotations

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

FUNDING_RATES_URL = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"
INTERVAL_HOURS = 8.0


@register
class LighterAdapter(VenueAdapter):
    name = "lighter"

    def fetch(self) -> list[FundingSnapshot]:
        import time

        payload = self._get(FUNDING_RATES_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        seen: set[str] = set()
        for row in payload["funding_rates"]:
            if row.get("exchange") != "lighter":
                continue
            if row["symbol"] in seen:
                continue
            seen.add(row["symbol"])
            snap = make_snapshot(
                venue="lighter",
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

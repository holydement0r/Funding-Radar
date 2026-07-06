"""Paradex adapter.

Endpoint (verified 2026-07-06):
GET https://api.prod.paradex.trade/v1/markets/summary?market=ALL
returns results[] mixing perps and options; only ``*-PERP`` symbols carry
usable ``funding_rate`` (8h basis per Paradex docs). ``open_interest`` is
coin-denominated (multiply by mark_price).
"""
from __future__ import annotations

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

SUMMARY_URL = "https://api.prod.paradex.trade/v1/markets/summary?market=ALL"
INTERVAL_HOURS = 8.0


@register
class ParadexAdapter(VenueAdapter):
    name = "paradex"

    def fetch(self) -> list[FundingSnapshot]:
        import time

        payload = self._get(SUMMARY_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        for row in payload["results"]:
            if not row["symbol"].endswith("-PERP"):
                continue
            if not row.get("funding_rate"):
                continue
            mark_price = float(row["mark_price"]) if row.get("mark_price") else None
            oi_usd = None
            if mark_price is not None and row.get("open_interest"):
                oi_usd = float(row["open_interest"]) * mark_price
            snap = make_snapshot(
                venue="paradex",
                raw_symbol=row["symbol"],
                rate=float(row["funding_rate"]),
                interval_hours=INTERVAL_HOURS,
                mark_price=mark_price,
                oi_usd=oi_usd,
                next_ts=None,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

"""Extended (extended.exchange) adapter.

Endpoint (verified 2026-07-06):
GET https://api.starknet.extended.exchange/api/v1/info/markets
returns data[] of markets with a ``marketStats`` block carrying
``fundingRate`` (1h basis), ``markPrice``, and ``openInterest`` which is
already USD-denominated (verified: openInterestBase * markPrice matches).
"""
from __future__ import annotations

import time

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

MARKETS_URL = "https://api.starknet.extended.exchange/api/v1/info/markets"
INTERVAL_HOURS = 1.0


@register
class ExtendedAdapter(VenueAdapter):
    name = "extended"

    def fetch(self) -> list[FundingSnapshot]:
        payload = self._get(MARKETS_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        for market in payload["data"]:
            if market.get("status") != "ACTIVE":
                continue
            stats = market.get("marketStats") or {}
            rate = stats.get("fundingRate")
            if rate in (None, ""):
                continue
            mark = float(stats["markPrice"]) if stats.get("markPrice") else None
            oi_usd = float(stats["openInterest"]) if stats.get("openInterest") else None
            snap = make_snapshot(
                venue="extended",
                raw_symbol=market["name"],
                rate=float(rate),
                interval_hours=INTERVAL_HOURS,
                mark_price=mark,
                oi_usd=oi_usd,
                next_ts=None,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

"""dYdX v4 adapter.

Endpoint (verified 2026-07-06):
GET https://indexer.dydx.trade/v4/perpetualMarkets
returns markets{ticker: {...}} where ``nextFundingRate`` is the HOURLY
rate (dYdX funds hourly; ``defaultFundingRate1H`` confirms the basis).
``openInterest`` is base-denominated (multiply by oraclePrice).
"""
from __future__ import annotations

import time

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

MARKETS_URL = "https://indexer.dydx.trade/v4/perpetualMarkets"
INTERVAL_HOURS = 1.0


@register
class DydxAdapter(VenueAdapter):
    name = "dydx"

    def fetch(self) -> list[FundingSnapshot]:
        payload = self._get(MARKETS_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        for market in payload["markets"].values():
            if market.get("status") != "ACTIVE":
                continue
            rate = market.get("nextFundingRate")
            if rate in (None, ""):
                continue
            oracle = float(market["oraclePrice"]) if market.get("oraclePrice") else None
            oi_usd = None
            if oracle is not None and market.get("openInterest"):
                oi_usd = float(market["openInterest"]) * oracle
            snap = make_snapshot(
                venue="dydx",
                raw_symbol=market["ticker"],
                rate=float(rate),
                interval_hours=INTERVAL_HOURS,
                mark_price=oracle,
                oi_usd=oi_usd,
                next_ts=None,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

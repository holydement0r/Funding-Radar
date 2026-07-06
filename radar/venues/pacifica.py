"""Pacifica adapter.

Endpoint (verified 2026-07-06):
GET https://api.pacifica.fi/api/v1/info/prices
returns data[] with ``symbol`` (bare, e.g. "BTC"), ``funding`` (HOURLY
rate), ``mark``, and ``open_interest`` (base-denominated, multiply by
mark for USD).
"""
from __future__ import annotations

import time

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

PRICES_URL = "https://api.pacifica.fi/api/v1/info/prices"
INTERVAL_HOURS = 1.0


@register
class PacificaAdapter(VenueAdapter):
    name = "pacifica"

    def fetch(self) -> list[FundingSnapshot]:
        payload = self._get(PRICES_URL)
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: dict, now: int) -> list[FundingSnapshot]:
        snapshots = []
        for row in payload["data"]:
            rate = row.get("funding")
            if rate in (None, ""):
                continue
            mark = float(row["mark"]) if row.get("mark") else None
            oi_usd = None
            if mark is not None and row.get("open_interest"):
                oi_usd = float(row["open_interest"]) * mark
            snap = make_snapshot(
                venue="pacifica",
                raw_symbol=row["symbol"],
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

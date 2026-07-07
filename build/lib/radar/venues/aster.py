"""Aster adapter (Binance-compatible futures API).

Endpoints (verified 2026-07-06):
- GET https://fapi.asterdex.com/fapi/v1/premiumIndex — all markets,
  ``lastFundingRate`` on an 8h default interval, ``nextFundingTime`` ms.
- GET https://fapi.asterdex.com/fapi/v1/fundingInfo — per-symbol interval
  overrides (``fundingIntervalHours``), Binance-style; only non-default
  symbols are listed. Missing endpoint tolerated (defaults apply).

Aster lists both USD- and USDT-quoted markets for ~47 coins; both would
normalize to the same symbol, so the USDT market wins on collision
(deeper liquidity as a rule).
"""
from __future__ import annotations

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

PREMIUM_INDEX_URL = "https://fapi.asterdex.com/fapi/v1/premiumIndex"
FUNDING_INFO_URL = "https://fapi.asterdex.com/fapi/v1/fundingInfo"
DEFAULT_INTERVAL_HOURS = 8.0


@register
class AsterAdapter(VenueAdapter):
    name = "aster"

    def fetch(self) -> list[FundingSnapshot]:
        import time

        payload = self._get(PREMIUM_INDEX_URL)
        overrides: dict[str, float] = {}
        try:
            for row in self._get(FUNDING_INFO_URL):
                if row.get("fundingIntervalHours"):
                    overrides[row["symbol"]] = float(row["fundingIntervalHours"])
        except Exception:  # noqa: BLE001 - overrides are best-effort
            pass
        return self._parse(payload, int(time.time()), interval_overrides=overrides)

    @staticmethod
    def _parse(
        payload: list, now: int, *, interval_overrides: dict[str, float]
    ) -> list[FundingSnapshot]:
        # USDT market beats USD market for the same base coin.
        rows: dict[str, dict] = {}
        for row in payload:
            raw = row["symbol"]
            base = raw[:-4] if raw.endswith("USDT") else raw[:-3] if raw.endswith("USD") else raw
            current = rows.get(base)
            if current is None or (raw.endswith("USDT") and not current["symbol"].endswith("USDT")):
                rows[base] = row

        snapshots = []
        for row in rows.values():
            next_ts = int(row["nextFundingTime"]) // 1000 if row.get("nextFundingTime") else None
            snap = make_snapshot(
                venue="aster",
                raw_symbol=row["symbol"],
                rate=float(row["lastFundingRate"] or 0.0),
                interval_hours=interval_overrides.get(row["symbol"], DEFAULT_INTERVAL_HOURS),
                mark_price=float(row["markPrice"]) if row.get("markPrice") else None,
                oi_usd=None,  # premiumIndex carries no open interest
                next_ts=next_ts,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

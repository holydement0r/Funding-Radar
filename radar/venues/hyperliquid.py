"""Hyperliquid adapter.

Endpoint (verified 2026-07-06): POST https://api.hyperliquid.xyz/info
with body {"type": "metaAndAssetCtxs"} returns [meta, assetCtxs] where
meta.universe[i] aligns with assetCtxs[i] by index. ``funding`` is the
HOURLY rate; ``openInterest`` is coin-denominated (multiply by markPx).
"""
from __future__ import annotations

from radar.models import FundingSnapshot
from radar.normalize import make_snapshot
from radar.venues import register
from radar.venues.base import VenueAdapter

INFO_URL = "https://api.hyperliquid.xyz/info"
INTERVAL_HOURS = 1.0


@register
class HyperliquidAdapter(VenueAdapter):
    name = "hyperliquid"

    def fetch(self) -> list[FundingSnapshot]:
        import time

        payload = self._post(INFO_URL, json={"type": "metaAndAssetCtxs"})
        return self._parse(payload, int(time.time()))

    @staticmethod
    def _parse(payload: list, now: int) -> list[FundingSnapshot]:
        meta, ctxs = payload
        snapshots = []
        for market, ctx in zip(meta["universe"], ctxs):
            if market.get("isDelisted"):
                continue
            mark_price = float(ctx["markPx"]) if ctx.get("markPx") else None
            oi_usd = None
            if mark_price is not None and ctx.get("openInterest"):
                oi_usd = float(ctx["openInterest"]) * mark_price
            snap = make_snapshot(
                venue="hyperliquid",
                raw_symbol=market["name"],
                rate=float(ctx["funding"]),
                interval_hours=INTERVAL_HOURS,
                mark_price=mark_price,
                oi_usd=oi_usd,
                next_ts=None,
                now=now,
            )
            if snap is not None:
                snapshots.append(snap)
        return snapshots

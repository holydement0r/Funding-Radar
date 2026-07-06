"""Funding Radar Apify actor.

Thin wrapper over the radar core library. Fetches live perp-DEX funding
rates (mode="rates") or fee-adjusted funding-arb opportunities
(mode="arb"), pushes each as a dataset item, and charges per result.
"""
from __future__ import annotations

import dataclasses

from apify import Actor

from radar.arb import find_opportunities
from radar.collect import collect_all
from radar.venues import all_adapters


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        mode = inp.get("mode", "arb")
        symbols = {s.upper() for s in inp.get("symbols", [])}
        venues = set(inp.get("venues", []))
        min_net_apr = float(inp.get("minNetApr", 0.10))
        require_oi = bool(inp.get("requireOi", True))

        # The per-run base fee is Apify's built-in "apify-actor-start" event,
        # charged automatically by the platform. We only charge per result
        # item below (event "result-item").

        adapters = all_adapters()
        if venues:
            adapters = [a for a in adapters if a.name in venues]
        result = collect_all(adapters)
        Actor.log.info(
            "collected %d snapshots, failed=%s",
            len(result.snapshots), result.failed_venues,
        )

        if mode == "rates":
            rows = [
                dataclasses.asdict(s) for s in result.snapshots
                if not symbols or s.symbol in symbols
            ]
        elif mode == "arb":
            opps = find_opportunities(
                result.snapshots, min_net_apr=min_net_apr, require_oi=require_oi
            )
            rows = [
                dataclasses.asdict(o) for o in opps
                if not symbols or o.symbol in symbols
            ]
        else:
            raise ValueError(f"unknown mode: {mode!r} (expected 'rates' or 'arb')")

        Actor.log.info("returning %d %s rows", len(rows), mode)
        for row in rows:
            charge = await Actor.push_data(row, "result-item")
            if charge is not None and getattr(charge, "event_charge_limit_reached", False):
                Actor.log.info("charge limit reached; stopping")
                break

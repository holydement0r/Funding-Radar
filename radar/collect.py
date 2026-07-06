"""Run all venue adapters with per-venue failure isolation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from radar.models import FundingSnapshot
from radar.venues.base import VenueAdapter

log = logging.getLogger(__name__)


@dataclass
class CollectResult:
    snapshots: list[FundingSnapshot] = field(default_factory=list)
    failed_venues: list[str] = field(default_factory=list)


def collect_all(adapters: list[VenueAdapter]) -> CollectResult:
    """Fetch every venue; one venue's failure never affects the others."""
    result = CollectResult()
    for adapter in adapters:
        try:
            result.snapshots.extend(adapter.fetch())
        except Exception:  # noqa: BLE001 - isolation is the contract (spec section 4)
            log.warning("venue %s failed", adapter.name, exc_info=True)
            result.failed_venues.append(adapter.name)
    return result

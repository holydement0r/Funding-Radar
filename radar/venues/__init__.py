"""Venue adapter registry. Each adapter module registers itself on import."""
from __future__ import annotations

from radar.venues.base import VenueAdapter

REGISTRY: dict[str, type[VenueAdapter]] = {}


def register(cls: type[VenueAdapter]) -> type[VenueAdapter]:
    REGISTRY[cls.name] = cls
    return cls


def all_adapters() -> list[VenueAdapter]:
    """Instantiate every registered adapter (imports trigger registration)."""
    # Import adapter modules here so REGISTRY is populated exactly once.
    from radar.venues import aster, hyperliquid, lighter, paradex  # noqa: F401

    return [cls() for cls in REGISTRY.values()]

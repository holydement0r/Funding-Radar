"""Venue adapter registry. Each adapter module registers itself on import."""
from __future__ import annotations

from radar.venues.base import VenueAdapter

REGISTRY: dict[str, type[VenueAdapter]] = {}


def register(cls: type[VenueAdapter]) -> type[VenueAdapter]:
    REGISTRY[cls.name] = cls
    return cls


def all_adapters() -> list[VenueAdapter]:
    """Instantiate every registered adapter (imports trigger registration)."""
    _import_all_adapter_modules()
    return [cls() for cls in REGISTRY.values()]


def _import_all_adapter_modules() -> None:
    """Import every adapter module in this package so REGISTRY is populated."""
    import importlib
    import pkgutil

    for module in pkgutil.iter_modules(__path__):
        if module.name in ("base",):
            continue
        importlib.import_module(f"{__name__}.{module.name}")

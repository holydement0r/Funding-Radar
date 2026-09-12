"""Fetch the published trailing-mean signal.

The signal needs several days of history to compute, which a one-shot
consumer (the Apify actor, anyone running the library standalone) does not
have. So the cron publishes it: every run writes ``signal.json`` alongside
the history it was computed from, and that file is served from the repo's
`data` branch.

Without it a consumer silently falls back to ranking on the spot spread --
the v1 method, measured at -4.21% realized APR. That fallback still runs,
because a network hiccup should not take the product down, but it is
labelled on every row it produces rather than passed off as the real thing.
"""
from __future__ import annotations

import json
import logging

import httpx

log = logging.getLogger(__name__)

DEFAULT_SIGNAL_URL = (
    "https://raw.githubusercontent.com/holydement0r/Funding-Radar/data/signal.json"
)
RANKING_TRAILING_MEAN = "trailing-mean"
RANKING_SPOT_FALLBACK = "spot-fallback"


def encode(signal: dict[tuple[str, str], float]) -> dict:
    """(symbol, venue) keys are not JSON-representable; join them."""
    return {f"{symbol}|{venue}": apr for (symbol, venue), apr in signal.items()}


def decode(payload: dict) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for key, apr in (payload.get("signal") or {}).items():
        symbol, _, venue = key.partition("|")
        if venue:
            out[(symbol, venue)] = apr
    return out


def fetch(url: str = DEFAULT_SIGNAL_URL, *, timeout: float = 20.0,
          min_keys: int = 50) -> dict[tuple[str, str], float] | None:
    """Return the published signal, or None if it is missing or too thin."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        signal = decode(json.loads(response.text))
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("signal fetch failed (%s): %s", url, exc)
        return None
    if len(signal) < min_keys:
        log.warning("published signal too thin (%d keys)", len(signal))
        return None
    log.info("loaded published signal: %d (symbol, venue) means", len(signal))
    return signal

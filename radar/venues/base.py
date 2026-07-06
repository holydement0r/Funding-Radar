"""Venue adapter base class: HTTP plumbing with timeout and retries."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from radar.models import FundingSnapshot

TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 2


class VenueAdapter(ABC):
    """One exchange's funding-rate source.

    Subclasses set ``name``, implement ``fetch()`` returning normalized
    snapshots, and may raise freely on failure — collect_all isolates them.
    Keep parsing in a pure ``_parse(payload, now)`` function so it can be
    tested against a recorded fixture without network access.
    """

    name: str

    @abstractmethod
    def fetch(self) -> list[FundingSnapshot]:
        ...

    def _get(self, url: str, **kwargs: Any) -> Any:
        return self._request("GET", url, **kwargs)

    def _post(self, url: str, json: Any) -> Any:
        return self._request("POST", url, json=json)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = httpx.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
                response.raise_for_status()
                return response.json()
            except Exception as error:  # noqa: BLE001 - retried, then re-raised
                last_error = error
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)
        raise RuntimeError(f"{self.name}: request failed after retries: {last_error}")

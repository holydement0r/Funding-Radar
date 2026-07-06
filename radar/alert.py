"""Telegram alert selection, dedup state machine, and delivery.

Dedup contract (spec section 3.5): a (symbol, long, short) pair alerts
once when net APR crosses the threshold, then stays suppressed until it
falls below 70% of the threshold (or disappears), which re-arms it.
State is a plain dict persisted by the caller (data/alert_state.json).
"""
from __future__ import annotations

import time

import httpx

from radar.models import ArbOpportunity

REARM_FRACTION = 0.7
SEND_RETRIES = 2


def _key(opp: ArbOpportunity) -> str:
    return f"{opp.symbol}:{opp.long_venue}:{opp.short_venue}"


def select_alerts(
    opps: list[ArbOpportunity],
    state: dict,
    *,
    threshold_apr: float = 0.15,
) -> tuple[list[ArbOpportunity], dict]:
    """Return (opportunities to alert now, next state)."""
    rearm_level = threshold_apr * REARM_FRACTION
    alerts = []
    next_state: dict = {}
    seen = {_key(o): o for o in opps}

    for key, opp in seen.items():
        armed = key not in state
        if opp.net_apr >= threshold_apr:
            if armed:
                alerts.append(opp)
            next_state[key] = {"net_apr": opp.net_apr, "alerted_at": int(time.time())}
        elif opp.net_apr >= rearm_level and not armed:
            next_state[key] = state[key]  # cooled but not re-armed yet
        # below rearm level or absent: key dropped -> re-armed

    return alerts, next_state


def format_alert(opp: ArbOpportunity, site_url: str) -> str:
    """English HTML-mode message for the free channel."""
    oi = f"${opp.min_oi_usd:,.0f}" if opp.min_oi_usd is not None else "n/a"
    return (
        f"⚡ <b>{opp.symbol}</b> funding arb: <b>{opp.net_apr * 100:.1f}%</b> net APR\n"
        f"SHORT {opp.short_venue} ({opp.short_apr * 100:+.1f}%) / "
        f"LONG {opp.long_venue} ({opp.long_apr * 100:+.1f}%)\n"
        f"Min leg OI: {oi} · fees included, 7d hold\n"
        f"{site_url}"
    )


def send_telegram(text: str, *, token: str, chat_id: str) -> bool:
    """POST to the Bot API; never raises (alerts must not break the pipeline)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    for attempt in range(SEND_RETRIES + 1):
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                return True
        except Exception:  # noqa: BLE001 - retried, then reported as False
            pass
        if attempt < SEND_RETRIES:
            time.sleep(2**attempt)
    return False

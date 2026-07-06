"""Pipeline orchestrator: collect -> store latest -> arb -> alert.

Usage: python -m radar.run [--dry-run] [--skip-telegram] [--data-dir data]

--dry-run parses recorded fixtures instead of hitting the network and
implies --skip-telegram; everything else (normalize, arb, alert state)
runs for real so CI can smoke the whole pipeline.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID (alerts skipped if unset),
SITE_URL (link appended to alerts).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys
import time
from pathlib import Path

from radar.alert import format_alert, select_alerts, send_telegram
from radar.arb import find_opportunities
from radar.collect import collect_all
from radar.models import FundingSnapshot
from radar.venues.base import VenueAdapter

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
DEFAULT_SITE_URL = "https://github.com/funding-radar"


class _FixtureAdapter(VenueAdapter):
    """Replays a recorded API response through a real adapter's parser."""

    def __init__(self, name: str, parse):
        self.name = name
        self._parse_fn = parse

    def fetch(self) -> list[FundingSnapshot]:
        payload = json.loads((FIXTURES_DIR / f"{self.name}.json").read_text())
        return self._parse_fn(payload, int(time.time()))


def _fixture_adapters() -> list[VenueAdapter]:
    from radar.venues.aster import AsterAdapter
    from radar.venues.hyperliquid import HyperliquidAdapter
    from radar.venues.lighter import LighterAdapter
    from radar.venues.paradex import ParadexAdapter

    return [
        _FixtureAdapter("hyperliquid", HyperliquidAdapter._parse),
        _FixtureAdapter(
            "aster", lambda p, now: AsterAdapter._parse(p, now, interval_overrides={})
        ),
        _FixtureAdapter("paradex", ParadexAdapter._parse),
        _FixtureAdapter("lighter", LighterAdapter._parse),
    ]


def main(argv: list[str] | None = None, adapters: list[VenueAdapter] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar.run")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if adapters is None:
        if args.dry_run:
            adapters = _fixture_adapters()
        else:
            from radar.venues import all_adapters

            adapters = all_adapters()

    result = collect_all(adapters)
    if not result.snapshots:
        log.error("all venues failed (%s); keeping previous latest.json", result.failed_venues)
        return 1

    opportunities = find_opportunities(result.snapshots)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    latest = {
        "generated_at": int(time.time()),
        "snapshots": [dataclasses.asdict(s) for s in result.snapshots],
        "failed_venues": result.failed_venues,
        "opportunities": [dataclasses.asdict(o) for o in opportunities],
    }
    (data_dir / "latest.json").write_text(json.dumps(latest, indent=1))
    log.info(
        "wrote latest.json: %d snapshots, %d opportunities, failed=%s",
        len(result.snapshots), len(opportunities), result.failed_venues,
    )

    state_path = data_dir / "alert_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    alerts, next_state = select_alerts(opportunities, state)
    state_path.write_text(json.dumps(next_state, indent=1))

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    site_url = os.environ.get("SITE_URL", DEFAULT_SITE_URL)
    if args.dry_run or args.skip_telegram or not (token and chat_id):
        log.info("telegram skipped; %d alert(s) selected", len(alerts))
    else:
        for opp in alerts:
            ok = send_telegram(format_alert(opp, site_url), token=token, chat_id=chat_id)
            log.info("alert %s -> %s", opp.symbol, "sent" if ok else "FAILED")

    return 0


if __name__ == "__main__":
    sys.exit(main())

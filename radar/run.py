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
from radar.store import load_history_window, prune_history, write_history
from radar.venues.base import VenueAdapter

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
DEFAULT_SITE_URL = "https://github.com/funding-radar"


class _FixtureAdapter(VenueAdapter):
    """Replays a recorded API response through a real adapter's parser."""

    def __init__(self, name: str, parse, fixture: str | None = None):
        self.name = name
        self._parse_fn = parse
        self._fixture = fixture or name

    def fetch(self) -> list[FundingSnapshot]:
        payload = json.loads((FIXTURES_DIR / f"{self._fixture}.json").read_text())
        return self._parse_fn(payload, int(time.time()))


def _fixture_adapters() -> list[VenueAdapter]:
    from radar.venues.aster import AsterAdapter
    from radar.venues.binance_via_lighter import BinanceViaLighterAdapter
    from radar.venues.dydx import DydxAdapter
    from radar.venues.extended import ExtendedAdapter
    from radar.venues.hyperliquid import HyperliquidAdapter
    from radar.venues.lighter import LighterAdapter
    from radar.venues.pacifica import PacificaAdapter
    from radar.venues.paradex import ParadexAdapter

    return [
        _FixtureAdapter("hyperliquid", HyperliquidAdapter._parse),
        _FixtureAdapter(
            "aster", lambda p, now: AsterAdapter._parse(p, now, interval_overrides={})
        ),
        _FixtureAdapter("paradex", ParadexAdapter._parse),
        _FixtureAdapter("lighter", LighterAdapter._parse),
        _FixtureAdapter("binance_via_lighter", BinanceViaLighterAdapter._parse,
                        fixture="lighter"),
        _FixtureAdapter("dydx", DydxAdapter._parse),
        _FixtureAdapter("extended", ExtendedAdapter._parse),
        _FixtureAdapter("pacifica", PacificaAdapter._parse),
    ]


def main(argv: list[str] | None = None, adapters: list[VenueAdapter] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar.run")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--site-out", default=None,
                        help="build the static site into this directory")
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

    if not args.dry_run:
        write_history(result.snapshots, root=str(data_dir))
        pruned = prune_history(root=str(data_dir))
        if pruned:
            log.info("pruned %d old history day(s)", pruned)

    if args.site_out:
        from radar.sitegen import build_site

        history_7d = load_history_window(root=str(data_dir))
        site_url = os.environ.get("SITE_URL", DEFAULT_SITE_URL)
        pages = build_site(latest, history_7d, Path(args.site_out), site_url)
        log.info("built site: %d pages -> %s", pages, args.site_out)

    state_path = data_dir / "alert_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    # Channel credibility: only alert on opportunities whose both legs have
    # verified open interest. No-OI pairs are mostly thin/stale noise with
    # absurd APRs; they stay on the site's "unverified" table only.
    alertable = [o for o in opportunities if o.min_oi_usd is not None]
    threshold = float(os.environ.get("ALERT_THRESHOLD_APR") or "0.10")
    alerts, next_state = select_alerts(alertable, state, threshold_apr=threshold)
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

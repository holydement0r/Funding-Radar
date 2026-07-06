"""Static SEO site generator (Jinja2, pure HTML/CSS, zero JS).

Consumes the pipeline's latest.json plus a 7-day history window and emits
a directory tree deployable to GitHub Pages:

    index.html                          top arbitrage opportunities
    funding-rates/<SYMBOL>/index.html   cross-venue table + 7d history
    exchanges/index.html                exchange directory
    exchanges/<venue>/index.html        all coins for one venue
    compare/<a>-vs-<b>/index.html       venue pair (top 8 by shared coins)
    sitemap.xml, robots.txt, style.css
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

TELEGRAM_URL = os.environ.get("TELEGRAM_URL", "https://t.me/fundingradar")
APIFY_URL = os.environ.get("APIFY_URL", "https://apify.com/")
MAX_COMPARE_PAGES = 8


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    v = round(x * 100, 2)
    if v == int(v):
        return f"{v:.1f}%"
    return f"{('%.2f' % v).rstrip('0')}%"


def _usd(x: float | None) -> str:
    if x is None:
        return "n/a"
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"${x / 1_000:.1f}K"
    return f"${x:,.2f}"


def _human(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts))


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    env.globals["pct"] = _pct
    env.globals["usd"] = _usd
    return env


def build_site(latest: dict, history_7d: dict, out_dir: Path, site_url: str) -> int:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = _env()

    snapshots = latest.get("snapshots", [])
    opportunities = latest.get("opportunities", [])
    failed = set(latest.get("failed_venues", []))
    venues = sorted({s["venue"] for s in snapshots})
    generated_human = _human(latest.get("generated_at", int(time.time())))

    base_ctx = dict(
        site_url=site_url.rstrip("/"),
        telegram_url=TELEGRAM_URL,
        apify_url=APIFY_URL,
        venue_count=len(venues),
        generated_human=generated_human,
    )

    def render(template: str, path: Path, rel: str, canonical: str, **ctx) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        html = env.get_template(template).render(rel=rel, canonical=canonical, **base_ctx, **ctx)
        path.write_text(html)

    urls: list[str] = []
    pages = 0

    # Index
    render("index.html.j2", out_dir / "index.html", "", "/",
           opportunities=opportunities, venues=venues)
    urls.append("/")
    pages += 1

    # Per-coin pages
    by_symbol: dict[str, list[dict]] = {}
    for s in snapshots:
        by_symbol.setdefault(s["symbol"], []).append(s)
    for symbol, rows in sorted(by_symbol.items()):
        rows = sorted(rows, key=lambda r: r["apr"], reverse=True)
        hist = history_7d.get(symbol, [])
        hist_points = [{"human": _human(p["t"]), "rates": p["rates"]} for p in hist]
        hist_venues = sorted({v for p in hist for v in p["rates"]})
        render("coin.html.j2", out_dir / "funding-rates" / symbol / "index.html",
               "../../", f"/funding-rates/{symbol}/",
               symbol=symbol, rows=rows, venue_list=", ".join(r["venue"] for r in rows),
               history=hist_points, history_venues=hist_venues)
        urls.append(f"/funding-rates/{symbol}/")
        pages += 1

    # Per-venue pages
    by_venue: dict[str, list[dict]] = {}
    for s in snapshots:
        by_venue.setdefault(s["venue"], []).append(s)
    counts = {v: len(by_venue.get(v, [])) for v in venues}
    for venue, rows in sorted(by_venue.items()):
        rows = sorted(rows, key=lambda r: r["apr"], reverse=True)
        render("venue.html.j2", out_dir / "exchanges" / venue / "index.html",
               "../../", f"/exchanges/{venue}/",
               venue=venue, rows=rows, stale=venue in failed)
        urls.append(f"/exchanges/{venue}/")
        pages += 1

    # Compare pages: venue pairs ranked by shared-coin count
    pairs = _top_pairs(by_symbol, venues)
    for a, b in pairs:
        rows = _compare_rows(by_symbol, a, b)
        render("compare.html.j2", out_dir / "compare" / f"{a}-vs-{b}" / "index.html",
               "../../", f"/compare/{a}-vs-{b}/",
               venue_a=a, venue_b=b, rows=rows)
        urls.append(f"/compare/{a}-vs-{b}/")
        pages += 1

    # Exchanges directory index
    render("exchanges_index.html.j2", out_dir / "exchanges" / "index.html",
           "../", "/exchanges/",
           venues=venues, counts=counts, venue_list=", ".join(venues), pairs=pairs)
    urls.append("/exchanges/")
    pages += 1

    # Assets + sitemap + robots
    shutil.copyfile(TEMPLATES_DIR / "style.css", out_dir / "style.css")
    _write_sitemap(out_dir, site_url.rstrip("/"), urls)
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site_url.rstrip('/')}/sitemap.xml\n"
    )
    (out_dir / ".nojekyll").write_text("")

    return pages


def _top_pairs(by_symbol: dict, venues: list[str]) -> list[tuple[str, str]]:
    scored = []
    for i, a in enumerate(venues):
        for b in venues[i + 1:]:
            shared = sum(
                1 for rows in by_symbol.values()
                if any(r["venue"] == a for r in rows) and any(r["venue"] == b for r in rows)
            )
            if shared:
                scored.append((shared, a, b))
    scored.sort(reverse=True)
    return [(a, b) for _, a, b in scored[:MAX_COMPARE_PAGES]]


def _compare_rows(by_symbol: dict, a: str, b: str) -> list[dict]:
    rows = []
    for symbol, snaps in by_symbol.items():
        ra = next((s for s in snaps if s["venue"] == a), None)
        rb = next((s for s in snaps if s["venue"] == b), None)
        if ra and rb:
            rows.append({"symbol": symbol, "apr_a": ra["apr"], "apr_b": rb["apr"],
                         "spread": abs(ra["apr"] - rb["apr"])})
    rows.sort(key=lambda r: r["spread"], reverse=True)
    return rows


def _write_sitemap(out_dir: Path, site_url: str, urls: list[str]) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(f"<url><loc>{site_url}{u}</loc></url>")
    lines.append("</urlset>")
    (out_dir / "sitemap.xml").write_text("\n".join(lines) + "\n")

# Funding Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perp-DEX funding-rate aggregation engine feeding three zero-marginal-cost revenue channels (Telegram alerts, Apify actor, SEO static site).

**Architecture:** Single Python package `radar/` with isolated venue adapters → normalized `FundingSnapshot` stream → fee-adjusted arbitrage engine → three thin output heads (Telegram, static site, Apify). GitHub Actions cron every 30 min is the only runtime; git branches are the only storage.

**Tech Stack:** Python 3.10, httpx, Jinja2, pytest. No database, no server.

**Spec:** `docs/superpowers/specs/2026-07-06-funding-radar-design.md` — read it first; error-handling table (§4) and test strategy (§5) apply to every task.

## Global Constraints

- Python 3.10 compatible (user machine runs 3.10.12). No 3.11+ syntax.
- Dependencies limited to: httpx, jinja2, pytest (dev). Stdlib otherwise.
- Zero servers. Everything runs in GitHub Actions or Apify.
- Single-venue failure must never fail a run; all-venue failure must never overwrite `data/latest.json`.
- Money-math (normalize, arb) requires explicit unit tests before implementation (TDD, non-negotiable).
- All site/README/alert copy in English (overseas market).
- Adapter rule: NEVER invent API fields. Before writing an adapter, hit the real endpoint, save the real response as a fixture in `tests/fixtures/<venue>.json`, then code against the fixture.
- Commit after every green test cycle. Commit messages end with `Co-Authored-By:` line for the executing model.

## Model Assignment

| Tasks | Model | Rationale |
|-------|-------|-----------|
| 1–10 (P0 core engine) | **Fable (this session)** | Money-correctness core, framework design |
| 11–15 (P1 pipeline & site) | **Opus** | Pattern-following against P0 exemplars |
| 16–17 (P2 monetization) | **Opus** | Integration work |
| 18–20 (copy, fees, runbook) | **Sonnet** | Text-heavy, low-risk |

## Verified Endpoint Reference (probed 2026-07-06, real responses)

| Venue | Endpoint | Key fields | Notes |
|-------|----------|-----------|-------|
| Hyperliquid | `POST https://api.hyperliquid.xyz/info` body `{"type":"metaAndAssetCtxs"}` | `[0].universe[i].name`, `[1][i].funding`, `[1][i].markPx`, `[1][i].openInterest` | universe/assetCtxs align by index; `funding` is HOURLY rate; skip `isDelisted` |
| Aster | `GET https://fapi.asterdex.com/fapi/v1/premiumIndex` | `symbol` (e.g. `SUSHIUSDT`), `lastFundingRate`, `markPrice`, `nextFundingTime` | Binance-compatible; interval default 8h — check `/fapi/v1/fundingInfo` for per-symbol overrides during implementation |
| Paradex | `GET https://api.prod.paradex.trade/v1/markets/summary?market=ALL` | `results[].symbol`, `funding_rate`, `mark_price`, `open_interest` | Response mixes options — keep only symbols ending `-PERP`; verify funding period (docs say 8h) against fixture |
| Lighter | `GET https://mainnet.zklighter.elliot.ai/api/v1/funding-rates` | `funding_rates[].exchange`, `.symbol`, `.rate` | Returns MULTIPLE exchanges (binance, lighter, …). Filter `exchange=="lighter"` for Lighter itself. BONUS: `exchange=="binance"` rows = free geo-unblocked Binance data — expose as pseudo-venue `binance_via_lighter` (P1, Task 12) |

---

## P0 — Core Engine (Fable, this session)

### Task 1: Scaffolding + data models

**Files:**
- Create: `pyproject.toml`, `radar/__init__.py`, `radar/models.py`, `tests/test_models.py`, `.gitignore`

**Interfaces (Produces):**
```python
@dataclass(frozen=True)
class FundingSnapshot:
    venue: str; symbol: str; rate: float; interval_hours: float
    apr: float; mark_price: float | None; open_interest_usd: float | None
    next_funding_ts: int | None; fetched_at: int

@dataclass(frozen=True)
class ArbOpportunity:
    symbol: str; long_venue: str; short_venue: str
    long_apr: float; short_apr: float; spread_apr: float; net_apr: float
    min_oi_usd: float | None
```

- [ ] Steps: failing test for `FundingSnapshot` construction + frozen-ness → run (FAIL) → implement `models.py` → run (PASS) → commit `feat: project scaffolding and data models`.

### Task 2: normalize.py (money-correctness core #1)

**Files:** Create `radar/normalize.py`, `tests/test_normalize.py`

**Interfaces (Produces):**
```python
def normalize_symbol(raw: str, venue: str) -> str | None   # "SUSHIUSDT"→"SUSHI", "BTC-USD-PERP"→"BTC", "1000PEPE"→"PEPE" (rate unaffected), unknown pattern→None
def annualize(rate: float, interval_hours: float) -> float # rate * (8760 / interval_hours)
def make_snapshot(venue, raw_symbol, rate, interval_hours, mark_price, oi_usd, next_ts, now) -> FundingSnapshot | None  # None if symbol unmappable or |apr| > 10.0 (1000%, dirty-data guard, spec §4)
```

- [ ] TDD cases (write ALL before implementing): hourly 0.0000125→apr≈0.1095; 8h 0.0001→apr≈0.1095; negative rates; `SUSHIUSDT`/`GNSUSD`/`BTC-USD-PERP`/`1000PEPE`/`kSHIB` mappings; unmappable→None; apr>10→None.
- [ ] Implement → PASS → commit `feat: symbol normalization and APR math`.

### Task 3: Adapter framework

**Files:** Create `radar/venues/__init__.py` (REGISTRY), `radar/venues/base.py`, `radar/collect.py`, `tests/test_collect.py`

**Interfaces (Produces):**
```python
class VenueAdapter(ABC):
    name: str
    def fetch(self) -> list[FundingSnapshot]  # implemented by subclass; raises on failure
# base provides: self._get(url, **kw) / self._post(url, json) — httpx, timeout=10s, 2 retries exponential backoff

def collect_all(adapters: list[VenueAdapter]) -> CollectResult
# CollectResult: snapshots: list[FundingSnapshot], failed_venues: list[str]
# one adapter raising → venue in failed_venues, others unaffected (spec §4)
REGISTRY: dict[str, type[VenueAdapter]]
```

- [ ] TDD with fake adapters (one good, one raising): isolation, failed_venues populated, all-fail returns empty snapshots + all names in failed_venues → implement → commit `feat: venue adapter framework with failure isolation`.

### Tasks 4–7: Flagship adapters (Hyperliquid, Aster, Paradex, Lighter)

One task per venue. Identical shape — repeat for each:

**Files:** Create `radar/venues/<venue>.py`, `tests/fixtures/<venue>.json`, `tests/test_venue_<venue>.py`

- [ ] Step 1: `curl` the real endpoint (see Verified Endpoint Reference), save raw response as fixture. Trim to ≤50 markets if huge, keep structure intact.
- [ ] Step 2: failing test — feed fixture through adapter's parse method, assert: ≥1 snapshot; a known symbol (BTC or ETH) present with plausible apr (|apr| < 10); venue field correct; interval correct (Hyperliquid=1h, Aster=8h w/ fundingInfo override check, Paradex=verify, Lighter=verify against docs/fixture).
- [ ] Step 3: implement adapter — parse-only pure function `_parse(payload, now) -> list[FundingSnapshot]` + thin `fetch()` calling `self._get/_post` then `_parse`. Register in REGISTRY.
- [ ] Step 4: PASS → live smoke `python -c "from radar.venues.<venue> import <V>; print(len(<V>().fetch()))"` → commit `feat: <venue> adapter`.

### Task 8: fees.py + arb engine (money-correctness core #2)

**Files:** Create `radar/fees.py`, `radar/arb.py`, `tests/test_arb.py`

**Interfaces (Produces):**
```python
TAKER_FEES: dict[str, float]  # venue -> taker fee (decimal). Initial values from official docs; Sonnet maintains (Task 18)
def find_opportunities(snapshots, *, min_oi_usd=500_000.0, holding_days=7.0, min_net_apr=0.0) -> list[ArbOpportunity]
```

Math (spec §3.4, direction already corrected in spec): short the HIGH-funding venue, long the LOW-funding venue.
`spread_apr = apr_short - apr_long` (where `apr_short ≥ apr_long`);
`cost_apr = 2 * (fee_long_venue + fee_short_venue) * (365 / holding_days)`;
`net_apr = spread_apr - cost_apr`. Sort desc by net_apr.

- [ ] TDD cases first: direction correctness (venue A apr=0.5, B apr=-0.1 → short A long B, spread=0.6); fee deduction exact number; OI filter drops thin legs (None OI = drop); stale/missing venue simply absent; same-venue pair never emitted; empty input → empty list.
- [ ] Implement → PASS → commit `feat: fee-adjusted arbitrage engine`.

### Task 9: Telegram alert logic

**Files:** Create `radar/alert.py`, `tests/test_alert.py`

**Interfaces (Produces):**
```python
def select_alerts(opps: list[ArbOpportunity], state: dict, *, threshold_apr=0.15) -> tuple[list[ArbOpportunity], dict]
# dedup: key f"{symbol}:{long_venue}:{short_venue}" in state → suppressed; key resets when net_apr < 0.7*threshold
def format_alert(opp: ArbOpportunity, site_url: str) -> str  # English, HTML parse mode
def send_telegram(text: str, token: str, chat_id: str) -> bool  # POST api.telegram.org, 2 retries, False on final failure (never raises — spec §4)
```

- [ ] TDD: first-seen alerts; repeat suppressed; reset-then-realert state machine; format contains both venues + net APR + link. `send_telegram` tested with monkeypatched httpx only.
- [ ] Implement → PASS → commit `feat: telegram alert selection and dedup`.

### Task 10: Orchestrator + dry-run integration

**Files:** Create `radar/run.py`, `tests/test_run.py`

**Interfaces (Produces):**
```python
def main(argv=None) -> int  # flags: --dry-run (fixture adapters, no network/telegram/write), --skip-telegram
# pipeline: collect_all → write data/latest.json (UNLESS all venues failed → exit 1, keep old file) → find_opportunities → select_alerts → send → save alert_state
# data layout: data/latest.json {"generated_at": ..., "snapshots": [...], "failed_venues": [...], "opportunities": [...]}
```

- [ ] TDD: dry-run exit 0 + latest.json written to tmp dir; all-failed → exit 1 + pre-existing latest.json untouched.
- [ ] Implement → PASS → run `python -m radar.run --dry-run` for real → commit `feat: pipeline orchestrator with dry-run`.
- [ ] P0 exit gate: full `pytest` green; live run `python -m radar.run --skip-telegram` produces real `data/latest.json` with ≥3 venues. Commit data file as sample.

---

## P1 — Pipeline & Site (Opus)

### Task 11: store.py — history + retention

**Files:** Create `radar/store.py`, `tests/test_store.py`; Modify `radar/run.py` (call store after latest.json write)

**Interfaces:** Consumes `CollectResult`. Produces `write_history(snapshots, root="data") -> Path` (writes `data/history/YYYY-MM-DD/HH.json`), `prune_history(root, keep_days=90) -> int`.

- [ ] TDD (tmp_path): file lands at hour path; second write same hour overwrites; prune deletes >90d dirs only. Implement, wire into `run.py` behind `--dry-run` guard, commit `feat: hourly history store with 90-day retention`.

### Task 12: Remaining adapters ×9

Venues: edgeX, dYdX v4, Drift, Extended, Vest, Bluefin, Hibachi, Pacifica, plus pseudo-venue `binance_via_lighter` (filter `exchange=="binance"` in the Lighter payload; separate adapter file reusing Lighter's fetch).

For EACH venue, follow the exact Task 4–7 shape (probe real endpoint → fixture → failing test → parse-only implementation → live smoke → commit). Endpoint discovery order: official API docs → loris.tools network tab → venue Discord. **If an endpoint needs auth or is geo-blocked from a US IP, skip the venue and record why in `docs/venue-notes.md`** — do not burn >30 min per venue. Interval MUST come from docs/fixture evidence, never assumed.

- [ ] One commit per venue: `feat: <venue> adapter`.

### Task 13: sitegen — SEO static site

**Files:** Create `radar/sitegen.py`, `radar/templates/{base,index,coin,venue,compare}.html.j2`, `radar/templates/style.css`, `tests/test_sitegen.py`; Modify `radar/run.py` (add `--site-out` flag)

**Interfaces:** Consumes `data/latest.json` + `data/history/` (7-day window for coin pages). Produces `build_site(latest: dict, history_7d: dict, out_dir: Path, site_url: str) -> int` (page count).

Pages per spec §3.6: `/` top-opportunities table; `/funding-rates/<symbol>/` per-coin cross-venue table + 7d history; `/exchanges/<venue>/`; `/compare/<a>-vs-<b>/` for top-8 venue pairs; `sitemap.xml`, `robots.txt`. Every page: unique `<title>` + meta description containing symbol/venue names; Telegram + Apify CTA block in `base.html.j2`. Pure HTML+CSS, zero JS.

- [ ] TDD smoke per spec §5: build from sample latest.json → expected file paths exist, BTC page contains venue names and APR strings, sitemap lists every generated URL. Commit `feat: static site generator`.

### Task 14: GitHub Actions — cron + tests + Pages

**Files:** Create `.github/workflows/cron.yml`, `.github/workflows/test.yml`

- `test.yml`: on push/PR → `pip install -e .[dev]` → `pytest`.
- `cron.yml`: `schedule: "*/30 * * * *"` + `workflow_dispatch`; checkout main + worktree `data` branch; `python -m radar.run` (secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`); commit+push `data` branch; `build_site` → deploy `gh-pages` (actions/deploy-pages or peaceiris); on failure → curl Telegram sendMessage to `TELEGRAM_ADMIN_CHAT_ID` (spec §3.8).
- [ ] Verify with `workflow_dispatch` run on GitHub before enabling schedule. Commit `ci: cron pipeline and pages deploy`.

### Task 15: End-to-end launch checklist (needs user's 1.5h, spec §7)

- [ ] User: create public GitHub repo + push; BotFather bot + channel + secrets. Then: manual dispatch green → channel receives first alert (temporarily lower threshold to force one) → Pages URL live → restore threshold. Record URLs in README. Commit `docs: launch state`.

---

## P2 — Monetization (Opus)

### Task 16: Apify actor

**Files:** Create `apify/` (Apify Python SDK project: `.actor/actor.json`, `.actor/pay_per_event.json`, `src/main.py`, `Dockerfile`, `README.md`)

Input schema: `{"mode": "rates"|"arb", "symbols": [...], "venues": [...]}`. Implementation: import `radar` (install repo as dependency), live `collect_all` filtered to requested venues → push each snapshot/opportunity as one dataset item → charge per event via `Actor.charge`. Follow current Apify pay-per-event docs at implementation time (rental model dead Oct 2026 — spec §1 research).

- [ ] Local test with `apify run`, then deploy `apify push`, publish with Sonnet's listing copy (Task 19). Commit `feat: apify actor`.

### Task 17: Premium alert tier

Deferred design (spec §3.5): lower threshold + earlier push to a private group; payment via Telegram Stars. **Gate: do not build until free channel > 200 subscribers.** Brainstorm anew when gate hit.

---

## Sonnet Tasks (ongoing)

### Task 18: fees.py verification
- [ ] For every venue in REGISTRY, verify taker fee against official docs; update `TAKER_FEES` with source-URL comment per line. Re-run `pytest tests/test_arb.py`. Commit `chore: verify venue taker fees`.

### Task 19: Copy pack (English)
- [ ] Repo README (what/why/data-source table/link to site+channel+actor); Apify Store listing (title ≤65 chars with "Funding Rate API", features, 3 output examples, pricing rationale vs Coinglass $29/mo); Telegram channel pinned intro; site footer/about blurb. No em dashes, plain developer tone. Commit `docs: marketing copy pack`.

### Task 20: Runbook
- [ ] `docs/runbook.md`: how to add a venue (Task 4–7 recipe), how to read failure DMs, monthly checklist (fees, dead venues, prune check), threshold tuning. Commit `docs: maintenance runbook`.

---

## Self-Review Notes

- Spec coverage: §3.1→T3–7,12; §3.2→T1; §3.3→T11; §3.4→T8; §3.5→T9,17; §3.6→T13; §3.7→T16; §3.8→T14; §4 woven into T3,8,9,10; §5 per-task TDD; §7→T15. No gaps.
- Type consistency: `FundingSnapshot`/`ArbOpportunity`/`CollectResult` signatures repeated verbatim where consumed.
- Deliberate deviations from full-code-in-plan rule: adapter bodies (Tasks 4–7, 12) intentionally specified as protocol not code — fabricating unverified API parsing in a plan is worse than mandating fixture-first verification. P0 executes in-session immediately after this plan, so P0 exemplar code becomes the living reference for Task 12.

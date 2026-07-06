from radar.collect import collect_all
from radar.models import FundingSnapshot
from radar.venues.base import VenueAdapter


def snap(venue, symbol="BTC"):
    return FundingSnapshot(
        venue=venue, symbol=symbol, rate=0.0001, interval_hours=8.0,
        apr=0.1095, mark_price=None, open_interest_usd=None,
        next_funding_ts=None, fetched_at=1783326670,
    )


class GoodAdapter(VenueAdapter):
    name = "good"

    def fetch(self):
        return [snap("good"), snap("good", "ETH")]


class BrokenAdapter(VenueAdapter):
    name = "broken"

    def fetch(self):
        raise RuntimeError("api exploded")


class EmptyAdapter(VenueAdapter):
    name = "empty"

    def fetch(self):
        return []


def test_all_good_adapters_merge_snapshots():
    result = collect_all([GoodAdapter(), GoodAdapter()])
    assert len(result.snapshots) == 4
    assert result.failed_venues == []


def test_one_broken_adapter_is_isolated():
    result = collect_all([GoodAdapter(), BrokenAdapter()])
    assert len(result.snapshots) == 2
    assert result.failed_venues == ["broken"]


def test_all_broken_returns_empty_and_all_failed():
    result = collect_all([BrokenAdapter(), BrokenAdapter()])
    assert result.snapshots == []
    assert result.failed_venues == ["broken", "broken"]


def test_empty_result_is_not_a_failure():
    result = collect_all([EmptyAdapter()])
    assert result.snapshots == []
    assert result.failed_venues == []


def test_registry_contains_registered_adapters():
    from radar.venues import REGISTRY

    assert isinstance(REGISTRY, dict)

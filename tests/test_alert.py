import httpx
import pytest

from radar.alert import format_alert, select_alerts, send_telegram
from radar.models import ArbOpportunity


def opp(symbol="BTC", long_v="paradex", short_v="hyperliquid", net=0.20):
    return ArbOpportunity(
        symbol=symbol, long_venue=long_v, short_venue=short_v,
        long_apr=-0.05, short_apr=net + 0.05, spread_apr=net + 0.10,
        net_apr=net, min_oi_usd=2_000_000.0,
    )


class TestSelectAlerts:
    def test_first_sighting_alerts(self):
        alerts, state = select_alerts([opp(net=0.20)], {}, threshold_apr=0.15)
        assert len(alerts) == 1
        assert "BTC:paradex:hyperliquid" in state

    def test_below_threshold_not_alerted(self):
        alerts, state = select_alerts([opp(net=0.10)], {}, threshold_apr=0.15)
        assert alerts == []
        assert state == {}

    def test_repeat_suppressed(self):
        _, state = select_alerts([opp(net=0.20)], {}, threshold_apr=0.15)
        alerts, _ = select_alerts([opp(net=0.25)], state, threshold_apr=0.15)
        assert alerts == []

    def test_reset_below_70pct_then_realert(self):
        _, state = select_alerts([opp(net=0.20)], {}, threshold_apr=0.15)
        # drops under 0.7 * 0.15 = 0.105 -> key cleared
        alerts, state = select_alerts([opp(net=0.09)], state, threshold_apr=0.15)
        assert alerts == []
        assert state == {}
        # spikes again -> re-alert
        alerts, state = select_alerts([opp(net=0.30)], state, threshold_apr=0.15)
        assert len(alerts) == 1

    def test_between_70pct_and_threshold_keeps_suppression(self):
        _, state = select_alerts([opp(net=0.20)], {}, threshold_apr=0.15)
        alerts, state = select_alerts([opp(net=0.12)], state, threshold_apr=0.15)
        assert alerts == []
        assert "BTC:paradex:hyperliquid" in state  # still armed, no re-alert

    def test_absent_opportunity_resets(self):
        _, state = select_alerts([opp(net=0.20)], {}, threshold_apr=0.15)
        alerts, state = select_alerts([], state, threshold_apr=0.15)
        assert state == {}

    def test_different_pairs_tracked_independently(self):
        alerts, state = select_alerts(
            [opp(net=0.20), opp(symbol="ETH", net=0.30)], {}, threshold_apr=0.15
        )
        assert len(alerts) == 2
        assert len(state) == 2


class TestFormatAlert:
    def test_contains_essentials(self):
        text = format_alert(opp(net=0.20), "https://example.com")
        assert "BTC" in text
        assert "hyperliquid" in text and "paradex" in text
        assert "20.0%" in text          # net apr
        assert "https://example.com" in text
        assert "SHORT" in text and "LONG" in text

    def test_handles_none_oi(self):
        o = ArbOpportunity(
            symbol="ETH", long_venue="lighter", short_venue="aster",
            long_apr=0.0, short_apr=0.3, spread_apr=0.3, net_apr=0.25,
            min_oi_usd=None,
        )
        text = format_alert(o, "https://example.com")
        assert "ETH" in text


class TestSendTelegram:
    def test_success(self, monkeypatch):
        calls = {}

        def fake_post(url, **kw):
            calls["url"] = url
            calls["json"] = kw.get("json")
            return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        assert send_telegram("hello", token="TOK", chat_id="@chan") is True
        assert "botTOK" in calls["url"]
        assert calls["json"]["chat_id"] == "@chan"

    def test_failure_returns_false_never_raises(self, monkeypatch):
        def fake_post(url, **kw):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr("time.sleep", lambda s: None)
        assert send_telegram("hello", token="TOK", chat_id="@chan") is False

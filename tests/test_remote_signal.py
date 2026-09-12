"""Publishing and consuming the trailing-mean signal across process boundaries."""
import json

import httpx
import pytest

from radar import remote_signal
from radar.remote_signal import decode, encode, fetch


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture
def patched_get(monkeypatch):
    """Route httpx.get through a mock transport."""
    def install(handler):
        client = httpx.Client(transport=_transport(handler))
        monkeypatch.setattr(remote_signal.httpx, "get",
                            lambda url, **kw: client.get(url))
    return install


def _payload(n):
    return {"generated_at": 0, "signal_days": 4.5,
            "signal": {f"SYM{i}|hyperliquid": 0.01 * i for i in range(n)}}


def test_encode_decode_roundtrip():
    signal = {("BTC", "hyperliquid"): 0.12, ("ETH", "dydx"): -0.03}
    assert decode({"signal": encode(signal)}) == signal


def test_decode_tolerates_missing_and_malformed_keys():
    assert decode({}) == {}
    assert decode({"signal": {"nopipe": 0.5}}) == {}


def test_fetch_returns_the_published_signal(patched_get):
    patched_get(lambda req: httpx.Response(200, text=json.dumps(_payload(60))))
    signal = fetch("https://example.test/signal.json")
    assert len(signal) == 60
    assert signal[("SYM3", "hyperliquid")] == pytest.approx(0.03)


def test_fetch_returns_none_on_http_error(patched_get):
    patched_get(lambda req: httpx.Response(404, text="nope"))
    assert fetch("https://example.test/signal.json") is None


def test_fetch_returns_none_on_malformed_json(patched_get):
    patched_get(lambda req: httpx.Response(200, text="{not json"))
    assert fetch("https://example.test/signal.json") is None


def test_fetch_rejects_a_signal_too_thin_to_rank_on(patched_get):
    """A near-empty signal must not silently degrade into spot ranking."""
    patched_get(lambda req: httpx.Response(200, text=json.dumps(_payload(5))))
    assert fetch("https://example.test/signal.json", min_keys=50) is None

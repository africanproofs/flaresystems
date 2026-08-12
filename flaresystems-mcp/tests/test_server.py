"""Server tools: uniform envelope, the ACT kill-switch, and fail-fast plan parsing."""

from __future__ import annotations

import pytest

from flaresystems_mcp import server
from flaresystems_mcp.bridge import BridgeError, ClifResult


class FakeBridge:
    def __init__(self, *, allow_apply=False, result=None, raise_exc=None):
        self.allow_apply = allow_apply
        self.networks = ("flare", "songbird")
        self._result = result or ClifResult(data={"severity": "OK"}, exit_code=0)
        self._raise = raise_exc
        self.calls: list[tuple] = []

    def run(self, args, *, network, fund=False):
        self.calls.append((tuple(args), network, fund))
        if self._raise:
            raise self._raise
        return self._result


@pytest.fixture
def patch_bridge(monkeypatch):
    def _install(bridge):
        monkeypatch.setattr(server, "_bridge", bridge)
        return bridge
    return _install


def test_observe_wraps_in_envelope(patch_bridge):
    patch_bridge(FakeBridge(result=ClifResult(data={"severity": "WARN"}, exit_code=1)))
    out = server.funding_health("flare")
    assert out == {"ok": False, "exit_code": 1, "data": {"severity": "WARN"}}


def test_bridge_error_becomes_error_dict(patch_bridge):
    patch_bridge(FakeBridge(raise_exc=BridgeError("container down")))
    out = server.epoch_status("flare")
    assert out["ok"] is False and "container down" in out["error"]


def test_signing_progress_passes_epoch(patch_bridge):
    b = patch_bridge(FakeBridge())
    server.epoch_signing_progress("flare", epoch=421)
    assert b.calls[0][0] == ("epoch", "signing-progress", "--epoch", "421")


def test_signing_progress_omits_epoch_when_none(patch_bridge):
    b = patch_bridge(FakeBridge())
    server.epoch_signing_progress("flare")
    assert b.calls[0][0] == ("epoch", "signing-progress")


def test_propose_rejects_bad_json_without_touching_bridge(patch_bridge):
    b = patch_bridge(FakeBridge())
    out = server.funding_propose("flare", "{not json")
    assert out["ok"] is False and "not valid JSON" in out["error"]
    assert b.calls == []  # never reached the bridge


def test_propose_compacts_and_routes_to_read_container(patch_bridge):
    b = patch_bridge(FakeBridge())
    server.funding_propose("flare", '[{"account": "FastUpdates-1", "amount": 200}]')
    args, _net, fund = b.calls[0]
    assert fund is False and args[:3] == ("fund", "propose", "--plan")
    assert args[3] == '[{"account":"FastUpdates-1","amount":200}]'  # whitespace stripped


def test_apply_disabled_by_default_refuses(patch_bridge):
    b = patch_bridge(FakeBridge(allow_apply=False))
    out = server.funding_apply("flare", "[]")
    assert out["ok"] is False and "disabled" in out["error"]
    assert b.calls == []  # never executed


def test_apply_enabled_routes_to_fund_container(patch_bridge):
    b = patch_bridge(FakeBridge(allow_apply=True))
    server.funding_apply("flare", '[{"account":"FastUpdates-1","amount":200}]')
    args, _net, fund = b.calls[0]
    assert fund is True and args[:3] == ("fund", "apply", "--plan")

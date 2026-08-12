"""ClifBridge: command construction, container routing, JSON parsing, error taxonomy."""

from __future__ import annotations

import pytest

from flaresystems_mcp.bridge import BridgeError, ClifBridge


class FakeRunner:
    """Records the argv it was handed; replays a scripted (code, stdout, stderr)."""

    def __init__(self, code: int = 0, stdout: str = "{}", stderr: str = "") -> None:
        self.code, self.stdout, self.stderr = code, stdout, stderr
        self.calls: list[list[str]] = []

    def __call__(self, cmd, timeout):
        self.calls.append(list(cmd))
        return self.code, self.stdout, self.stderr


def _bridge(runner, **kw) -> ClifBridge:
    return ClifBridge(networks=("flare", "songbird"), runner=runner, **kw)


def test_read_routes_to_epoch_container_and_appends_json():
    r = FakeRunner(stdout='{"severity":"OK"}')
    br = _bridge(r)
    out = br.run(["fund", "health"], network="flare")
    assert out.data == {"severity": "OK"} and out.exit_code == 0
    assert r.calls[0] == ["docker", "exec", "clif-epoch-flare", "clif", "fund", "health", "--json"]


def test_fund_routes_to_fund_container():
    r = FakeRunner(stdout="{}")
    br = _bridge(r)
    br.run(["fund", "apply", "--plan", "[]"], network="songbird", fund=True)
    assert r.calls[0][:4] == ["docker", "exec", "clif-fund-songbird", "clif"]


def test_json_parsed_even_on_nonzero_exit():
    # `epoch status` exits 2 when degraded but still prints its report.
    r = FakeRunner(code=2, stdout='{"exit_code":2,"summary":"degraded"}')
    out = _bridge(r).run(["epoch", "status"], network="flare")
    assert out.exit_code == 2 and out.data["summary"] == "degraded"


def test_unknown_network_rejected():
    with pytest.raises(BridgeError, match="unknown/disabled network"):
        _bridge(FakeRunner()).run(["doctor"], network="coston2")


def test_empty_output_is_bridge_error_with_stderr():
    r = FakeRunner(code=1, stdout="", stderr="container not running")
    with pytest.raises(BridgeError, match="container not running"):
        _bridge(r).run(["doctor"], network="flare")


def test_non_json_output_is_bridge_error():
    r = FakeRunner(stdout="Traceback (most recent call last): boom")
    with pytest.raises(BridgeError, match="not JSON"):
        _bridge(r).run(["doctor"], network="flare")


def test_custom_container_templates():
    r = FakeRunner(stdout="{}")
    br = _bridge(r, read_container="c-{net}-r", fund_container="c-{net}-f")
    br.run(["fund", "health"], network="flare")
    br.run(["fund", "apply"], network="flare", fund=True)
    assert r.calls[0][2] == "c-flare-r" and r.calls[1][2] == "c-flare-f"


def test_from_env_reads_overrides(monkeypatch):
    monkeypatch.setenv("FLARESYSTEMS_MCP_NETWORKS", "flare , coston2")
    monkeypatch.setenv("FLARESYSTEMS_MCP_ALLOW_APPLY", "true")
    monkeypatch.setenv("FLARESYSTEMS_MCP_TIMEOUT", "30")
    br = ClifBridge.from_env()
    assert br.networks == ("flare", "coston2") and br.allow_apply is True and br.timeout == 30.0


def test_default_apply_disabled():
    assert ClifBridge().allow_apply is False

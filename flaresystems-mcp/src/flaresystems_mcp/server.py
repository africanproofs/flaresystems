"""flaresystems-mcp — the agent-native surface for the fwd+clif system (ADR-0006).

Custody-isolated by construction: OBSERVE tools are broad reads; the one ACT family
(funding propose/apply) is the deterministic membrane — an untrusted caller PROPOSES a
funding plan, clif VALIDATES + EXECUTES the accepted subset keyless, and fwd's policy
is the independent final gate. This server holds no keys and no tokens (see bridge.py):
it execs the already-scoped clif containers. `funding_apply` is additionally hard-off
unless FLARESYSTEMS_MCP_ALLOW_APPLY=true, so a freshly-registered server cannot move
value until the operator opts in. The NEVER tier (fwdctl capability grant / policy edit
/ wallet create / master key) has no tool here — enforced by omission.
"""

from __future__ import annotations

import json

import mcp.server.fastmcp as fastmcp

from flaresystems_mcp.bridge import BridgeError, ClifBridge

_bridge = ClifBridge.from_env()

mcp_server = fastmcp.FastMCP(
    "flaresystems",
    instructions=(
        "flaresystems MCP: the agent interface to AP's fwd+clif signing/funding system "
        "(ADR-0006). OBSERVE (read, broad): funding_health, epoch_status, clif_doctor, "
        "epoch_signing_progress. ACT (membraned, bounded): funding_propose validates a "
        "gas-funding plan against hard bounds and executes NOTHING (the review step); "
        "funding_apply validates then executes the accepted subset keyless — every line "
        "is rejected unless it is a known account, ≤ the per-tx cap, would NOT push the "
        "account above its balance band, and fits the ap-funder runway; fwd's policy is "
        "the final gate. Always funding_propose first and show the accept/reject lines "
        "before funding_apply. This server holds no keys; it cannot grant capabilities, "
        "mint tokens, edit policy, or touch a key — those are human-only. Networks: "
        f"{', '.join(_bridge.networks)}."
    ),
)


def _envelope(result) -> dict:
    """Uniform tool return: clif's exit code + its --json body (which may itself carry
    an `exit_code`/`ok` — kept nested under `data` to avoid collision)."""
    return {"ok": result.exit_code == 0, "exit_code": result.exit_code, "data": result.data}


def _err(msg: str) -> dict:
    return {"ok": False, "error": msg}


# --------------------------------------------------------------------------- OBSERVE


@mcp_server.tool()
def funding_health(network: str) -> dict:
    """Balances of every FSP account vs its funding band, the ap-funder runway, and an
    overall severity (OK/WARN/CRIT). Read-only. A read failure is CRIT, never healthy."""
    try:
        return _envelope(_bridge.run(["fund", "health"], network=network))
    except BridgeError as exc:
        return _err(str(exc))


@mcp_server.tool()
def epoch_status(network: str) -> dict:
    """The epoch daemon's health: current/last-done reward epoch, per-epoch phase, and a
    degraded flag. exit_code 2 = degraded/dead, 3 = no daemon state. Read-only."""
    try:
        return _envelope(_bridge.run(["epoch", "status"], network=network))
    except BridgeError as exc:
        return _err(str(exc))


@mcp_server.tool()
def clif_doctor(network: str) -> dict:
    """Consumer self-check (ADR-0001 seam): fwd reachability + master status, configured
    capabilities (NAMES only, never token values), on-chain contract-drift vs clif's
    pins, the epoch daemon summary, and the compat tuple. Read-only."""
    try:
        return _envelope(_bridge.run(["doctor"], network=network))
    except BridgeError as exc:
        return _err(str(exc))


@mcp_server.tool()
def epoch_signing_progress(network: str, epoch: int | None = None) -> dict:
    """Reward/uptime signing progress for an epoch (default: the current one): signed %
    vs threshold, signer count, finalized flag, and whether OUR vote is on-chain. Read-only."""
    args = ["epoch", "signing-progress"]
    if epoch is not None:
        args += ["--epoch", str(epoch)]
    try:
        return _envelope(_bridge.run(args, network=network))
    except BridgeError as exc:
        return _err(str(exc))


# ------------------------------------------------------------------------------- ACT


def _prepare_plan(plan_json: str) -> str | dict:
    """Fail fast on an unparseable plan; return the compact JSON to pass to clif."""
    try:
        doc = json.loads(plan_json)
    except json.JSONDecodeError as exc:
        return _err(f"plan is not valid JSON: {exc}")
    return json.dumps(doc, separators=(",", ":"))


@mcp_server.tool()
def funding_propose(network: str, plan_json: str) -> dict:
    """VALIDATE a gas-funding plan against the hard bounds and execute NOTHING (the
    review step). `plan_json` is a JSON string: a list `[{"account":"FastUpdates-1",
    "amount":200}]` or `{"topups":[...]}`; each item is `{"account", "amount"}` or
    `{"account", "target"}` (target resolves to the gap to that balance). Returns per-line
    accept/reject with reasons. Always call this and review before funding_apply."""
    prepared = _prepare_plan(plan_json)
    if isinstance(prepared, dict):  # parse error envelope
        return prepared
    try:
        return _envelope(_bridge.run(["fund", "propose", "--plan", prepared], network=network))
    except BridgeError as exc:
        return _err(str(exc))


@mcp_server.tool()
def funding_apply(network: str, plan_json: str) -> dict:
    """VALIDATE then EXECUTE the accepted lines of a gas-funding plan, keyless (the ACT
    surface). Rejected lines are never touched; each transfer is verified to have raised
    the balance (mined ≠ success); fwd's policy is the final gate. Same `plan_json` shape
    as funding_propose. Disabled unless FLARESYSTEMS_MCP_ALLOW_APPLY=true (a stray/compromised
    server cannot move value); when disabled, use funding_propose to preview only."""
    if not _bridge.allow_apply:
        return _err(
            "funding_apply is disabled (FLARESYSTEMS_MCP_ALLOW_APPLY!=true). "
            "Use funding_propose to preview; ask the operator to enable execution."
        )
    prepared = _prepare_plan(plan_json)
    if isinstance(prepared, dict):
        return prepared
    try:
        return _envelope(_bridge.run(["fund", "apply", "--plan", prepared], network=network, fund=True))
    except BridgeError as exc:
        return _err(str(exc))


def main() -> None:
    mcp_server.run()


if __name__ == "__main__":
    main()

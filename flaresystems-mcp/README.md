# flaresystems-mcp

The agent-native **MCP surface** for AP's `fwd`+`clif` signing/funding system
(ADR-0006, `flaresystems/docs/adr/0006-agent-interface-layer.md`). It exposes the
system's OBSERVE reads and the one membraned ACT family (gas-funding) as MCP tools an
agent — or a human via an MCP client — can call, **without ever holding custody**.

## Custody posture (why this is safe)

- **Holds no keys and no caller tokens.** Every tool is a thin `docker exec` into the
  already-deployed, already-scoped `clif` container (`bridge.py`). The read tokens and
  the scoped funding token live only in the container's env; **fwd's policy is the
  independent final gate** regardless of any bug here. This is strictly stronger than
  ADR-0006 §54's "holds only the scoped token" — it holds none.
- **The ACT tool is opt-in.** `funding_apply` refuses unless
  `FLARESYSTEMS_MCP_ALLOW_APPLY=true`, so a freshly-registered or compromised server
  cannot move value. `funding_propose` (validate-only) is always available.
- **The NEVER tier has no tool.** No capability grant, policy edit, wallet create, or
  master-key access exists here — enforced by omission and by the container holding no
  custody authority.

## Tools

**OBSERVE** (read):
- `funding_health(network)` — balances vs bands, ap-funder runway, severity.
- `registration_status(network)` — the RE423 detector: are we in the on-chain registered
  voter set for the current/next reward epoch, and are the prereqs green? CRIT = live exclusion.
- `epoch_status(network)` — reward-epoch/phase, degraded flag.
- `clif_doctor(network)` — fwd reachability, capabilities (names only), contract drift.
- `epoch_signing_progress(network, epoch?)` — signed % vs threshold, our-vote-on-chain.

**ACT** (membraned — propose/validate → execute-within-bounds; fwd policy is the floor):
- `funding_propose(network, plan_json)` — validate a plan, execute nothing.
- `funding_apply(network, plan_json)` — execute the accepted subset, keyless, verified.

`plan_json` is a JSON string: `[{"account":"FastUpdates-1","amount":200}]` or
`{"topups":[...]}`; each item is `{"account","amount"}` or `{"account","target"}`.

## Config (env)

| var | default | meaning |
|---|---|---|
| `FLARESYSTEMS_MCP_NETWORKS` | `flare,songbird` | allowed networks |
| `FLARESYSTEMS_MCP_READ_CONTAINER` | `clif-epoch-{net}` | container for reads (holds the state file + tokens) |
| `FLARESYSTEMS_MCP_FUND_CONTAINER` | `clif-fund-{net}` | container for funding (holds the scoped funding token) |
| `FLARESYSTEMS_MCP_ALLOW_APPLY` | `false` | must be `true` for `funding_apply` to execute |
| `FLARESYSTEMS_MCP_TIMEOUT` | `90` | per-call seconds |
| `FLARESYSTEMS_MCP_DOCKER` | `docker` | docker binary |

## Run

Registered in the root `.mcp.json` as a stdio server:

```json
"flaresystems": {
  "command": "poetry",
  "args": ["--directory", "<abs>/flaresystems/flaresystems-mcp", "run", "flaresystems-mcp"],
  "env": {}
}
```

Requires the `clif` containers running locally (Docker) with their per-network env.

## Test

```bash
poetry install
poetry run pytest -q
poetry run ruff check .
```

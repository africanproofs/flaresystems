# ADR 0006 — The agent interface layer: CLI + MCP over the flaresystems, observe/act/never

- **Status:** Accepted (contract). Build: phased (see § Phasing); Phase 0 is this document. **Extends ADR-0001** (the trust-domain membrane / `capability_id` spine) — the interface layer is a *consumer* of that membrane, never a new authority. Supersedes nothing.
- **Date:** 2026-08-12.
- **Scope:** cross-project — `clif` (the CLI substrate + the `funding.apply` membrane), `fwd`/`fwdctl` (custody read surface; custody authority stays human-only), a new `flaresystems-mcp` server, and (reused, not rebuilt) `flarestack`'s chain/provider read tools.
- **Location:** git-tracked in the `flaresystems` umbrella (`docs/adr/`).

## Context

The fwd+clif system is now feature-complete: fwd is the zero-egress custody signer; clif is the keyless
consumer for reward-signing, claiming, **and gas-funding** (the `ap-funder` + native-transfer capability,
proven live on mainnet 2026-08-11). We want the whole system to become **agent-drivable later** — an AI
agent that observes state and takes bounded actions — WITHOUT attaching an agent now, and WITHOUT ever
handing an agent custody authority.

The load-bearing question is not "which agent framework" but **"what is the stable, bounded interface an
untrusted decision-maker talks through, such that the worst it can do is already contained?"** AP's
existing doctrine answers the shape (FICS/qamata: the LLM *proposes*, a deterministic membrane *executes*,
and the membrane — never the LLM — touches infra). This ADR fixes that interface contract before any MCP
tool or agent exists, so the surface is designed for containment from the first line.

The funding capability is the **reference ACT capability**: `run_funding` already does the keyless
execute-and-verify; the only new thing an interface needs is a validated front door (`funding.apply`).

## Decision (load-bearing — do not relitigate)

1. **Three tiers with a HARD boundary — OBSERVE / ACT / NEVER.**
   - **OBSERVE** (read): open, broad — balances, epoch/phase, signing %, health, nonce, audit.
   - **ACT** (write): *membraned* — every action validates against deterministic bounds, and fwd's policy
     is the independent final gate. Bounded blast radius by construction.
   - **NEVER**: custody authority (`fwdctl capability grant`, policy edits, `wallets create`, master key)
     is **human CLI only — never an MCP tool, never an agent-reachable action.** An agent may *propose* a
     funding plan; it can never grant itself a capability, mint a token, or touch a key. This is the
     ADR-0001 membrane restated at the interface layer: the interface holds **no native authority**.

2. **CLI is the substrate; MCP wraps it.** One implementation, two surfaces. Every capability is a CLI
   command emitting structured JSON (`--json`); MCP tools shell/import those commands. No business logic
   is duplicated in the MCP layer — it is transport + schema only. (Mirrors ADR-0001's "one canonical
   impl" tenet.)

3. **ACT is proposer/executor-separated and doubly-gated.** The caller (agent) *proposes*; clif's
   deterministic membrane *validates + executes*; fwd's policy *bounds*. For funding, `funding.apply`
   accepts `{topups:[{account, amount|target}]}`, and REJECTS any line that is not in the registry
   allowlist, exceeds the band upper, exceeds fwd's per-tx cap, or exceeds ap-funder runway / a daily
   budget — executing only the valid subset, keyless, verifying the balance rose (mined ≠ success). fwd's
   recipient-allowlist + per-tx cap + rate + daily aggregate remain the independent hard floor regardless
   of any clif or agent bug.

4. **Expose BOTH `propose` (pending) and `apply` (execute-within-bounds).** `propose` writes a pending,
   auditable plan a human approves (FICS "human approval on writes"); `apply` executes immediately within
   the membrane's bounds. Same validation, different gate — so a future agent can be run **human-gated OR
   autonomous without any interface change**. Default posture for a first agent: human-gated.

5. **The MCP server is capability-scoped, custody-isolated.** A NEW `flaresystems-mcp` is the agent-native
   surface for the fwd+clif *system*; it holds ONLY read access + the scoped `funding.apply` caller token,
   NOT custody. A compromised MCP server cannot exceed fwd's policy (§3) and holds no key. `flarestack`
   stays the chain/devops read layer it already is (reused for `provider.health`/reward reads, not
   rebuilt). Rationale for a new server over extending flarestack: isolate the one write authority
   (funding-apply) in a single tightly-scoped process; keep the read-focused flarestack read-only.

6. **Structured I/O + idempotency + audit.** Every tool returns typed JSON (agent-consumable) with a human
   render; every ACT carries an idempotency key; every decision → action → effect is traced (the caller's
   proposal, clif's per-line accept/reject, fwd's hash-chained audit) — complete accountability for who
   decided what and which wei moved.

## The surface (catalog — the contract Phase 1–3 implement)

**OBSERVE** (safe, broad; CLI `--json` → MCP tool):
- `funding.health` / `funding.accounts` — balances vs bands, ap-funder runway, severity.
- `epoch.status` — current epoch, phase, signing %, claim state, degraded flag.
- `fwd.health` / `fwd.nonce` / `fwd.audit.tail` / `fwd.capabilities` — custody read-only.
- `provider.health` — FSP voter registration + submission health (reuse flarestack `check_fsp_health`).
- `chain.reward_state` — claimable epochs, reward conditions, contract-drift check.

**ACT** (membraned, bounded):
- `funding.propose(plan)` — validate + write a pending plan (human-approve gate). **Reference.**
- `funding.apply(plan)` — validate + execute-within-bounds, keyless, verified.
- *(later, same pattern)* `nonce.sync`, `epoch.rehearse`.

**NEVER** (human CLI only — `fwdctl`): capability grant, policy edit, wallet create, master key.

## Phasing

- **Phase 0 — this ADR** (the contract). ✅ Done at Accepted (2026-08-12).
- **Phase 1 — CLI `--json` completeness.** Every OBSERVE capability emits structured JSON (clif: `fund
  health`, `epoch status`, `doctor` + gaps; fwdctl read commands). The MCP layer is thin over this.
  🟡 **Partial (clif v0.5.46): `fund health --json` shipped.** Remaining: `epoch status`, `doctor`,
  fwdctl read commands.
- **Phase 2 — the funding membrane.** `clif fund propose` + `clif fund apply --plan <json>` — the
  validated executor. The one ACT capability; small extension of `run_funding`.
  ✅ **DONE + DEPLOYED (clif v0.5.46, 2026-08-12).** `validate_plan()`/`apply_plan()` in
  `clif/funding.py`; `fund propose` (validate-only) + `fund apply` (validate+execute keyless) + `fund
  health --json`. Live read-only reject/JSON/exit-code proof on Flare prod; execute path shares the
  mainnet-proven `_execute_topup`. 338 clif tests green.
- **Phase 3 — `flaresystems-mcp`.** Wrap the Phase-1 reads + `funding.propose`/`apply` as MCP tools;
  scoped tokens; reuse flarestack reads. ⏭️ **Next.**
- **Phase 4 — (out of scope here)** attach an agent; it merely consumes this surface.

## Consequences / non-goals

- **No agent is attached by this ADR.** It builds the interface an agent will *later* use. The system stays
  fully operable by the deterministic daemons + human CLI in the meantime.
- **Custody authority never enters the agent surface.** The NEVER tier is enforced by omission (no MCP tool
  exists for it) AND by fwd (the MCP token has no custody scope) AND by the human-only `fwdctl` path.
- **The interface is versioned.** Tool schemas are a contract; changes are additive or versioned, never
  silent — an agent built against it must not break on a point release.
- **Blast radius is unchanged from today:** at worst, AP's own float moves between AP's own whitelisted
  accounts, ≤ per-tx cap, ≤ daily aggregate — with or without an agent, human-gated or autonomous.

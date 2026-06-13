# ADR 0005 — The `fsp` consumer: the Flare-systems signing stack, dual-mode keyless via fwd

- **Status:** Accepted (scope + contract). Build: phased, Songbird-canary-gated (see § Phasing). **Extends ADR-0001** (activates its deferred `provider`/manifest framework) and **ADR-0004** (builds the `fsp` consumer branch of the tree). Supersedes nothing.
- **Date:** 2026-06-13.
- **Scope:** cross-project — `fwd`, `fwd-client` (Go), the downstream forks of `flare-system-client` + `fast-updates`, and the `provider` coordinator (now triggered).
- **Location:** git-tracked in the `flaresystems` umbrella (`docs/adr/`).

## Context

ADR-0004 named **`fsp`** — the keyless flare-system-client — as fwd consumer #2 and the **forcing
function** for the framework ADR-0001 deferred ("build the seam, defer the framework; do not abstract from
N=1"). This ADR schedules that build and fixes its load-bearing decisions before any immutable
`capability_id` is minted or any live signing key moves.

**The defining finding.** clif already migrated the only *slow, epoch-cadence* slice of the FSP path
(uptime/reward sign + submit), riding transitionally under `claim/`. Everything left in the Flare-systems
signing stack is **per-round and time-critical**: `submit1/2/3`, `submitSignatures` (and its payload
signature), and `fast-updates`. Therefore `fsp` is **not** "repeat the clif pattern on more keys" — it
puts **fwd inside the FTSO/FSP consensus loop for the first time**. A fwd miss inside a ~90-second voting
window costs that round's reward; a sustained miss drops the provider below **minimal conditions** and
forfeits the epoch across every protocol. fwd's role changes from a convenience signer for slow operations
to a **consensus-critical real-time dependency** — and that, not the Go mechanics, is the centre of
gravity.

**The signing surface (ground-truthed from the repos).** The stack holds four hot keys across three Go
services and signs inline, broadcasting itself:

| Operation | Key (SGB / FLR) | fwd endpoint | New fwd capability? | Cadence |
|---|---|---|---|---|
| submit1/2/3 tx | SUBMIT_PK `0xa8BB` / `0x366B` | `/v1/sign-transaction` | no | per-round |
| submitSignatures tx | SIGNATURES_PK `0xf417` / `0x81ac` | `/v1/sign-transaction` | no | per-round |
| signUptimeVote / signRewards / signNewSigningPolicy / registerVoter / preRegisterVoter tx | SIGNING_PK `0xfB02` / `0x3FA0` | `/v1/sign-transaction` | no (clif proved uptime/reward submit) | per-epoch |
| fast-updates submitUpdates / submitAndPass tx | sortition key | `/v1/sign-transaction` | no | per-block (sortition) |
| uptime signature | SIGNING_PK | `/v1/sign-fsp-message` UPTIME | exists (clif) | per-epoch |
| reward-distribution signature | SIGNING_PK | `/v1/sign-fsp-message` REWARD_DISTRIBUTION | exists (clif) | per-epoch |
| **submitSignatures payload sig** | SIGNING_PK | new typed msg `PROTOCOL_PAYLOAD` | **GAP** | **per-round** |
| **signing-policy hash sig** | SIGNING_PK | new typed msg `SIGNING_POLICY` | **GAP** | per-epoch |
| **voter-registration sig** (legacy + chainId) | SIGNING_PK | new typed msg `VOTER_REGISTRATION` | **GAP** | per-epoch |
| **fast-updates proof sig** (custom prefix) | sortition key | new typed msg / signer branch | **GAP** | per-block |

`fdc-client` holds **no signing key** (only `api_keys`) — empirically confirming ADR-0004's call that
there is **no `fdc` consumer**; FDC participation rides the system-client keys. The fast-updates BN254
sortition *randomness* is a local computation, not a signature — it never leaves the client.

## Decision

### D1 — Topology: co-locate (flexible)
fwd runs on the FSP-stack host; the bundle handoff and signing are loopback. This **erases the latency
failure mode** and keeps the **off-host transport deferred** (ADR-0001 §Scope) — the first genuinely
off-host consumer re-triggers it.

### D2 — Availability: single co-located fwd, prove on Songbird; HA deferred-pending-canary
The starting posture is **one** co-located fwd with supervisor auto-restart and hard monitoring/alerting
on sign latency + availability. The all-four-keys migration runs on **Songbird first**; the real miss-rate
over N reward epochs is measured. **Hot-standby / HA is a fast-follow gated on that evidence**, not in the
initial scope. An **automatic runtime fallback to a local key is rejected** — it keeps a hot key on the
box and violates custody; the rollback lever is the deploy-time mode (D5), not a silent re-sign.

### D3 — Scope: all four keys migrate
SIGNING_PK, SUBMIT_PK, SIGNATURES_PK, and the fast-updates sortition key all move into fwd's sealed
master. There is no permanent local-key carve-out; the end-state is fully keyless.

### D4 — Fork strategy: downstream fork
A maintained downstream fork of `flare-system-client` and `fast-updates` (not an upstream PR). The fwd
integration is isolated behind a thin `Signer` seam to minimise rebase surface against upstream.

### D5 — Dual-mode signer: a deploy-time `local | fwd` setting; deprecate `local` in time
The fork exposes a `Signer` strategy interface with two backends, selected by config
(`signer.backend`, default **`local`**):
- **`local`** — the existing in-process `*ecdsa.PrivateKey` + `types.SignTx` path; **byte-for-byte the
  upstream behaviour**; loads the env keys exactly as today. The fork is a behaviour-identical drop-in.
- **`fwd`** — keyless via `fwd-client/go`; loads **no** local key; keeps **nonce management + broadcast
  local** (the zero-egress contract: fwd signs, the client broadcasts + reports back).

Credential loading is mode-gated: `local` requires the env keys and forbids fwd config; `fwd` requires the
fwd base-url + caller tokens and forbids the env keys — so "keyless" provably means **no key on disk**. An
optional per-role override permits a staged migration; the default is whole-stack. The `local` path is
**retained but deprecated**, removed only once `fwd` mode is proven on both mainnets. The setting is both
the rollback lever and the deprecation runway.

### Raw-hash resolution: path (i), typed messages (NOT a generic sign-hash verb)
fwd reconstructs every preimage **server-side** from structured fields and EIP-191-signs it
(`domain/fsp_message.py::build_fsp_message`, `infra/envelope_signer.py::sign_fsp_eip191`); it **never**
signs a caller-supplied hash. The four signing gaps are closed by **adding new typed FSP messages** to
fwd's message-type registry — `SIGNING_POLICY`, `VOTER_REGISTRATION`, `PROTOCOL_PAYLOAD`, and the
fast-updates proof — each with its own field schema, per-type hash construction, and policy
authorization (`FspPermissionBlock.message_types` already string-matches, so least-privilege is one caller
per message type). A blanket `/v1/sign-hash` verb is **rejected**: it would let the SIGNING_PK caller sign
any 32-byte value — including a forged EVM-tx preimage — inverting fwd's core safety contract.

**The one deliberate compromise — `PROTOCOL_PAYLOAD`.** The `submitSignatures` payload is opaque protocol
bytes (38/66 B encoding protocol-id, voting round, and the votes/merkle root); full semantic
reconstruction would require fwd to embed FTSO/FDC protocol knowledge. So `PROTOCOL_PAYLOAD` accepts the
*bytes*, and fwd does `keccak` + EIP-191 itself, with policy **bounded by protocol-id and length** — not
open-ended. This is the single, recorded departure from pure server-side reconstruction; it stays
domain-separated from EVM-tx signing by the EIP-191 prefix.

### Fork repo home
The forked `flare-system-client` and `fast-updates` become the **`fsp` consumer's code**, living as
independent repos under `github.com/africanproofs/` and co-located as umbrella members under
`flaresystems/` (gitignored from the umbrella, exactly like `clif/`). A new `flaresystems/fsp/` member
holds the consumer wrapper — `fsp spec` (the custody-diff renderer), `import-credentials`, the `fspctl`
deployment wrapper, and the deploy manifest — mirroring clif's role split. (Exact layout confirmed at
Phase-0 close; the structural decision — fsp is a custody boundary owning these forks — is firm.)

## Phasing (each phase = its own Opus→Sonnet hand-off when scheduled)

- **Phase 0** — this ADR + the `fsp` consumer spec + fork repo home. No code.
- **Phase 1** — fwd capability extension (the new typed messages + policy + `generate_policy` fsp roles + onboard fsp bundle). Fully unit-tested before any consumer touches it.
- **Phase 2** — the Go fork + dual-mode `Signer` (`local` default + `fwd`). Ships running in `local` mode = behaviour-identical to upstream, de-risking the fork before any key moves.
- **Phase 3** — the `provider` framework (manifest, cross-consumer conflict detection, `provider doctor`) + the `claim/`→`fsp/` prefix migration of clif's four transitional FSP roles (revoking the old `claim/` callers — `fwd reissue` will not auto-revoke renamed callers).
- **Phase 4** — Songbird canary: co-located fwd, flip to `fwd` mode, all four keys, miss-rate measurement, the HA gate.
- **Phase 5** — Flare cutover, gated on a clean Songbird canary.
- **Phase 6** — deprecate then remove `local` mode once `fwd` mode is proven on both mainnets.

## Decided vs deferred

- **Decided (this ADR):** D1–D5; the typed-message raw-hash resolution + the `PROTOCOL_PAYLOAD` compromise; all four keys; the downstream dual-mode fork; the fork repo home; the Songbird-canary-gated phasing.
- **Deferred, with named triggers:** **HA/hot-standby fwd** → gated on the Songbird miss-rate (D2); **off-host transport** → the first off-host consumer (D1 co-location avoids it now); **the per-role staged-migration override** → used only if the canary shows the per-round path needs isolating from the epoch-cadence path.

## Consequences

- fwd gains a **consensus-path role** with an explicit availability contract; the canary miss-rate becomes a hard go/no-go for Flare. This is the first time fwd's uptime is revenue-critical in real time.
- The `provider` framework (`consumer-contract-v1` §7) is **built**, not deferred — consumer #2 supplies the second consumer the conflict-detector needs, and the tree's "no wallet in two consumers" invariant (ADR-0004) becomes enforceable.
- The dual-mode setting makes the fork a safe drop-in and gives every AP Go consumer a template for incremental fwd adoption: ship in `local`, prove, flip to `fwd`, deprecate `local`.
- fwd's typed-message registry grows by four message types; its safety model (reconstruct-and-reason, never sign-an-opaque-hash) is preserved, with `PROTOCOL_PAYLOAD` the single bounded exception.

## Addendum (2026-06-13) — complete fsp sign-role set + the `fsp-voter` capability

Phase 1a/1b implemented the four new fwd typed messages and verified each against the upstream Go client
(`build_fsp_message` golden vectors; fwd at commits `a9ec8f2` + `aede961`, 953 unit tests green). That work
**discovered signing operations ADR-0004's `fsp` tree did not list** — the tree predated the gap analysis.
The fsp consumer's **complete** sign-role taxonomy (immutable `fsp/<net>/<role>` capability_ids) is
therefore extended with four roles, named per the `<context>-<noun>-<verb>` convention:

| role | fwd message_type | wallet (key) | cadence |
|---|---|---|---|
| `signing-policy-sign` | `SIGNING_POLICY` | fsp-signing (SIGNING_PK) | per-epoch |
| `voter-registration-sign` | `VOTER_REGISTRATION` | fsp-signing (SIGNING_PK) | per-epoch |
| `protocol-message-sign` | `PROTOCOL_PAYLOAD` | fsp-signing (SIGNING_PK) | **per-round** (submitSignatures payload, any subprotocol — FTSO/FDC) | 
| `fastupdate-sign` | `FAST_UPDATE` | fastupdate (sortition key) | per-block (sortition) |

`protocol-message-sign` is named protocol-agnostic deliberately (operator decision 2026-06-13): the same
SIGNING_PK leg signs the submitSignatures payload for **any** subprotocol, so it is NOT `ftso-signature-*`.

**Policy-generation home (`fsp-voter` capability).** `generate_policy` (`app/policy_init.py`) is the only
renderer of policy blocks; the generic `fwdctl capability grant` path mints callers against
already-existing policy_paths (`capability_grant.py` is parse+plan+mint only). To render the fsp voter's
blocks **without polluting clif's `fsp` capability output** (clif rides `fsp/uptime-*`/`fsp/reward-*`
transitionally — ADR-0004), the voter set is emitted under a **new `fsp-voter` capability** that composes
with `fsp` (clif = `claim,fsp`; the fsp consumer = `fsp,fsp-voter`). Sequencing (operator decision):
- **1c-i (no new ABIs):** `fsp-voter` emits the four sign `fsp_permissions` blocks above + the
  `fastupdate-<net>` wallet; the four roles added to `_ROLE_CONVENTION`.
- **1c-ii (needs ABIs):** the submit-tx roles (`ftso-price-submit`, `ftso-signature-submit`,
  `fastupdate-submit`, `fdc-bitvote-submit`) — blocked on sourcing the **Submission** + **FastUpdater**
  ABIs into the fwd registry (today it has only reward_manager / flare_systems_manager / participant_register
  / erc20). At that point `fastupdate-<net>` also enters `fsp_self_submit` (sign + self-submit carve-out).

**Resolved (2026-06-13, from the deployment compose env-mapping — the authoritative source for key
topology).** The fast-updates proof is signed by `SIGNING_PK` (`SIGNING_PRIVATE_KEY=${SIGNING_PK}`, = the
`fsp-signing` wallet); the three `FAST_UPDATES_ACCOUNTS` are **EVM-only** `submitUpdates` tx accounts; the
BN254 `FAST_UPDATES_SORTITION_PRIVATE_KEY` is **local-only** (computes randomness, never signs, never fwd).
So the fwd model is **one `fastupdate-sign` on `fsp-signing` + three EVM-only `fastupdate-submit-{1,2,3}`** —
NO cross-domain fast-update wallet and NO `fast_updater` carve-out. ADR-0004's `fastupdate-submit-{1,2,3}`
referred to these three tx accounts; the proof-sign is a single role, not three. (Corrected in fwd
`86479b6`, superseding `2a23dcf`'s erroneous 3-seat model — the multiplicity was wrongly inferred from the
on-chain identity list instead of the deployment's key wiring.) Also resolved: system-sender =
`SIGNING_PK` (`SYSTEM_CLIENT_SENDER_PRIVATE_KEY=${SIGNING_PK}`), consistent with the existing FSM
self-submit carve-out.

**Phase-1 follow-on (OI-2, RESOLVED + built — fwd `a0dfe47`).** The system-client finalizer
(`enabled_finalizer = true`) submits to the **Relay** contract via the `relay()` method, signing with
`SigningPolicyPrivateKey` (= the `fsp-signing` wallet) — so `fsp-signing` is cross-domain over Relay too.
Built as the `relay-submit` role (Relay `relay()`, `max_value_wei=0`) on `fsp-signing`, with `relay()`
added to `_FSP_SELF_SUBMIT_SHAPES` (fsp-signing's exempt EVM shapes = FSM signUptimeVote/signRewards AND
relay; carve-out independently tamper-verified to stay bounded). Relay addresses (FlareContractRegistry):
flare `0xCcF30790A93F15e24EB909548a2C58a9b0a7FBd4`, songbird `0xCB86E8Be709001e01897Bf59847406853da8f14b`.
**This completes fwd's capability surface — every key/operation in the live flare-system deployment now maps
to a built, unit-proven fwd capability.** The keyless Go client (`fwd-client/go` `2fa4553`) models all six
FSP message types; the Python `fwd-client` mirror is a lockstep follow-on (no consumer needs it yet).

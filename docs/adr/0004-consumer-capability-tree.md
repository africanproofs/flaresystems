# ADR 0004 — The consumer/capability tree: how to draw consumer boundaries

- **Status:** Accepted. **Extends ADR-0001** (settles the consumer-naming / granularity question ADR-0001 §Scope left deferred). Supersedes nothing.
- **Date:** 2026-06-13.
- **Scope:** cross-project — `fwd`, `clif`, `fwd-client`, and the named future consumers `fsp`, `fdc`.
- **Location:** git-tracked in the `flaresystems` umbrella (`docs/adr/`).

## Context

ADR-0001 made `capability_id` (`<consumer>/<network>/<role>`) the immutable spine but **deferred** the
question of how to *draw consumer boundaries* — "build the seam, defer the framework." That question is
now live: the operator named two siblings to `clif` — **`fsp`** (the keyless flare-system-client, from
`flare-foundation/flare-systems-deployment`) and **`fdc`** (`flare-foundation/fdc-suite-deployment`).

Because `capability_id` is **immutable by contract** (renaming breaks every downstream holder joined on
it — fwd policy, bundle, import state, `provider doctor`), the taxonomy must be settled **before**
consumer #2 deploys against it. A boundary drawn wrong today is permanent. This ADR fixes the
**principle that generates the tree**, so every future workload slots in without re-litigation, and
records the resulting tree + two concrete corrections.

## Decision — the generating principle

> **A consumer is a custody boundary: a coherent set of capabilities sharing a key-set and an
> operational identity. It is NOT a deployment container, a git repo, or a protocol.**

Five corollaries decide every boundary:

1. **Shared signing key ⟹ same consumer.** Two consumers authorized over one on-chain key is the exact
   cross-consumer key-sharing the `provider` conflict-detector exists to catch (ADR-0001 §7). The
   boundary question is never "which app/repo?" but **"which key, which registered identity?"**
2. **Name by function/identity, never by form.** `fsp`, `claim` — not `clif` ("CLI for Flare"). The
   consumer name is the immutable capability prefix; it must read as *what it is*, forever. (ADR-0001
   already flagged "clif" as illustrative.)
3. **A capability = one `(network, wallet, contract, method, leg)` tuple = one caller token = one fwd
   policy block.** The Leg-1 *sign* (`/v1/sign-fsp-message`) vs Leg-2 *submit* (`/v1/sign-transaction`)
   split is **structural** — fwd forbids one `policy_path` key in both `permissions` and
   `fsp_permissions`, so a sign role and its submit role are always distinct capabilities.
4. **Network is orthogonal** (`<consumer>/<net>/<role>`) — a dimension of every capability, never a
   consumer split.
5. **Build a consumer only when its key actually migrates to fwd.** The tree below is the *target*;
   unbuilt branches are placeholders with named triggers, not a backlog (the ADR-0001 deferral
   discipline, unchanged).
6. **Role tokens are `<context>-<noun>-<verb>`, fully self-describing** (verb ∈ {`claim`, `sign`,
   `submit`}, verb last) — readable in isolation (the role appears bare in `_ROLE_CONVENTION`, policy
   paths, audit rows, the bundle). The verb disambiguates operations that share a noun: reward
   *claiming* (`ftso-reward-claim`) vs reward *signing* (`reward-distribution-sign`). FSP signing is
   split **per message-type** for least-privilege — `fsp_permissions.message_types` pins one caller to
   UPTIME and another to REWARD_DISTRIBUTION, so an uptime token structurally cannot sign a reward
   distribution (one capability = one message-type/method = one caller token).

## The tree

```
fwd  — custody authority: holds every HOT EVM key (sealed AES-256-GCM), signs, never broadcasts
│
├─ fsp/      the protocol VOTER — keyless flare-system-client (Go, via fwd-client/go, built for this).
│            ONE operational identity: the EntityManager-registered hot key-set. Owns ALL protocol
│            participation — FTSO, the FSP base layer, AND FDC (shared voter key).
│   roles per net {flare, songbird} — illustrative; fsp self-describes the exact set via `fsp spec --json`:
│   ├─ fsp/<net>/ftso-price-submit          Submission.submit1/submit2             (Submit key 0x366B…)
│   ├─ fsp/<net>/ftso-signature-submit      Submission.submitSignatures            (SubmitSignatures key 0x81ac…)
│   ├─ fsp/<net>/uptime-vote-sign           sign-fsp-message — UPTIME              (SigningPolicy key 0x3FA0…)
│   ├─ fsp/<net>/uptime-vote-submit         FlareSystemsManager.signUptimeVote     (gas sender)
│   ├─ fsp/<net>/reward-distribution-sign   sign-fsp-message — REWARD_DISTRIBUTION (SigningPolicy key)
│   ├─ fsp/<net>/reward-distribution-submit FlareSystemsManager.signRewards        (gas sender)
│   ├─ fsp/<net>/fdc-bitvote-submit         FDC bitvote (shared voter key)         ← FDC lives HERE
│   └─ fsp/<net>/fastupdate-submit-{1,2,3}  FastUpdater.submitUpdates              (FastUpdates-1/2/3 keys)
│
├─ claim/    reward HARVESTER — clif, rescoped (Python). Orthogonal to voting; distinct claim-executor
│            key; recipient-pinned. NO foundation repo does the claim. The 4 FSP roles ride here
│            TRANSITIONALLY (same tokens migrate to fsp/ on a prefix swap) until the fsp consumer lands.
│   ├─ claim/<net>/ftso-reward-claim           RewardManager.claim                    (claim executor 0x0A33…, recipient pinned)
│   ├─ claim/<net>/uptime-vote-sign            sign-fsp-message — UPTIME              [transitional → fsp]
│   ├─ claim/<net>/uptime-vote-submit          FlareSystemsManager.signUptimeVote     [transitional → fsp]
│   ├─ claim/<net>/reward-distribution-sign    sign-fsp-message — REWARD_DISTRIBUTION [transitional → fsp]
│   ├─ claim/<net>/reward-distribution-submit  FlareSystemsManager.signRewards        [transitional → fsp]
│   └─ claim/<net>/validator-reward-claim      staking/validator reward (EVM side)    [future]
│
└─ deferred — built only when the key actually moves to fwd (named triggers, not a backlog):
   ├─ register/<net>/…   ParticipantRegister txs   (apregister / apcli .env PRIVATE_KEY → fwd)
   └─ payments/<net>/…   Lantana payouts            (future demand source)
```

**NOT consumers** (the two corrections that simplify the model):

- **`fdc-suite-deployment` is verifier/indexer INFRASTRUCTURE** — it holds no keys and signs nothing.
  FDC *participation* is roles **under `fsp`** (the system-client signs the FDC bitvote/merkle with the
  shared voter key). **There is no `fdc` consumer** — the named repo is infra, not a signer. (The exact
  FDC role placement under `fsp` is confirmed when `fsp` is built and self-describes; the structural
  claim — shared voter key ⟹ same consumer, verifier-infra ≠ consumer — is firm.)
- **identity / delegation / validator P-chain keys** — offline hardware wallet ONLY, never fwd (the
  custody doctrine; fwd holds hot operational keys only).

## What this resolves about clif

- **clif → the `claim` consumer.** Its durable, non-overlapping identity is reward harvesting
  (`ftso-reward-claim`). The rescope renames the consumer-identity string (`clif`→`claim`) + the
  capability prefix, and **splits FSP signing into four least-privilege roles**
  (`uptime-vote-{sign,submit}`, `reward-distribution-{sign,submit}`) — each pinned to one message-type
  or FSM method in the generated policy. They ride transitionally under `claim/` while clif is the only
  FSP signer. The GitHub repo MAY keep the name "clif"; only the consumer-identity string is load-bearing.
- **clif's FSP roles → `fsp`.** When the keyless flare-system-client lands, the four FSP roles migrate
  to `fsp/<net>/…` (same tokens, a `claim/`→`fsp/` prefix swap — no re-split) and are revoked from
  `claim`. The signing-policy key then lives in fwd **once** — today it is duplicated
  (flare-system-client keystore *and* fwd), a half-finished migration that `fsp` completes.

## Why now

`capability_id` immutability makes a boundary fixed today permanent. Right now there is exactly one live
consumer, both ends operator-controlled, with the reissue/reinstall and conformant generic-grant paths
freshly proven. The clif→`claim` rescope is **one onboard cycle**. Once `fsp` deploys against a taxonomy
that still says "clif" — and the `clif/<net>/fsp-*` overlap with `fsp/<net>/…` is minted — the
inconsistency is frozen into immutable ids. This ADR exists to be decided at the cheapest moment.

## Decided vs deferred

- **Decided (this ADR):** the generating principle + the five corollaries; the two-consumer tree
  (`fsp`, `claim`); `fdc` folds into `fsp` and `fdc-suite-deployment` is infra (no consumer); clif's
  end-state is the `claim` consumer.
- **Deferred (ADR-0001 §Scope, unchanged), with named triggers:**
  - the **clif→`claim` rescope execution** → operator-gated (touches live mainnet capability_ids);
  - the **`fsp` consumer build** → when the keyless-flare-system-client work is scheduled (also the
    forcing function for the `provider`/manifest framework, ADR-0001 §7);
  - **`register` / `payments` consumers** → when their `.env PRIVATE_KEY` actually migrates to fwd.

## Consequences

- A new workload's consumer boundary is now a mechanical question — "which registered key/identity does
  it sign with?" — not a judgment call; siblings stop accreting by repo or by protocol.
- The `provider` conflict-detector (deferred) gains a crisp invariant to enforce: **no wallet appears in
  two consumers' capabilities.** The tree is conflict-free by construction.
- `consumer-contract-v1` §6b ("adding a consumer") points here for *where a consumer's boundary is
  drawn*; this ADR points there for *what a conformant consumer must implement*.

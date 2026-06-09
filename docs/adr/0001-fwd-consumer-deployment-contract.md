# ADR 0001 — fwd consumer deployment contract and capability handoff

- **Status:** Accepted (contract). Rollout: pending — clif-migration-first.
- **Date:** 2026-06-09
- **Scope:** cross-project — `fwd`, `clif`, future fwd consumers, the future deploy repo.
- **Location:** **interim.** This file lives in the (untracked) root `proofs.africa/docs/`
  while no deploy repo exists — same convention as the root constitution. Its versioned home
  is the deploy repo's `docs/decisions.md`; copy the operative version there on creation and
  leave a pointer here.

## Context

This is a **working system**, not a greenfield design:

- **fwd** — zero-egress signer. Holds custody: keys, policy, wallets, caller tokens, audit.
  Installs itself; default-deny.
- **clif** — keyless consumer. Builds calldata, reads chain, asks fwd to sign, broadcasts,
  reports back. Holds no signing key.
- **clifctl** — host wrapper for the clif deployment (compose lifecycle).
- The epoch-anchored sign→claim daemon is **live-proven**: reward epoch 404 was signed and
  claimed automatically on **Flare and Songbird**.

Two forces make the *interface* — not the machinery — the thing to bed down now:

1. **More fwd consumers are certain** (e.g. an oracle, payments). Without a written contract,
   the first consumer's ad-hoc integration silently becomes the thing every later consumer
   reverse-engineers.
2. Today's naming leaks trust domains — notably **`clifwd`**, which is *fwd's* admin CLI
   wearing a `clif` prefix, making custody look like a clif concern.

This ADR codifies the cohesive operator/consumer interface the working system converges
toward, plus the migration path from today. It changes **no proven internals**.

## Decision

The organizing axis is **trust domain**; the durable primitive is the **`capability_id`**.

### 1. Trust-domain naming

| name | role | authority |
|---|---|---|
| `fwd` / **`fwdctl`** | the signer + its admin CLI | **custody** — the only surface that mutates signer state |
| `clif`, `<consumer>` | keyless application CLI | none over custody |
| `clifctl`, `<consumer>ctl` | host wrapper for that consumer's deployment | host / deployment only |
| **`provider`** | neutral runbook coordinator | **none native** |

- **The prefix carries authority, not the suffix.** `fwd*` = custody; `clif*` / `<consumer>*`
  = keyless. `ctl` just means "the control CLI for that domain."
- **`provider` deliberately drops the `ctl` suffix.** `ctl` (kubectl, systemctl) connotes
  direct control; the coordinator only *plans, presents, and verifies* — its name must not
  imply authority it lacks.
- **`clifwd` is retired** in favour of `fwdctl`.

### 2. Authority split — host vs custody

The coordinator **may hold host authority** (install Docker assets, clone, build, install
wrappers, start services). It must **never hold custody authority** (wallet create/import,
policy writes, caller-token minting, `setClaimExecutors`). Enforced **structurally, by
capability-absence** — the coordinator holds no fwd admin credential and has no code path that
writes custody — not by convention. Custody mutations happen only through human-gated
`fwdctl` / `sudo fwd …`.

### 3. `capability_id` — the spine

A fwd consumer capability is identified by one **immutable, consumer-namespaced
`capability_id`**, e.g. `clif/songbird/claimer-submit`. It is the single join key across the
whole lifecycle:

> spec **requests** it → fwdctl **grants/mints** for it → bundle is **keyed** by it →
> consumer **imports** by it → provider doctor **reconciles** on it → rotation **re-mints**
> it → conflict-detection **compares** ids across consumers.

Everything below references the `capability_id`.

### 4. Consumer spec = a human-reviewable custody diff

A capability request exists primarily to be **judged by a human at the custody gate** —
machine-readability is secondary. It MUST render as an adjudicable diff. `clif spec` is the
reference:

```
capability_id:    clif/songbird/claimer-submit
consumer: clif    network: songbird
fwd caller:       clif-claimer-songbird
wallet:           claimer-songbird
contract:         RewardManager 0x…
method:           claim(address,address,uint24,bool,…)
value:            0
recipient pinned: 0x…
rate:             4/hour, 8/day
→ approve / reject
```

If the spec cannot render that diff, it is **non-conformant**.

### 5. Handoff — one-shot local bundle, no consumer key

`consumer spec → fwd custody review → fwdctl mints a credential bundle keyed by
capability_id → consumer imports`. The bundle is **one-shot over local trust** (same-host,
mode-0600, consumed on import, short TTL). It is **not** sealed-to-a-consumer-key: a keyless
consumer must not hold a decryption key — that would re-expand the secret surface the membrane
exists to shrink. `<consumer>ctl import-credentials` is **idempotent and keyed by
capability_id**, so the same path is also the **rotation / revocation** channel, not a
one-time bootstrap.

### 6. `provider doctor` — three-way reconciliation

Three independent holders claim "what exists," joined on `capability_id`: **manifest**
(desired), **fwd** (granted), **consumer** (imported / in-use). doctor diffs all three:

| drift | meaning | remediation owner |
|---|---|---|
| manifest wants, fwd hasn't granted | pending custody gate | human → `fwdctl` |
| fwd granted, consumer hasn't imported | pending handoff | consumer |
| consumer using, manifest dropped it | orphaned capability | human → `fwdctl` (revoke) |
| fwd granted, manifest never asked | **ungoverned grant** (hand-edited policy) | surface loudly |

doctor **reads and classifies only**. Every remediation that touches custody is human-gated
`fwdctl`.

### 7. Manifest is truth; cursor is cache

The deploy manifest (consumers + per-consumer compat + networks) is the **source of truth**;
`provider plan/doctor` reconciles host + deployment toward it, gating at custody. The runbook's
progress cursor is a **cache, re-derivable from ground truth** (fwd health, on-chain
authorizations, each `<consumer>ctl status`) — never authority. Compatibility is pinned **per
consumer** as a tuple `{fwd_contract, fwd_client, consumer, membrane_protocol}` — a *pattern*;
exact values live in the manifest, not this ADR (they drift weekly).

## Invariants (the testable membrane)

Future `provider verify-consumer` / `provider doctor` check these:

1. A keyless consumer holds **no signing key and no unseal key** (only bearer caller tokens).
2. The coordinator has **no code path and no credential** that mutates custody.
3. Every capability **spec renders as a reviewable custody diff** (§4).
4. Credential **import is idempotent and keyed by `capability_id`**.
5. **fwd never reads or writes a consumer's env layout** — the consumer places its own tokens.
6. A **consumer never authors fwd policy** — it requests; the human-gated fwd side instantiates.

## Scope — decided vs deferred

- **Decided (this ADR):** the contract above.
- **Deferred** until consumer #2 forces them: the generic registry loader, the deploy repo +
  `provider` implementation, and `consumer-contract-v1`'s normative schemas / verb-lists
  (illustrative here, normative there). **Build the seam; defer the framework.**

## Ownership (anti-drift)

| surface | owner |
|---|---|
| custody, `fwdctl`, grant + mint + bundle | **fwd** repo |
| `clif`, `clifctl`, `clif spec` — the **reference** consumer | **clif** repo |
| `consumer-contract-v1`, `provider`, the manifest, conformance | **deploy** repo (when created) |
| this cross-cutting contract, until the deploy repo exists | **this ADR** |

## Migration (from the working present)

1. fwd ships **`fwdctl`**, keeps **`clifwd` as a deprecation alias**, removes it later.
2. clif updates its references to prefer `fwdctl`.
3. `fwd onboard --clif-env-dir` (fwd writing clif's env) survives **as N=1 compatibility
   only**. **clif's own migration to the bundle/import flow is the forcing function and must
   land before consumer #2** — the reference consumer must not run the deprecated pattern, or
   the first new consumer copies the leak.
4. No proven internals are removed: this is naming + contract-formalization + a membrane-clean
   handoff.

## Provenance / next

- Interim, untracked (root `proofs.africa/` is not a git repo, like the constitution). On
  deploy-repo creation, copy the operative version into its `docs/decisions.md` and leave a
  one-line pointer here.
- Pointers to add: the root constitution (`proofs.africa/CLAUDE.md`) and the fwd repo (a
  fwd-side task). clif carries a git-tracked breadcrumb as the reference consumer.

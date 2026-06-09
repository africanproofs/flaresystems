# ADR 0001 — fwd consumer deployment contract and capability handoff

- **Status:** Accepted (contract). Rollout: pending — clif-migration-first (see § Rollout status).
- **Date:** 2026-06-09
- **Scope:** cross-project — `fwd`, `clif`, future fwd consumers, the `provider` coordinator.
- **Location:** git-tracked in the **`flaresystems`** umbrella repo
  (`github.com/africanproofs/flaresystems`, `docs/adr/`) — the fwd-ecosystem home for the
  cross-project coordination layer. The earlier "untracked root file" durability gap is
  **closed** (remote-backed). If a dedicated deploy repo is later split out, this ADR moves
  with it.

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

## Rollout status (2026-06-09)

A point-in-time snapshot of the contract against reality (update on each material change).
**Reconciled 2026-06-09 against a code-level audit of clif / fwd / fwd-client** — the prior
snapshot under-reported clif's shipped import half and under-framed the fwd naming gap (both
corrected below). The contract is recorded; the reference consumer (clif) speaks **all of its
consumer-facing seams**; the custody, coordinator, and remaining handoff sides are unbuilt or
gated.

**Built — clif, the reference consumer (shipped, v0.5.37):**

- `capability_id` is real: `clif/<net>/{claim,fsp-sign,fsp-submit}` (`clif/config.py`),
  emitted by `clif spec`.
- The spec renders as a human-reviewable custody diff (§4) + machine-readable `clif spec --json`.
- consumer→coordinator surface: `clif doctor` + `status --json` + `clifctl doctor/status --json`.
- The compat tuple `{fwd_contract_expected, fwd_client, clif}`.
- **`clif import-credentials` / `clifctl import-credentials` — the consumer (import) half of the
  §5 handoff — is BUILT and C6-conformant** (`clif/credentials.py` + `clif/cli.py`, unit-tested):
  validates `version==1` + consumer + `expires_at` + mode-0600 + governed `capability_id`s,
  performs an idempotent id-keyed `.env.<net>` upsert (the rotation channel), one-shot-consumes
  the bundle on success, and never logs a token value. It validates against the **pinned v1
  bundle shape**; end-to-end against a *real fwd-emitted* bundle is blocked on the fwd emit half
  (live gap 1).

**Paper / unbuilt:** `clifwd`→`fwdctl` (and see live gap 2); an fwd grant minted *by*
`capability_id`; the **fwd emit half** of the one-shot bundle handoff (fwd has no `capability_id`
and no bundle emission — it still writes clif's env directly, live gap 1); `provider` (three-way
doctor + drift taxonomy + manifest + `verify-consumer`); the provider-side normative
`consumer-contract-v1` §7. Most are **deferred by design** until consumer #2 (§Scope). fwd is live
at **v1.1.0a96**; the fwd-side program is staged (PREPARATORY, *unauthorized*) in the Phase-0
reviewer brief `~/.claude/plans/fwd-dialect-phase0-brief.md` (Units 1–5), gated on the operator's
Unit 1.

**Two live gaps (not deferrals):**

1. **The `--clif-env-dir` forcing function is unmet — but the consumer half is done.** clif's
   import side is built + conformant (above); the blocker is the **fwd side**. fwd (v1.1.0a96)
   still provisions clif via `fwd onboard --clif-env-dir`, writing clif's `.env.<net>` directly —
   the §Migration pattern to retire *before* consumer #2, and a standing breach of Invariant #5
   ("fwd never reads or writes a consumer's env"). Closing it needs fwd's bundle-emission side
   (custody — unbuilt, gated). So the exemplar is clean on spec/doctor/import, yet the *live*
   handoff is still the env-write leak until fwd emits bundles.
2. **fwd has not adopted the dialect — and its current doctrine runs the other way.** fwd prescribes
   its own doctrine (no ADR-0001 reference); its admin surface is `clifwd` throughout (`pyproject.toml`
   console-script, `install/clifwd`, the Typer app) and its CLAUDE.md §Scope endorses it. On
   `clifwd`→`fwdctl` this is not merely "unadopted": a prior fwd **docs** ship (v1.1.0a39, 2026-05-31,
   predating this ADR) recorded the operator's choice to **reuse `clifwd` rather than add an
   `fwc`/`fwdctl` command**. So §1's later "clifwd is retired in favour of fwdctl" runs **against fwd's
   current doctrine and the operator's standing preference** — making the rename an **open, unbuilt
   task** (the brief's Unit 2) gated behind an operator-only constitutional decision (Unit 1), not a
   pending or mechanical edit. `--clif-env-dir` is likewise current, blessed fwd design. "fwd speaks
   the dialect" is a constitutional amendment to fwd + a multi-ship custody program through fwd's gated
   Opus/Sonnet/Operator workflow.

**Spine status:** `capability_id` threads **the consumer-side links it touches** — `spec`
(requests it), `import` (id-keyed import), and the consumer half of `rotate` (idempotent
re-import). The remaining links — `grant`, `bundle` (emit), `reconcile`, `conflict-detect`, and
the fwd half of `rotate` (re-mint) — are unbuilt, all on the **fwd / `provider`** side. The join
becomes fully real only when fwd grants by id and `provider` reconciles on it.

**Framework deferral (2026-06-09 — ADR-0002).** Building Units 3–5 + the one-shot bundle was
briefly authorized, then **reversed** after an operator-requested adversarial review flagged it as
premature (N=1 generalization, ~nil security delta, framework value only at multi-consumer scale).
The framework is now **deferred and gated on a concrete consumer #2** — see
[`0002-defer-fwd-bundle-grant-framework.md`](./0002-defer-fwd-bundle-grant-framework.md). Only the
`fwdctl` **alias** (not the full rename) and `--json` on existing reads remain as opportunistic
seam work.

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

- Now git-tracked **and remote-backed** in the `flaresystems` umbrella repo
  (`github.com/africanproofs/flaresystems`) — the loose-root-file durability gap is closed.
  `flaresystems` is the home for the cross-project coordination layer (`provider`,
  `consumer-contract-v1`, the manifest); if those are later split into a dedicated deploy
  repo, this ADR moves with them.
- Pointers: the root constitution (`proofs.africa/CLAUDE.md`) records the `flaresystems/`
  grouping + remote. Still to add: a fwd-repo pointer (fwd-side task); clif may carry a
  breadcrumb as the reference consumer.

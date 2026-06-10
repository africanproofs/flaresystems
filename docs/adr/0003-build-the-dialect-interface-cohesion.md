# ADR 0003 — Build the fwd dialect now (interface cohesion); supersede ADR-0002

- **Status:** Accepted. **Supersedes** ADR-0002. **ADR-0001 is unchanged** — this builds its deferred Units 3–5.
- **Date:** 2026-06-10.
- **Scope:** cross-project — `fwd`, `clif`, `fwd-client`, future consumers.
- **Location:** git-tracked in the `flaresystems` umbrella (`docs/adr/`).

## Context

ADR-0002 deferred the bundle/grant "framework" until a second consumer existed, gating on
**consumer population / operational scale**. That gate asked the **wrong question.** The core work
at this stage is **interface cohesion — a more cohesive *language* for interacting with the fwd
system** — and that is a **present need at N=1**, independent of how many consumers exist. The
language is incoherent *today* in three concrete ways:

1. `install/onboard`'s `--clif-env-dir` env-write is a **standing breach of Invariant #5** ("fwd
   never reads or writes a consumer's env").
2. `capability_id` — ADR-0001's spine — threads only the **consumer** side (`spec`/`import`); the
   fwd half (grant) is unbuilt, so the join is fictional.
3. fwd grants are keyed by `(name, policy_path)`, not by `capability_id`.

**Why the N=1 "wrong-abstraction" objection (ADR-0002) dissolves:** the generalization is anchored
on the **shared primitive**, not on clif. Every consumer is **`fwd-client`** (the canonical keyless
transport lib — verified **pure transport**: it wraps the sign/broadcast/report endpoints + error
taxonomy + idempotency, and models **no** dialect concept; it needs **no change**) **+
consumer-specific calldata / capability-config.** So building the dialect on `fwd-client` +
`capability_id` + **clif as the *reference* consumer** generalizes *by construction* — the
abstraction anchors on the proven transport primitive and the id spine, not on clif's idiosyncrasies.
clif is the reference, not a sample-of-one.

This **supersedes** ADR-0002 — but **keeps the adversarial review's findings as binding constraints**
(below), which is what makes the supersession credible rather than a re-override.

## Decision

Build the dialect now, through fwd's gated workflow, with clif as the reference consumer.

### Locked design decisions (operator, 2026-06-10)
1. **`capability_id` lives in the policy schema only** (`CallerBinding` + the audit row) — **NO
   custody-DB / Alembic migration.** Unit 5 reads the live policy; the join needs no DB column.
2. **Unit 3 scope:** fwd ingests `clif spec --json`, attaches the `capability_id`, and **re-renders
   the ADR-0001 §4 custody diff** for the operator's judgment; **policy *content* (contract / method
   / recipient / rate) stays template-driven** (`generate_policy` unchanged). Respects Invariant #6
   (consumer requests; the human-gated fwd side instantiates). The consumer never authors policy
   content.
3. **`doctor`** (three-way reconcile: manifest=desired vs fwd=granted vs consumer=imported, joined
   on `capability_id`) ships **now as a runbook**, not a deployable — Units 3+5 make the three legs
   machine-readable and joinable; the reconcile *logic* is a runbook diffing the three `--json`
   outputs. This keeps ADR-0002's correct insight ("at N=1 a runbook is the reconciliation engine").

### Build now (interface cohesion)
ADR-0003 (this) · **Unit 3** — `capability_id`-keyed grant (policy-only; spec→id+diff) · **Unit 4a**
— one-shot bundle emit (additive; `env_write` unchanged) + the **clif lockstep ship** + the Songbird
canary · **Unit 5** — granted-capabilities read surface (reads the live policy) · **Unit 4b** —
retire `env_write` / `--clif-env-dir` (**closes Invariant #5** — the non-aesthetic payoff; *last*,
gated on the 4a canary proof) · the **`doctor` runbook** · a **descriptive** "consumer dialect"
reference doc (point at clif as the reference implementation).

### Defer to N≥2 (genuinely population-dependent)
The `provider` coordinator as a standalone deployable · cross-consumer conflict-detection (empty at
N=1) · the *normative* `consumer-contract-v1` with conformance for arbitrary consumers · the generic
registry / manifest loader · **any *code* extraction** of the consumer dialect into a shared package
(`fwd-client` stays pure transport; the second consumer reveals the truly-shared surface — extracting
from one consumer is the premature-abstraction risk ADR-0002 rightly named).

## Constraints (the adversarial residue — carried from ADR-0002 as binding design requirements)
- **Revocation first-class:** Unit 5 makes revocation-state visible by `capability_id`; **revoke-by-
  id** as an *action* is a small follow-on — the program is **not "done" on the custody-lifecycle
  axis until revoke-by-id exists** (revocation is where custody mistakes are irreversible).
- **Immutability + rotation:** `capability_id` is immutable across rotation (re-mint + re-emit the
  *same* id, new token); the loader uniqueness check must NOT reject a rotation.
- **Bundle-leakage threat model, designed before Unit-4a code:** mode-0600 both sides, gitignored,
  the bundle path **OUTSIDE backup / litestream scope**, short TTL (~10 min), one-shot consume; a
  *failed* import leaves the file until TTL — document operator cleanup. The bundle is the only
  artifact carrying plaintext caller-token values outside fwd's DB.
- **Core #19:** the `capability_id` audit arm (incl. the commit-before-raise `CallerExistsError`
  path) is verified against the **real `session_scope` rollback**, not a mock.
- **Diff determinism:** capabilities are sorted by `capability_id` in both clif's emission and fwd's
  re-render → re-runs produce a byte-identical diff (no operator-diff fatigue).
- **Golden-test coupling:** fwd's Unit-4a bundle golden test pins to clif's **real** `validate_bundle`
  (or a CI drift-check), never a hand-copied fixture (clif's importer is the frozen acceptance oracle).
- **No scope creep:** do NOT "tidy" `install/onboard`'s `clifwd` references — the `fwdctl` alias
  resolves identically; the full rename is deferred.

## Sequencing
`a97` naming (DONE / live) → **ADR-0003** → **a98 Unit 3** (keystone) → **a99 Unit 4a + clif lockstep
+ canary** → **a100 Unit 5** → **a101 Unit 4b** (gated on the 4a canary). The `doctor` runbook +
consumer-dialect doc land alongside (coordination layer).

## Membrane & gating
The umbrella/coordination layer (this ADR, the consumer-dialect doc, the doctor runbook, the canonical
prompts) is drafted here; it touches no `fwd/` source. Each fwd unit is a constitutional-amendment /
feature ship through fwd's **Opus-prescribes / Sonnet-implements / Operator-gates** workflow, with its
own `docs/decisions.md` D-record. The clif lockstep is a clif-repo ship. The operator gates every prod
cutover (`~/.claude/plans/fwd-cutover-runbook.md`).

## Relationship to ADR-0001 / ADR-0002
Re-affirms ADR-0001's contract (this builds its deferred Units 3–5). **Supersedes ADR-0002** on the
*axis*: ADR-0002 gated on scale; the driver is coherence, present at N=1. ADR-0002 stays in the
record as "tested, briefly overridden, re-affirmed, then superseded on a re-framed axis" — its six
captured requirements live on here as constraints.

## Provenance
The re-framing is the operator's (2026-06-10): "core work at this stage is a better interface and a
more cohesive language; clif can do a lot for the framework since any new caller is based on the same
primitives — `fwd-client`." Grounded by a read-only design pass confirming `fwd-client` is pure
transport (the dialect is orthogonal to it) and the exact fwd touch points for Units 3/4/5. The
candidate canonical prompts (`~/.claude/plans/fwd-canonical-prompt-{unit3,unit4a,unit5}*.md` +
`clif-ship-consume-fwd-bundle-lockstep.md`) are re-activated under this ADR with the decision-1/2
narrowing applied.

# ADR 0002 — Defer the fwd bundle/grant framework; gate it on a concrete consumer #2

- **Status:** **SUPERSEDED by [ADR-0003](./0003-build-the-dialect-interface-cohesion.md)** (2026-06-10) — ADR-0002 gated on consumer *scale*; the driver is interface *coherence*, present at N=1. Its six captured requirements are carried forward as binding constraints in ADR-0003. **Date:** 2026-06-09.
- **Scope:** cross-project — `fwd`, `clif`, future consumers, the `provider` coordinator.
- **Location:** git-tracked in the `flaresystems` umbrella (`docs/adr/`). It **re-affirms**
  ADR-0001 §Scope ("build the seam; defer the framework until consumer #2 forces them") with an
  explicit, checkable gate, and **supersedes the "build now" framing** of the Phase-0 reviewer
  brief (`~/.claude/plans/fwd-dialect-phase0-brief.md`).

## Context

ADR-0001 deferred the bundle/grant/coordinator machinery "until consumer #2 **forces** it." On
2026-06-09 the operator briefly ratified building the full framework now — the brief's Units 3–5
(`capability_id`-keyed grants; one-shot bundle emission + retiring `--clif-env-dir`; a granted-id
read surface) — on the trigger "consumer #2 is **imminent**." An operator-requested friendly-
adversary review challenged it ("halt and wait for consumer #2"), and the team reversed. (The
anticipated #2 is an oracle / payments service, but this ADR's gate is **consumer-agnostic** — any
real second consumer.)

Grounds for the reversal:

- **N=1 generalization.** There is one consumer (clif). "Imminent" is not "forces it." Reshaping
  the custody daemon's grant + secret-handoff around a single consumer risks the wrong
  abstraction — the precise risk deferral exists to avoid, and worst in key-custody code.
- **~Nil security delta.** Caller tokens land in the consumer's env either way; the "bundle" only
  changes *who writes the file* and *adds* a transient plaintext-token artifact. The benefit is
  membrane-purity / least-privilege, **not** reduced key exposure.
- **Scale mismatch.** The framework's payoff — reconciliation, rotation, drift-detection across
  many capabilities, a `provider` coordinator — materializes at **multi-consumer scale with
  automated coordination**. At N=1→2 with one human operator, a **runbook** is the reconciliation
  engine.
- **The one non-aesthetic goal is achievable without the framework.** Closing the Invariant-#5
  env-write gap needs only `fwd callers create --json | <consumer>ctl import-credentials --from -`
  (the consumer writes its own env) — **no** bundle protocol, **no** `capability_id` re-keying.

## Decision

1. **DEFER Units 3–5 and the one-shot bundle protocol.** They are **candidate design, not
   authorized work**. The drafted canonical prompts
   (`~/.claude/plans/fwd-canonical-prompt-{unit3,unit4a,unit5}*.md` +
   `clif-ship-consume-fwd-bundle-lockstep.md`) are the candidate implementation, banner-marked
   **NOT AUTHORIZED**.
2. **Rescope the naming change** to the `fwdctl` **alias only** (keep `clifwd`), done
   **opportunistically** — **not** the full ~250-occurrence rename as a dedicated ship. (Supersedes
   the `a97` prompt as drafted.)
3. **Onboard any future consumer #2 with current tools + a runbook first** (consumer emits a
   human-reviewable spec → operator reviews → `callers create` → consumer's own
   `import-credentials --from -` writes its env → runbook verifies live). **Document any friction
   precisely** — the friction is the data that defines the framework.

## The unlock gate (concrete — designed to trip on evidence, not vibes)

Units 3–5 (or a re-scoped subset) unlock **only when BOTH** hold:

- **(a)** a **real** consumer #2 exists and has produced a **concrete capability spec**; AND
- **(b)** the runbook onboarding path **failed in a documented, custody-relevant way** — the
  current `caller` / `policy_path` / env model genuinely cannot express the requirement, OR the
  **same** friction recurred across two consumers.

"Cleaner," "imminent," or "already designed" do **not** trip the gate. When it trips, the
documented failure defines the **minimal** increment — re-scope from the real requirement rather
than defaulting to the full Units 3–5.

## Authorized now / opportunistic / deferred

| band | content |
|---|---|
| **Now (this ADR)** | record the decision; mark the prompts candidate-not-authorized; correct the prior "build authorized" record. |
| **Opportunistic** (no forcing function — only when already touching those files) | the `fwdctl` alias; `--json` on existing fwd reads (`callers/wallets/policy list`). Neither bakes in the `provider` abstraction. |
| **On consumer #2** | the runbook path above (+ the minimal `--from -` stdin handoff, which closes Invariant #5 without the framework). |
| **Deferred behind the gate** | `capability_id`-keyed grants; the bundle protocol; the granted-id coordinator surface; the `provider` coordinator. |

## Future requirements (captured now, for the gated design)

If/when the gate trips, the framework MUST address (surfaced by the adversarial review):

- **Revocation** as a first-class lifecycle (the real custody test — not an afterthought).
- **Audit migration** — pre-existing audit rows lack `capability_id`; the cross-migration story
  must be boring and explicit.
- A **bundle-leakage threat model** — shell history, logs, backups, support bundles, file perms —
  designed **before** code.
- **Schema / DB-migration** blast radius (re-keying grants by `capability_id`).
- **`capability_id` immutability + explicit rotation semantics** — an id is never repurposed.
- **Operator-diff fatigue** — the custody diff stays short, stable, rare, or it is ceremony, not a
  control.

## Relationship to ADR-0001

Re-affirms ADR-0001 §Scope and makes its gate explicit + checkable. It changes none of ADR-0001's
contract; it records that the contract's deferral discipline was **tested, briefly overridden, and
re-affirmed**.

## Provenance

Reversal prompted by an operator-requested friendly-adversary LLM review (2026-06-09; verdict
"halt-and-wait-for-consumer-#2"). The agent-process lesson (re-raise the strongest concern on an
override in custody work; polished specs can launder a premature decision) is captured in agent
memory.

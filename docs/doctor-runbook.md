# fwd `doctor` — three-way capability reconcile (RUNBOOK)

- **Status:** runbook (ADR-0003 decision 3 — `doctor` is a **runbook**, not a deployable, at N=1).
  The `provider` coordinator + **cross-consumer** conflict-detection are deferred to N≥2.
- **Purpose:** detect drift between what a consumer **desires**, what fwd has **granted**, and what
  the consumer has **imported** — joined on `capability_id`. At N=1 this reconciles one consumer's
  three independent views; the three legs are machine-readable, so the reconcile is a `--json` diff.

## The three legs
| leg | command | what it yields |
|---|---|---|
| **DESIRED** (manifest) | `clif spec --json` | the `capability_id`s the consumer **requests**. At N=1 the consumer's own spec *is* the manifest. |
| **GRANTED** (fwd) | `fwdctl capability list --json` | the `capability_id`s fwd's **live policy** grants. **[lands with Unit 5]** — until Unit 5 ships, read manually: `clifwd callers list` + the `CallerBinding`s in the loaded `policy.yaml`. |
| **IMPORTED** (consumer) | `clif doctor --json` → `.capabilities[].configured` | which ids the consumer holds tokens for. |

## The reconcile (diff the three id-sets, joined on `capability_id`)
| drift | condition | meaning | remediation |
|---|---|---|---|
| **pending-gate** | desired, not granted | awaiting the custody gate | human → `fwdctl capability grant` |
| **pending-handoff** | granted, not imported | awaiting the bundle | consumer → `clifctl import-credentials` |
| **orphaned** | imported, not desired | dropped capability | human → revoke (revoke-by-id is a follow-on) |
| **ungoverned-grant** | granted, **never desired** | hand-edited policy | **SURFACE LOUDLY** → investigate |

The **ungoverned-grant** row is the worst drift and the reason the GRANTED leg reads the **live
policy**, not the audit log: a hand-edited `CallerBinding` that no `spec` asked for appears in the
live policy but in no grant-audit row.

## N=1 procedure
Run the three `--json` commands; diff their `capability_id` sets and classify per the table (a tiny
script or a manual diff — **no coordinator binary at N=1**). When a second consumer exists, the
cross-consumer "does A's grant collide with B's?" check and the `provider` deployable that automates
this become worthwhile (ADR-0003 defers them until then).

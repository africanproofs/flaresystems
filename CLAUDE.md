# flaresystems — umbrella for the fwd signer system + its keyless consumers

> Co-locates the **fwd** ecosystem and tracks the cross-project coordination
> layer (decision records + the future deployment/`provider` runbook) that binds
> it together. Remote: `github.com/africanproofs/flaresystems`. This umbrella
> tracks **only** the coordination layer — the member projects below are
> independent repos.

## What lives here

| dir | role | trust domain | own repo |
|---|---|---|---|
| `fwd/` | zero-egress signer — keys, policy, wallets, caller tokens, audit | **custody authority** | local |
| `fwd-client/` | shared keyless client lib (Python + Go) | keyless transport | `github.com/africanproofs/fwd-client` |
| `clif/` | keyless FTSO reward claimer + FSP signer — the **reference consumer** | keyless | `github.com/africanproofs/clif` |
| `docs/adr/` | cross-project architecture decisions for the fwd ecosystem | coordination | **this repo** |

Members are **independent git repositories** with their own remotes and history.
They live inside this folder for co-location and are **gitignored from the
umbrella by design** — each is tracked only by its own `.git`. The umbrella
commits **only** `docs/adr/` (and, when they land, the deferred coordination
artifacts below).

## THE working rule — never sweep a member into an umbrella commit

Each member is its **own repo with its own CLAUDE.md**. To work on `fwd`,
`fwd-client`, or `clif`: navigate **into** that member directory, read **its**
CLAUDE.md, and commit **in that repo**. The members are gitignored here on
purpose; an umbrella commit must contain coordination-layer files only
(`docs/adr/`, future `provider`/`consumer-contract-v1`/manifest). If a `git
status` at the umbrella root shows member-internal files staged, STOP — you are
in the wrong repo. The umbrella never carries a member's source.

## The trust-domain membrane (ADR-0001 — the binding contract)

The organizing axis is **trust domain**; the durable primitive is the
**`capability_id`**. **The prefix carries authority, not the suffix.**

- `fwd*` / **`fwdctl`** — **custody authority**: the only surface that mutates
  signer state (keys, policy, wallets, caller-token minting, `setClaimExecutors`).
  (`clifwd` is retired in favour of `fwdctl`.)
- `clif*` / `<consumer>*` — **keyless**: builds calldata, reads chain, asks fwd
  to sign, broadcasts, reports back. Holds **no signing key, no unseal key** —
  only bearer caller tokens.
- `<x>ctl` (`clifctl`, `<consumer>ctl`) — that domain's **deployment wrapper**:
  host/compose lifecycle only.
- `provider` — neutral **runbook coordinator**: **no native authority**. May
  hold host authority (clone, build, install wrappers, start services); **never**
  custody authority. Drops the `ctl` suffix deliberately — it plans, presents,
  and verifies, and **pauses at the human-gated `fwdctl`** custody gate.

The full contract is `docs/adr/0001-fwd-consumer-deployment-contract.md`. Its
load-bearing decisions — **do not relitigate**:

- **`capability_id` is the spine** — one immutable, consumer-namespaced id (e.g.
  `clif/songbird/claimer-submit`) joins spec → grant → bundle → import →
  reconcile → rotate → conflict-detect.
- **A consumer spec renders as a human-reviewable custody diff** — judged at the
  custody gate; `clif spec` is the reference. If it can't render the diff, it's
  non-conformant.
- **Handoff is a one-shot local bundle, no consumer key** — same-host, mode-0600,
  consumed on import, short TTL; **not** sealed-to-a-consumer-key (a keyless
  consumer must hold no decryption key). `import-credentials` is idempotent and
  keyed by `capability_id`, so it is also the rotation/revocation channel.
- **`provider doctor` is three-way reconciliation** — manifest (desired) vs fwd
  (granted) vs consumer (imported), joined on `capability_id`; reads and
  classifies only, every custody remediation is human-gated `fwdctl`.
- **Manifest is truth; cursor is cache** — the runbook cursor is re-derivable
  from ground truth, never authority.

## Deferred — build the seam, defer the framework

Not yet built; deferred until **consumer #2** forces them (ADR-0001 §Scope):
the **`provider`** coordinator implementation, **`consumer-contract-v1`**'s
normative schemas/verb-lists, and the deploy **manifest**. clif's own migration
to the bundle/import handoff is the forcing function and lands **before**
consumer #2 — the reference consumer must not run the deprecated
`fwd onboard --clif-env-dir` pattern, or the first new consumer copies the leak.

## Commits (inherited AP doctrine)

A single terse conventional line — `feat: update`, `fix: update`,
`docs: update`, `chore: maintenance`. No body, no specifics, no rationale.
**Never** add a `Co-Authored-By: Claude`, an AI co-author, or a "Generated with"
line to any commit, PR, tag, or release — strip it if a tool adds one. The
operator is the sole author. Umbrella commits touch coordination-layer files
only; member work is committed inside the member repo.

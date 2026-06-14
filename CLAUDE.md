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
| `clif/` | keyless FTSO reward claimer + FSP signer — the **reference consumer** (consumer #1 = `claim`) | keyless | `github.com/africanproofs/clif` |
| `fsp/` | **consumer #2** wrapper — declares the fsp capability set (`fsp spec`, conformant to fwd's `parse_spec`) + `import-credentials` for the two forked Go voters; holds no keys, signs nothing | keyless / onboard | `github.com/africanproofs/fsp` |
| `provider/` | neutral runbook **coordinator** (ADR-0001 §7) — manifest + three-way `provider doctor` + cross-consumer conflict detection + `verify-consumer`; reads/classifies/plans, never custody | coordination | **this repo** (umbrella-tracked) |
| `docs/adr/` | cross-project architecture decisions for the fwd ecosystem | coordination | **this repo** |

The `fsp` consumer's actual signing services are the two AP **forks** of the Flare
voter — `github.com/africanproofs/{flare-system-client, fast-updates}` — each with a
dual-mode `Signer` seam (`local` = byte-identical to upstream, `fwd` = keyless with
per-capability token routing). They live outside this umbrella, under `africanproofs`.

Members (`fwd`, `fwd-client`, `clif`, `fsp`) are **independent git repositories** with
their own remotes/history, co-located here and **gitignored from the umbrella**. The
umbrella itself commits the **coordination layer — `docs/adr/` + `provider/`** (provider
is umbrella-*tracked*, not a member).

## THE working rule — never sweep a member into an umbrella commit

Each member is its **own repo with its own CLAUDE.md**. To work on `fwd`,
`fwd-client`, `clif`, or `fsp`: navigate **into** that member directory, read **its**
CLAUDE.md, and commit **in that repo**. The members are gitignored here on
purpose; an umbrella commit must contain coordination-layer files only
(`docs/adr/`, `provider/`, `consumer-contract-v1`/manifest). If a `git
status` at the umbrella root shows a **member's** internal files staged (e.g. `fsp/…`,
`clif/…`), STOP — you are in the wrong repo. (`provider/` IS umbrella-tracked — that's
expected.) The umbrella never carries a member's source.

## The trust-domain membrane (ADR-0001 — the binding contract)

The organizing axis is **trust domain**; the durable primitive is the
**`capability_id`**. **The prefix carries authority, not the suffix.**

- `fwd*` / **`fwdctl`** — **custody authority**: the only surface that mutates
  signer state (keys, policy, wallets, caller-token minting, `setClaimExecutors`).
  (`fwdctl` is the canonical custody CLI — the in-container shim since fwd 0a27fd5;
  `clifwd` remains a compatibility alias. The full in-app rename stays deferred.)
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

## Status — consumer #2 + the framework core are now BUILT (was "Deferred")

**The seam is live AND the framework is built (2026-06-13/14).** The handoff ships both
ways (`fwd onboard` for clif's turnkey path; `fwdctl capability grant --emit-bundle
--config NETWORK=<net> …` for the consumer-generic path, with a pre-mint conformance
gate). **Consumer #2 started from the generic path (`consumer-contract-v1` §6b), NOT by
forking clif's onboard.**

**Consumer #2 = `fsp`** (the keyless flare-system stack) is built end to end — both forked
Go voters with the dual-mode `Signer` seam, the `fsp/` wrapper (`spec` conformant to fwd's
`parse_spec`), and fwd's complete fsp capability set + bounded self-submit carve-outs,
**deployed on l-desktop** (`c916446`), backward-compatible (clif unaffected). The once-
deferred **framework is now built**: the **`provider`** coordinator CORE — manifest,
three-way `provider doctor` + the 4 drift types, cross-consumer conflict detection,
`verify-consumer` (C2/C3/C7/C8). See memory `fsp-consumer-build-complete.md`.

**Still remaining (gated / integration / loose ends — NOT a fresh build):**
- The **live canary** — onboard fsp (`fwdctl capability grant` against `fsp spec`) → flip
  `backend=fwd` on Songbird → Flare. Operator-gated; runbook
  `~/.claude/plans/fsp-canary-runbook.md`; fwd deploy procedure = memory
  `fwd-reinstall-preserves-custody.md`.
- **Off-host transport** — fwd is deployed on l-desktop, but the FSP voter runs elsewhere;
  if not co-located, **fsp is the first off-host consumer** (the named ADR-0001 trigger) and
  forces the remote handoff / nonce-bridge. **Resolve the FSP-voter host BEFORE the fsp
  onboard** — memory `fsp-canary-topology-blocker.md`.
- provider **live adapters** (real fwd-granted + consumer reads — stubbed), `fspctl`, the
  remaining `provider` verbs (`plan`/`next`/`verify`) + the C1/C4/C5/C6/C9 runtime checks,
  and the fwd-client **Python** lockstep mirror.
- The policy-template extension still fires only if a future consumer's roles don't fit the
  template+`_ROLE_CONVENTION` pattern (operator-gated fwd change — Invariant #6).

## Commits (inherited AP doctrine)

A single terse conventional line — `feat: update`, `fix: update`,
`docs: update`, `chore: maintenance`. No body, no specifics, no rationale.
**Never** add a `Co-Authored-By: Claude`, an AI co-author, or a "Generated with"
line to any commit, PR, tag, or release — strip it if a tool adds one. The
operator is the sole author. Umbrella commits touch coordination-layer files
only; member work is committed inside the member repo.

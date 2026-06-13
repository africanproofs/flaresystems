# provider — neutral runbook coordinator

> Coordination layer for the fwd ecosystem. Tracked in the `flaresystems/`
> umbrella repo (not a member repo; no separate remote). Owned by
> `consumer-contract-v1` §7 + ADR-0001.

## Authority: NONE (non-negotiable)

`provider` has **no native authority** and **no custody credential**.

It **never**:
- holds or touches a fwd admin credential
- writes fwd policy
- mints or rotates caller tokens
- calls `fwdctl` or any custody-mutating surface
- writes any consumer's `.env`

Every custody remediation (grant, revoke, rotate) is human-gated `fwdctl`.
This is enforced structurally by capability-absence, not convention.

The authority split is defined in ADR-0001 §2 and consumer-contract-v1 §0.

## What provider does

`provider` reads, classifies, and presents:

| verb | action |
|---|---|
| `provider doctor` | three-way reconciliation: manifest vs fwd vs consumer (§7.2 drift taxonomy) |
| `provider conflict` | cross-consumer wallet conflict detection (ADR-0004 tree invariant) |
| `provider verify-consumer <x>` | §8 conformance checklist against one consumer |
| `provider review` | render pending custody diffs awaiting the human gate |
| `provider plan/next/verify` | stubs — deferred until consumer #2 is named |

## The three sources (joined on capability_id)

- **manifest** (desired) — `provider-manifest.yaml` at the umbrella root (§7.1)
- **fwd** (granted) — capability_ids fwd has granted in policy; real fwd-admin
  adapter deferred; file-backed stub available for offline use
- **consumer** (configured) — from `<x> doctor --json` `capabilities[].configured`

## The drift taxonomy (§7.2)

| drift | condition | remediation |
|---|---|---|
| `pending-gate` | manifest wants, fwd hasn't granted | human → `fwdctl` |
| `pending-handoff` | fwd granted, consumer hasn't imported | `<x>ctl import-credentials` |
| `orphaned` | consumer using, manifest dropped | human → `fwdctl` revoke |
| `ungoverned-grant` | fwd granted, manifest never asked | surface LOUDLY |

## Stack

- Python 3.12, Poetry
- typer, pydantic, pyyaml
- No fwd dependency (the membrane runs one way; fwd must never import provider)

## Running tests

```bash
cd /home/l/working/gitlab.com/proofs.africa/flaresystems/provider
poetry install
poetry run pytest -q
```

## manifest location

`provider-manifest.yaml` lives at the umbrella root (`flaresystems/`), not
inside `provider/`. The CLI resolves it from the current directory or one
level up. Pass `--manifest <path>` to override.

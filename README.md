# flaresystems

Umbrella workspace for the **fwd signer system** and its keyless consumers, and the
home of the cross-project coordination layer (the deployment/`provider` runbook and the
shared decision records) for the fwd ecosystem. Repo:
`github.com/africanproofs/flaresystems`.

The member projects below are **independent git repositories** with their own remotes
and history. They live inside this folder for co-location but are **gitignored here** —
each is tracked only by its own `.git`. This umbrella tracks only the cross-project layer.

## Members (independent repos)

| dir | role | remote |
|---|---|---|
| `fwd/` | zero-egress signer — custody (keys, policy, wallets, caller tokens, audit) | local |
| `fwd-client/` | shared keyless client library (Python + Go) | github.com/africanproofs/fwd-client |
| `clif/` | keyless FTSO reward claimer + FSP signer (reference consumer) | github.com/africanproofs/clif |

## Tracked here

- `docs/adr/` — cross-project architecture decisions for the fwd ecosystem.
  - `0001-fwd-consumer-deployment-contract.md` — the deployment + capability-handoff contract.
- _(future)_ the `provider` coordinator, `consumer-contract-v1`, and the deploy manifest.

## Trust domains (ADR 0001)

`fwd*` = custody authority · `clif*` / `<consumer>*` = keyless · `<x>ctl` = deployment
wrapper · `provider` = neutral runbook coordinator (no native authority; pauses at
human-gated `fwdctl`).

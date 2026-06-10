# Consumer dialect — how to be an fwd consumer (DESCRIPTIVE reference)

- **Status:** **descriptive**, not normative. The *normative* `consumer-contract-v1` (with
  conformance checks for arbitrary consumers) is **deferred to N≥2** (ADR-0003) — you formalize from
  two data points, not one. This doc captures the pattern *as it exists today*, with **clif** as the
  reference implementation, so consumer #2 inherits it cleanly.
- **Derives from:** ADR-0001 (the contract) + ADR-0003 (build-the-dialect decision).

## Every consumer = two layers

### 1. The SHARED primitive — `fwd-client` (do not change it)
`github.com/africanproofs/fwd-client` — Python (`python/`) + Go (`go/`), lockstep. **Pure keyless
transport:** it wraps `sign-transaction` / `sign-fsp-message` / `broadcast-result` / `receipt` /
`get-transaction` / `healthz`, the **error taxonomy** (terminal vs retryable, with the 409 split),
and the **idempotency-key hashing**. It holds **no keys, no crypto, no dialect** (no `capability_id`,
no bundle, no spec). **Every consumer uses it unchanged.** Adding dialect to `fwd-client` is
forbidden — it would couple every consumer to one consumer's shape.

### 2. The CONSUMER-SPECIFIC dialect (you write this; clif is the reference)
| piece | what | clif reference |
|---|---|---|
| **a. Capability list** | a `Capability` per `<network>×<role>` yielding `capability_id = <consumer>/<network>/<role>` (immutable), `caller_token_env` (the env-var **name** the consumer reads its bearer token from), `wallet_name` (the fwd wallet name) | `clif/config.py::capabilities()` |
| **b. `spec` / `spec --json`** | the capability **request** fwd ingests + re-renders at the custody gate: `{consumer, network, compat, capabilities[]}` + a human-reviewable ADR-§4 diff | `clif/cli.py::spec` |
| **c. `import-credentials`** | `validate_bundle` (`version==1`, consumer match, expiry, mode-0600, governed `capability_id`s, env-injection guard) + idempotent **id-keyed** `.env.<net>` upsert (the rotation channel) + **one-shot consume** | `clif/credentials.py` — the **frozen acceptance oracle** fwd's bundle-emit conforms to byte-for-byte |
| **d. `<consumer>ctl`** | host wrapper: compose lifecycle + `import-credentials` + a `doctor` / `status --json` coordinator-scrape surface | `clif/install/clifctl`, `clif doctor`/`epoch status` |

## Invariants every consumer holds
- **Keyless:** no signing key, no unseal key — only bearer caller tokens (in its `.env`, placed by
  import). It builds calldata, asks fwd to sign (via `fwd-client`), broadcasts itself, reports back.
- **`capability_id` grammar:** `^<consumer>/<network>/<role>$`; **immutable** (a new authorization
  shape is a *new* id — never rename; renaming breaks every downstream holder joined on it).
- **Names, not values:** `spec`/`doctor`/`status` carry env-var **names** + `capability_id`s, never
  a token value. The value lives only in the consumer's `.env` and the one-shot bundle.
- **Consumer requests; fwd instantiates:** the consumer *requests* capabilities (`spec`); the
  human-gated fwd side authors the policy (Invariant #6). A consumer never authors fwd policy.

## For consumer #2
**Copy the clif PATTERN (pieces a–d) — do NOT inherit a base class.** There is no shared dialect
*package*, by design (ADR-0003): `fwd-client` is the only shared *code*; the dialect is *copied*,
not inherited, until the second consumer reveals which parts are truly shared vs clif-specific
(extracting a framework from one consumer is the premature-abstraction risk). When consumer #2
exists, this descriptive pattern is formalized into the normative `consumer-contract-v1` +
conformance checks (ADR-0001 §Ownership; deferred per ADR-0003).

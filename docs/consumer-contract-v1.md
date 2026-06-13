# consumer-contract-v1 — the fwd consumer deployment contract (NORMATIVE)

- **Status:** Normative. Versioned `consumer-contract-v1`.
- **Owner:** the `flaresystems` deploy repo (ADR-0001 §Ownership). This file is the
  authority `provider verify-consumer <x>` checks against.
- **Derives from:** [`docs/adr/0001-fwd-consumer-deployment-contract.md`](./adr/0001-fwd-consumer-deployment-contract.md)
  (the binding contract — read it first). The ADR decides; this file makes the
  ADR's "illustrative here, normative there" schemas concrete.
- **Reference consumer:** `clif` (`github.com/africanproofs/clif`). Every shape
  below is **derived from clif's actual outputs** — `clif spec --json`,
  `clif doctor --json`, `clif status/epoch status --json`, and
  `clif.config.capabilities()`. Where this file and clif's live behaviour ever
  diverge, **clif's behaviour is the ground truth** and this file is the defect.

> **Scope split (ADR-0001 §Scope).** §§1–6 + §8–§9 are the **consumer-side
> contract** — built, in use, conformance-checkable today against clif. §7 is the
> **provider side** — owned here, **DESIGN ONLY, NOT BUILT**; deferred until
> consumer #2 forces it. "Build the seam; defer the framework."

---

## 0. Terms & trust domains (ADR-0001 §1)

| name | role | authority |
|---|---|---|
| `fwd` / `fwdctl` | the zero-egress signer + its admin CLI | **custody** — the only surface that mutates signer state (keys, policy, wallets, caller tokens, nonces) |
| `<consumer>` (`clif`, …) | keyless application CLI | **none** over custody — builds calldata, reads chain, asks fwd to sign, broadcasts, reports back |
| `<consumer>ctl` (`clifctl`, …) | host wrapper for that consumer's deployment | **host / deployment only** (compose lifecycle, env placement) |
| `provider` | neutral runbook coordinator | **none native** — plans, presents, reconciles, verifies; holds no fwd admin credential |

**The prefix carries authority, not the suffix.** `fwd*` = custody; `<consumer>*`
= keyless. `ctl` means "control CLI for that domain." `provider` deliberately drops
`ctl` — it must not imply authority it lacks.

A **conformant consumer** is a keyless fwd consumer (ADR Invariant #1: holds no
signing key and no unseal key — only bearer caller tokens) that exposes the
command surface of §§2–5 with the JSON shapes and exit codes specified here.

---

## 1. `capability_id` — the spine (ADR-0001 §3)

A fwd consumer capability is identified by one **immutable, consumer-namespaced**
identifier:

```
<consumer>/<network>/<role>
```

- **`<consumer>`** — the consumer's stable name (`clif`).
- **`<network>`** — `flare` | `songbird` | `coston2` (one capability set per network).
- **`<role>`** — a stable role token within the consumer.

The `capability_id` is the **single join key** across the whole lifecycle:

> spec **requests** it → `fwdctl` **grants/mints** for it → bundle is **keyed** by
> it → consumer **imports** by it → `provider doctor` **reconciles** on it →
> rotation **re-mints** it → conflict-detection **compares** ids across consumers.

**It is immutable.** A role's authorization may change (contract, recipient, rate),
but its `capability_id` MUST NOT be renamed — renaming breaks every downstream
holder joined on it. A new authorization shape is a **new** `capability_id`.

### 1.1 clif's canonical roles (CANONICAL — do not rename)

clif's three live roles, emitted by `clif.config.capabilities()`:

| `capability_id` | role | fwd endpoint | what it authorizes |
|---|---|---|---|
| `clif/<net>/claim` | `claim` | `/v1/sign-transaction` | `RewardManager.claim(...)`, `value 0`, `_recipient` pinned |
| `clif/<net>/fsp-sign` | `fsp-sign` | `/v1/sign-fsp-message` | FSP message signing (UPTIME / REWARD_DISTRIBUTION) — Leg-1 |
| `clif/<net>/fsp-submit` | `fsp-submit` | `/v1/sign-transaction` | `FlareSystemsManager.signUptimeVote / signRewards` tx — Leg-2 |

> ADR-0001 §4 illustrated a `claimer-submit` role. That was **illustrative**.
> clif's actual ids (`claim`, `fsp-sign`, `fsp-submit`) are **canonical**. Tooling
> MUST treat them verbatim; **do not rename them** to match the ADR's example.

The `fsp-sign` / `fsp-submit` split is structural, not cosmetic: fwd forbids one
`policy_path` key appearing in both `permissions` and `fsp_permissions`, so a single
caller cannot span Leg-1 (`/v1/sign-fsp-message`) and Leg-2 (`/v1/sign-transaction`).
One `capability_id` = one caller token = one fwd policy block.

---

## 2. `<x> spec --json` — the capability request (ADR-0001 §3/§4)

The consumer's `spec` command renders its requested capabilities **two** ways. A
conformant consumer MUST produce BOTH:

1. **machine-readable** (`<x> spec --json`) — the capability-request JSON below;
2. **human-reviewable custody diff** (default, e.g. markdown) — §2.2.

> **"If it can't render the custody diff, it is non-conformant."** (ADR Invariant #3.)

### 2.1 `<x> spec --json` shape

```json
{
  "consumer": "clif",
  "network": "songbird",
  "compat": {
    "fwd_contract_expected": "v1.1.0a69",
    "fwd_client": "<fwd-client version>",
    "clif": "<clif version>"
  },
  "capabilities": [
    {
      "capability_id": "clif/songbird/claim",
      "role": "claim",
      "endpoint": "/v1/sign-transaction",
      "caller_token_env": "FWD_CALLER_TOKEN",
      "wallet_env": "FWD_WALLET_NAME",
      "wallet_name": "claimer-songbird",
      "contract": "0xE26AD68b17224951b5740F33926Cc438764eB9a7",
      "contract_name": "RewardManager",
      "method": "claim(address,address,uint24,bool,(bytes32[],(uint24,bytes20,uint120,uint8))[])",
      "value_wei": "0",
      "recipient_pinned": "0x7c3579aB3E647395c96a1EfC98aF9A31C5Ecc294",
      "suggested_rate": "8/day"
    }
    // ... one object per capability_id (clif emits claim, fsp-sign, fsp-submit)
  ]
}
```

**Per-capability required keys** (every object MUST carry all of these; a key whose
value is not applicable to the role is present with `null`):

| key | type | meaning |
|---|---|---|
| `capability_id` | string | `<consumer>/<network>/<role>` — immutable join key |
| `role` | string | the role token |
| `endpoint` | string | the fwd endpoint (`/v1/sign-transaction` or `/v1/sign-fsp-message`) |
| `caller_token_env` | string | env-var **name** the consumer reads the granted token from — **never the value** |
| `wallet_env` | string | env-var name for the fwd wallet **name** |
| `wallet_name` | string \| null | the configured fwd wallet **name** (a name, not a key); `null` if unset |
| `contract` | string \| null | target contract address; `null` for a detached signature (`fsp-sign`) |
| `contract_name` | string \| null | human label (`RewardManager`, `FlareSystemsManager`); `null` if none |
| `method` | string \| null | the method/message the capability authorizes |
| `value_wei` | string \| null | `"0"` for tx capabilities; `null` for `/v1/sign-fsp-message` |
| `recipient_pinned` | string \| null | the pinned recipient arg (claim only); `null` otherwise |
| `suggested_rate` | string \| null | **request only** — fwd policy is authoritative |

**`suggested_rate` is advisory.** It is a request the operator may tighten or
override when authoring fwd policy; the consumer never asserts it.

### 2.2 The human-reviewable custody diff (the adjudicable artifact)

A capability request exists primarily to be **judged by a human at the custody
gate**. The default (non-`--json`) `spec` output MUST render each capability as an
adjudicable block — the operator approves or rejects each one. Reference rendering
(from `clif spec` `_capability_block`):

```
### `clif/songbird/claim`  (claim)
- endpoint: `/v1/sign-transaction`
- fwd wallet: `claimer-songbird`  (env `FWD_WALLET_NAME`)
- caller token: clif holds it in env `FWD_CALLER_TOKEN` (granted by fwd; the value is never in this doc)
- contract: RewardManager `0xE26AD68b17224951b5740F33926Cc438764eB9a7`
- method: `claim(address,address,uint24,bool,(bytes32[],(uint24,bytes20,uint120,uint8))[])`
- value: `0`
- recipient pinned: `0x7c3579aB3E647395c96a1EfC98aF9A31C5Ecc294`
- suggested rate: 8/day  (request only — fwd policy is authoritative)
- → approve / reject
```

The diff MUST surface, per capability: the `capability_id`, the fwd wallet **name**,
the caller-token **env-var name** (with an explicit note the value is not shown), the
contract + method, the pinned value/recipient, and an approve/reject affordance. A
`spec` that cannot render this is **non-conformant** (§8 check C3).

---

## 3. `<x>ctl {status, doctor} --json` — the coordinator scrape seam

The consumer→coordinator surface. A conformant consumer exposes `doctor` and
`status` both as the application CLI (`<x> doctor`) and via its host wrapper
(`<x>ctl doctor`); `--json` is the coordinator scrape form. Exit codes and required
keys are derived from clif's `cli.py` + `autostate.py`.

### 3.1 `<x> doctor --json` — consumer self-check

Aggregates: keyless assertion, fwd reachability + `master` state, the consumer's
**imported** capability view (caller-token presence — NAMES only, never values), the
compat tuple, and daemon status.

```json
{
  "consumer": "clif",
  "network": "songbird",
  "ok": true,
  "keyless": true,
  "compat": { "fwd_contract_expected": "v1.1.0a69", "fwd_client": "...", "clif": "..." },
  "fwd": { "endpoint": "http://fwd:8080", "reachable": true, "master": "ok" },
  "capabilities": [
    { "capability_id": "clif/songbird/claim",      "role": "claim",      "configured": true  },
    { "capability_id": "clif/songbird/fsp-sign",   "role": "fsp-sign",   "configured": false },
    { "capability_id": "clif/songbird/fsp-submit", "role": "fsp-submit", "configured": false }
  ],
  "daemon": { "present": true, "degraded": false, "summary": "healthy", "exit_code": 0 }
}
```

**Required keys:** `consumer`, `network`, `ok` (bool), `keyless` (bool — MUST be
`true`), `compat`, `fwd` (`endpoint`/`reachable`/`master`), `capabilities[]`
(each `capability_id`/`role`/`configured`), `daemon`
(`present`/`degraded`/`summary`/`exit_code`).

- `capabilities[].configured` is the consumer's **imported** view: `true` iff the
  consumer holds the caller token for that role in its env (NAME-keyed presence
  check — the value is never read into the report).
- `fwd.reachable` is a transport probe; `fwd.master` is fwd's `/healthz` master
  state. `fwd_ok` ⇔ `reachable && master == "ok"`.

**Exit codes (`<x> doctor`):**

| code | meaning |
|---|---|
| `0` | healthy — fwd reachable with `master == "ok"` **and** no running daemon is failing |
| `2` | fwd unreachable / `master != "ok"`, **or** a present daemon reports a non-zero status |

> Daemon **absence** is not a doctor failure (a consumer may be configured but its
> daemon not yet started). A **present** daemon with a non-zero `exit_code` fails doctor.

### 3.2 `<x> status --json` — daemon health

The scrapable health of the consumer's running daemon (clif: the canonical
`epoch status`; the legacy `status` / `fsp status` share the same shape + codes).

```json
{ "ok": true, "exit_code": 0, "summary": "healthy", "report": { ... } }
```

**Required keys:** `ok` (bool), `exit_code` (int), `summary` (string), `report`
(object \| null — the raw daemon status file, or `null` when absent).

**Exit codes (`<x> status` / `<x> epoch status`):**

| code | meaning |
|---|---|
| `0` | healthy — daemon fresh and not degraded. A daemon deliberately **disabled** (e.g. `FSP_AUTO_ENABLED!=true`, idling, not signing) is also `0` (healthcheck stays green). |
| `2` | **degraded** — degraded reasons present, **or** the status file is stale (older than `_DEAD_INTERVALS × poll_interval`, i.e. daemon dead/stuck) |
| `3` | **no state** — the daemon has never written a status file |

> doctor (§3.1) and status (§3.2) use **different** code spaces by design: doctor
> is `{0, 2}`; status is `{0, 2, 3}`. `3` ("no daemon state") is a status-only
> condition. A conformant consumer MUST NOT collapse them.

---

## 4. `<x>ctl import-credentials` — the one-shot bundle handoff (ADR-0001 §5)

The credential handoff: `consumer spec → fwd custody review → fwdctl mints a bundle
keyed by capability_id → <x>ctl import-credentials`.

### 4.1 Bundle format (PINNED — both this spec and the consumer's importer MUST match)

A bundle is a **one-shot JSON file** `fwd` (via `fwdctl`) emits to a local host
path. It is protected by **one-shot-consume + mode-0600 + same-host local trust + a
short TTL** — it is **NOT** encrypted to a consumer key. A keyless consumer holds no
decryption key (ADR-0001 §5 / Invariant #1); sealing the bundle to a consumer key
would re-expand the secret surface the membrane exists to shrink.

```json
{
  "version": 2,
  "consumer": "clif",
  "network": "songbird",
  "issued_at": "2026-06-09T12:00:00Z",
  "expires_at": "2026-06-09T12:10:00Z",
  "config": {
    "NETWORK": "songbird",
    "FWD_ENDPOINT": "http://fwd:8080",
    "IDENTITY_ADDRESS": "0x...",
    "CLAIM_RECIPIENT_ADDRESS": "0x...",
    "WRAP_REWARDS": "false",
    "FSP_AUTO_ENABLED": "true",
    "UPTIME_AUTO_ENABLED": "false",
    "EPOCH_REWARD_INITIAL_DELAY_SEC": "3600",
    "EPOCH_POLL_INTERVAL_SEC": "1800"
  },
  "capabilities": [
    {
      "capability_id": "clif/songbird/claim",
      "caller_token_env": "FWD_CALLER_TOKEN",
      "caller_token": "fwd_live_...",
      "wallet_name": "claimer-songbird"
    }
    // ... one entry per granted capability_id
  ]
}
```

| field | meaning |
|---|---|
| `version` | bundle schema version: **`2`** = the complete handoff (config + capabilities); `1` = the prior tokens-only format |
| `consumer` | MUST match the importing consumer's name |
| `network` | the network this bundle's tokens are for; selects the target `.env.<net>` |
| `issued_at` / `expires_at` | ISO-8601; import MUST refuse a bundle past `expires_at` |
| `capabilities[].capability_id` | the join key (§1); the import is keyed on this |
| `capabilities[].caller_token_env` | the env-var **name** to write the value into |
| `capabilities[].caller_token` | **the secret value**, delivered once (a bearer token — NOT a signing key) |
| `capabilities[].wallet_name` | the fwd wallet **name** for that capability (the importer writes it to the consumer's own `<wallet_env>`, which it knows because it governs the `capability_id`) |
| `config` | a flat `{ENV_VAR: string}` map of the consumer's **non-secret** network config (endpoint, identity/recipient addresses, behaviour flags, timings) — written verbatim into `.env.<net>`. **MUST include the consumer's network selector** — for clif this is **`NETWORK`** (the active chain); without it clif silently defaults to flare (`cli.py:715`), so a "complete handoff" that omits it is **not** complete. **NEVER a token or a signing key.** The importer **allowlists** the keys (§4.2) so the bundle cannot inject an arbitrary env var. |

### 4.2 Import semantics (NORMATIVE)

`<x>ctl import-credentials <bundle-path>` MUST:

1. **Verify** `version == 2`, `consumer` matches, `expires_at` is in the future, the
   bundle file is local + mode-0600, and **every `config` key is in the importer's
   allowlist** of known config env-vars (reject an unknown key — the bundle MUST NOT be
   able to inject an arbitrary env var), with clean values (no control chars / newlines).
   Refuse otherwise. (`version == 1`, tokens-only, MAY be accepted for back-compat during transition.)
2. **Be idempotent and keyed by `capability_id`** (ADR Invariant #4). For each bundle
   entry, write `<caller_token_env>=<value>` **and** `<wallet_env>=<wallet_name>` (the
   importer knows `<wallet_env>` because it governs the `capability_id`) into the consumer's
   per-network `.env.<net>`, replacing any existing line. Then write each allowlisted `config`
   `KEY=value` the same way. Re-running with a bundle for the same `capability_id` updates in
   place — the **same path is the rotation / config-refresh channel**. The `config` makes the
   bundle the **complete** handoff: fwd composes it; the consumer places its own env from it
   (Invariant #5 — fwd never touches `.env`).
3. **One-shot consume:** on success, **delete** the bundle file. A consumed bundle
   cannot be replayed.
4. **Never log a token value.** Logs/output reference `capability_id` +
   `caller_token_env` (names) only. (§8 check C7; §9.)
5. **Place its own env** (ADR Invariant #5): the consumer writes its own tokens into
   its own env layout. **fwd never reads or writes the consumer's env** — it emits
   the bundle; the consumer imports it.

Token **values** are bearer caller tokens the consumer already holds in `.env`
(NOT signing keys) — the keyless invariant is intact end to end.

---

## 5. `<x>ctl run / logs` — the deployment-wrapper verbs

The host wrapper (`<consumer>ctl`) owns the deployment lifecycle (compose). It holds
**host authority only** (ADR-0001 §2) — never custody.

| verb | meaning |
|---|---|
| `<x>ctl run [<net>]` | start the consumer's daemon service(s) for a network (compose up; clif: `epoch run` per network) |
| `<x>ctl logs [<net>]` | tail the running daemon's logs |
| `<x>ctl status [<net>]` / `<x>ctl doctor [<net>]` | the §3 seams, wrapper-fronted |
| `<x>ctl import-credentials <bundle>` | the §4 handoff |
| `<x>ctl restart [<net>]` | restart after an env change (env is read at daemon startup) |

A conformant wrapper MUST NOT contain any code path that mutates custody (wallet
create/import, policy writes, caller-token minting, `setClaimExecutors`). Custody
mutations happen only through human-gated `fwdctl` / `sudo fwd …`.

---

## 6. The compat tuple (ADR-0001 §7)

Every consumer pins compatibility **per consumer** as a tuple. The keys are a
**pattern**; exact values live in the consumer (and, for the provider side, in the
manifest §7), never frozen here — they drift weekly.

```json
{ "fwd_contract_expected": "<fwd HTTP/ABI contract version the consumer is built against>",
  "fwd_client": "<shared fwd-client library version>",
  "<consumer>": "<consumer version>" }
```

- **`fwd_contract_expected`** — the fwd HTTP + ABI contract version the consumer
  targets (clif: `clif.config.FWD_CONTRACT_EXPECTED`).
- **`fwd_client`** — the shared keyless transport library version
  (`fwd_client.__version__`).
- **`<consumer>`** — the consumer's own version (clif: `clif.__version__`).

The tuple appears verbatim in `<x> spec --json` (`compat`) and `<x> doctor --json`
(`compat`). `provider doctor` (§7) compares it against the per-consumer compat pin
in the manifest. (ADR-0001 §7 names a fourth `membrane_protocol` slot as part of the
pattern; clif's live tuple is the three keys above — a consumer MAY carry additional
compat keys, but MUST carry at least these three.)

---

## 6b. Adding a consumer — the minimal normative path

A new consumer (`<x>`) is added via the **consumer-generic path**, never by forking
clif's `fwd onboard` script (that is the reference consumer's turnkey deployment, not
the abstraction). The split:

**The consumer MUST implement** (clif is the reference for each — copy the *contract*,
not the code; fwd never imports a consumer):

1. **`<x> spec --json`** (§2) — self-describe its `capability_id`s
   (`<x>/<net>/<role>`), each capability's `caller_token_env`, `wallet_name`, and the
   compat tuple (§6). The consumer owns its shape; fwd holds no consumer-roles table.
2. **`<x>ctl import-credentials <net> <bundle>`** (§4) — validate the v2 bundle
   (version/consumer/network/expiry/governed-ids), allowlist the `config` keys against
   **its own** settings fields, apply the env-injection + `*PRIVATE_KEY*` guards, write
   its own `.env.<net>` idempotently (the same path is the rotation channel), force-pin
   its network selector from the bundle's validated `network`, one-shot-consume on
   success. Token VALUES never printed.
3. **Keyless transport via `fwd-client`** (the shared library — Python or Go) for ALL
   fwd HTTP: sign requests, broadcast-result + receipt report-back. The consumer
   broadcasts; fwd never does.
4. **Effect verification** — a mined tx is not success; verify the intended on-chain
   effect of that exact tx (clif D16).

**The custody side (operator-gated, per consumer):**

5. Wallets via `fwdctl wallets create|import`; policy via the template path
   (`fwdctl policy init … --merge` keeps existing networks/consumers intact).
6. Grant + handoff: paste `<x> spec --json` into
   **`fwdctl capability grant --approve --emit-bundle <path> --config NETWORK=<net>
   [--config K=V …]`** — renders the custody diff for operator judgment, mints by
   `capability_id`, emits the complete v2 bundle (pre-mint conformance gate: refuses a
   null `wallet_name`, a missing or contradicting `NETWORK`, before any token is minted).
7. **A new ROLE (different contract/method) is a deliberate fwd change** — a
   `_ROLE_CONVENTION` entry + a policy template (`capability_grant.py`,
   `cli/policy.py`), shipped through fwd's gated workflow. This is by design
   (Invariant #6: policy content is template-driven, never consumer-supplied).

Deferred pieces a new consumer does NOT need: the `provider` coordinator, the deploy
manifest, conflict detection (§7) — those activate at N≥2 by recorded decision.

---

## 7. The provider side (DESIGN — owned here, NOT BUILT; deferred until consumer #2)

Everything in §7 is **design owned by this contract**, deferred per ADR-0001 §Scope
("Build the seam; defer the framework"). It becomes real only when fwd grants by
`capability_id` and `provider` reconciles on it. The **bare-verb** coordinator name
is `provider` (no `ctl` — ADR-0001 §1).

### 7.1 Declarative manifest schema

The manifest is the **source of truth** (ADR-0001 §7); host + deployment are
reconciled toward it, gating at custody.

```yaml
# provider-manifest.yaml (deferred schema — illustrative shape)
version: 1
networks: [flare, songbird]
consumers:
  - ref: clif                      # consumer name (joins to <consumer> in capability_id)
    networks: [flare, songbird]    # subset of top-level networks this consumer runs on
    compat:                        # the per-consumer compat pin (§6) — exact values
      fwd_contract_expected: v1.1.0a69
      fwd_client: ">=X.Y"
      clif: ">=A.B"
    # capabilities are NOT re-declared here — they are discovered from `<x> spec --json`
    # (the consumer owns its capability set); the manifest governs WHICH consumers/networks
    # exist and their compat, not the per-capability authorization (fwd policy owns that).
```

### 7.2 `provider doctor` — three-way reconciliation (ADR-0001 §6)

Three independent holders claim "what exists," joined on `capability_id`:
**manifest** (desired) · **fwd** (granted) · **consumer** (imported / in-use, from
`<x> doctor --json` `capabilities[].configured`). `provider doctor` diffs all three
and classifies drift. **It reads and classifies only** — every custody remediation
is human-gated `fwdctl`.

**Drift taxonomy:**

| drift | condition | meaning | remediation owner |
|---|---|---|---|
| **pending-gate** | manifest wants, fwd hasn't granted | pending custody gate | human → `fwdctl` |
| **pending-handoff** | fwd granted, consumer hasn't imported | pending handoff | consumer (`<x>ctl import-credentials`) |
| **orphaned** | consumer using, manifest dropped it | orphaned capability | human → `fwdctl` (revoke) |
| **ungoverned-grant** | fwd granted, manifest never asked | hand-edited policy | surface **loudly** |

### 7.3 Cursor-is-cache

The runbook's progress **cursor is a cache**, re-derivable from ground truth (fwd
health, on-chain authorizations, each `<x>ctl status`) — never authority. The
manifest is truth; the cursor accelerates, it does not decide.

### 7.4 The bare-verb coordinator

`provider` exposes bare verbs (no `ctl`):

| verb | role |
|---|---|
| `provider doctor` | three-way reconciliation + drift taxonomy (§7.2) — read/classify only |
| `provider plan` | the host/deployment actions to converge toward the manifest (gating at custody) |
| `provider next` | the next single runbook step (cursor-advised, ground-truth-checked) |
| `provider review` | render the pending custody diffs awaiting the human gate |
| `provider verify` | run the membrane invariants (ADR-0001 §Invariants) across the deployment |
| `provider verify-consumer <x>` | run the §8 conformance checklist against one consumer |

---

## 8. Conformance checklist — what `provider verify-consumer <x>` checks

`provider verify-consumer <x>` (design, §7) runs these concrete checks against a
consumer. A consumer is **conformant** iff all pass. (The checks are runnable today
by hand against clif.)

| # | check | how |
|---|---|---|
| **C1** | **keyless** | `<x> doctor --json` `.keyless == true`; the consumer holds no signing key and no unseal key (only bearer caller tokens). ADR Invariant #1. |
| **C2** | **spec --json schema** | `<x> spec --json` parses and carries `consumer`, `network`, `compat` (§6 keys), and `capabilities[]` with **all** §2.1 required keys per entry; every `capability_id` matches `^<consumer>/<network>/<role>$`. |
| **C3** | **custody diff renders** | the default (non-`--json`) `<x> spec` renders the §2.2 adjudicable diff for every capability (id, wallet name, caller-token env name, contract+method, pinned value/recipient, approve/reject). If it cannot, **non-conformant**. ADR Invariant #3. |
| **C4** | **doctor exit codes** | `<x> doctor` exits `0` when fwd is reachable + `master==ok` + no failing daemon; `2` when fwd is unreachable/`master!=ok` or a present daemon fails (§3.1). |
| **C5** | **status states + codes** | `<x> status` / `<x> epoch status` JSON carries `ok`/`exit_code`/`summary`/`report`; exits `0` healthy (incl. deliberately-disabled), `2` degraded/stale, `3` no-state (§3.2). The three states are distinct, not collapsed. |
| **C6** | **import idempotent + id-keyed + one-shot** | `<x>ctl import-credentials` is idempotent, keyed by `capability_id`, refuses an expired/non-local/non-0600 bundle, consumes (deletes) the bundle on success, and writes tokens into the consumer's own `.env.<net>`. ADR Invariant #4 + §4.2. |
| **C7** | **no token-value leak** | no `caller_token` **value** appears in any `spec`, `doctor`, `status`, or import log/output — only names (`caller_token_env`) and `capability_id`. §9. |
| **C8** | **compat tuple present** | both `<x> spec --json` and `<x> doctor --json` carry the §6 compat tuple with at least `fwd_contract_expected`, `fwd_client`, `<consumer>`. |
| **C9** | **consumer never authors fwd policy** | the consumer/`ctl`/coordinator contains no code path that writes fwd policy or mints/custodies a credential. ADR Invariant #2 + #6. |

---

## 9. Security invariants (the testable membrane)

These restate ADR-0001 §Invariants in consumer-contract terms; `provider verify` /
`provider verify-consumer` enforce them.

1. **Keyless.** A conformant consumer holds **no signing key and no unseal key** —
   only bearer caller tokens. (ADR #1.)
2. **Names, not token values, in spec/doctor/status.** `spec`, `doctor`, and
   `status` carry env-var **names** (`caller_token_env`), wallet **names**, and
   `capability_id`s — **never** a caller-token value. The token value lives only in
   the consumer's `.env` (placed by import) and in the one-shot bundle.
3. **The bundle carries values one-shot only.** The credential bundle (§4) is the
   sole carrier of token values, protected by one-shot-consume + mode-0600 +
   same-host trust + short TTL, **not** sealed to a consumer key. Consumed on import.
4. **No consumer decryption key.** A keyless consumer holds no key to decrypt
   anything — the bundle's protection is local trust + TTL, not encryption-to-key.
   (ADR #1.)
5. **The coordinator holds no custody credential.** `provider` has no fwd admin
   credential and no code path that mutates custody — enforced structurally by
   capability-absence, not convention. (ADR #2.)
6. **fwd never reads/writes the consumer's env.** The consumer places its own
   tokens (via import); fwd only emits the bundle. (ADR #5.)
7. **The consumer never authors fwd policy.** It **requests** capabilities (`spec`);
   the human-gated fwd side **instantiates** them. (ADR #6.)
8. **Import is idempotent and id-keyed** — the rotation/revocation channel, not a
   one-time bootstrap. (ADR #4.)

---

## 10. Versioning & ownership

- This document is **`consumer-contract-v1`**. A breaking change to any normative
  shape (bundle format, required JSON keys, exit-code semantics, `capability_id`
  grammar) ⇒ a new `consumer-contract-v2`, not an in-place edit.
- **Owner:** the `flaresystems` deploy repo (ADR-0001 §Ownership). clif owns the
  reference implementation; fwd owns custody + grant + mint + bundle emission;
  `provider` (§7, deferred) owns three-way reconciliation + conformance.
- Where this file and the live reference consumer (clif) diverge, **clif is ground
  truth** and this file is the defect to fix.

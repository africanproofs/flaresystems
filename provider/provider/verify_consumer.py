"""
provider.verify_consumer — §8 conformance checklist.

`provider verify-consumer <x>` checks a consumer against the §8 checklist
from consumer-contract-v1. A consumer is conformant iff all checks pass.

Checks are classified as:
  - implemented:       can be run from spec JSON alone (C2, C7, C8)
  - implemented-live:  requires running the consumer CLI (C3)
  - skipped(runtime):  requires a running consumer+fwd stack (C1, C4, C5, C6, C9)

READ + CLASSIFY ONLY. No custody operations.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped(runtime)"


@dataclass
class CheckResult:
    check: str           # C1 … C9
    name: str
    status: CheckStatus
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass
class VerifyResult:
    consumer: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.PASS]

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    @property
    def skipped(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.SKIPPED]

    @property
    def conformant(self) -> bool:
        """True iff no checks failed (skipped checks are not failures)."""
        return len(self.failed) == 0

    def as_dict(self) -> dict:
        return {
            "consumer": self.consumer,
            "conformant": self.conformant,
            "checks": [c.as_dict() for c in self.checks],
        }


# Regex for capability_id grammar: <consumer>/<network>/<role>
_CAPABILITY_ID_RE = re.compile(
    r"^[a-z][a-z0-9_-]*/(?:flare|songbird|coston2)/[a-z][a-z0-9_-]*$"
)

# Required per-capability keys per §2.1
_REQUIRED_CAP_KEYS = {
    "capability_id",
    "role",
    "endpoint",
    "caller_token_env",
    "wallet_env",
    "wallet_name",     # may be null
    "contract",        # may be null
    "contract_name",   # may be null
    "method",          # may be null
    "value_wei",       # may be null
    "recipient_pinned",# may be null
    "suggested_rate",  # may be null
}

_REQUIRED_COMPAT_KEYS = {"fwd_contract_expected"}  # fwd_client optional for fsp


def _check_c2(spec: dict[str, Any], consumer: str) -> CheckResult:
    """C2: spec --json schema — required keys + capability_id grammar."""
    errors: list[str] = []

    # Top-level required
    for key in ("consumer", "network", "compat", "capabilities"):
        if key not in spec:
            errors.append(f"missing top-level key: {key!r}")

    # compat keys
    compat = spec.get("compat", {})
    for key in _REQUIRED_COMPAT_KEYS:
        if key not in compat:
            errors.append(f"missing compat key: {key!r}")

    # capabilities array
    caps = spec.get("capabilities", [])
    if not isinstance(caps, list):
        errors.append("capabilities is not an array")
    else:
        for i, cap in enumerate(caps):
            missing = _REQUIRED_CAP_KEYS - set(cap.keys())
            if missing:
                errors.append(f"capabilities[{i}] missing keys: {sorted(missing)}")
            cid = cap.get("capability_id", "")
            # consumer prefix must match spec.consumer
            spec_consumer = spec.get("consumer", consumer)
            if not _CAPABILITY_ID_RE.match(cid):
                errors.append(
                    f"capabilities[{i}] capability_id {cid!r} does not match "
                    r"^<consumer>/<network>/<role>$"
                )
            elif not cid.startswith(f"{spec_consumer}/"):
                errors.append(
                    f"capabilities[{i}] capability_id {cid!r} prefix does not "
                    f"match consumer {spec_consumer!r}"
                )

    if errors:
        return CheckResult("C2", "spec --json schema", CheckStatus.FAIL, "; ".join(errors))
    return CheckResult("C2", "spec --json schema", CheckStatus.PASS, f"{len(caps)} capabilities validated")


def _check_c3(consumer: str, network: str | None = None) -> CheckResult:
    """C3: custody diff renders — default (non --json) spec produces output."""
    cmd = [consumer, "spec"]
    if network:
        cmd += ["--network", network]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if not output:
            return CheckResult(
                "C3", "custody diff renders", CheckStatus.FAIL,
                "spec (non-json) produced no output"
            )
        # Check for key adjudicable markers: capability_id, wallet, approve/reject
        markers = ["approve", "reject", "endpoint"]
        missing_markers = [m for m in markers if m not in output.lower()]
        if missing_markers:
            return CheckResult(
                "C3", "custody diff renders", CheckStatus.FAIL,
                f"spec output missing adjudicable markers: {missing_markers}"
            )
        return CheckResult(
            "C3", "custody diff renders", CheckStatus.PASS,
            f"spec rendered {len(output.splitlines())} lines with approve/reject markers"
        )
    except FileNotFoundError:
        return CheckResult(
            "C3", "custody diff renders", CheckStatus.FAIL,
            f"consumer CLI {consumer!r} not found in PATH"
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            "C3", "custody diff renders", CheckStatus.FAIL,
            "spec timed out after 30s"
        )


def _check_c7(spec: dict[str, Any]) -> CheckResult:
    """C7: no token value leak — caller_token value must never appear in spec JSON."""
    # Check that no capability has a 'caller_token' key with a non-null value
    # (that key is bundle-only, not spec-side)
    leaks: list[str] = []
    for cap in spec.get("capabilities", []):
        if "caller_token" in cap and cap["caller_token"] is not None:
            leaks.append(cap.get("capability_id", "unknown"))
        # Also check that caller_token_env holds a NAME not a value
        # (a value would typically start with 'fwd_live_' or be a long token string)
        env_val = cap.get("caller_token_env", "")
        if env_val and (env_val.startswith("fwd_live_") or len(env_val) > 80):
            leaks.append(
                f"{cap.get('capability_id', 'unknown')} — "
                f"caller_token_env looks like a value: {env_val[:20]}..."
            )

    if leaks:
        return CheckResult(
            "C7", "no token-value leak", CheckStatus.FAIL,
            f"token values found in spec for: {leaks}"
        )
    return CheckResult(
        "C7", "no token-value leak", CheckStatus.PASS,
        "no caller_token values in spec output"
    )


def _check_c8(spec: dict[str, Any]) -> CheckResult:
    """C8: compat tuple present — fwd_contract_expected + consumer version."""
    compat = spec.get("compat", {})
    consumer = spec.get("consumer", "unknown")
    errors: list[str] = []

    if "fwd_contract_expected" not in compat:
        errors.append("missing fwd_contract_expected")
    # consumer-named key (e.g. 'clif', 'fsp', 'claim') must be present
    consumer_key = consumer  # the consumer's own version key matches its name
    if consumer_key not in compat:
        errors.append(f"missing consumer version key {consumer_key!r} in compat")

    if errors:
        return CheckResult("C8", "compat tuple present", CheckStatus.FAIL, "; ".join(errors))
    return CheckResult(
        "C8", "compat tuple present", CheckStatus.PASS,
        f"compat: {dict(compat)}"
    )


def _skip(check: str, name: str, reason: str = "requires running consumer+fwd stack") -> CheckResult:
    return CheckResult(check, name, CheckStatus.SKIPPED, reason)


def verify(
    consumer: str,
    spec: dict[str, Any],
    network: str | None = None,
) -> VerifyResult:
    """
    Run the §8 conformance checklist against one consumer.

    Args:
        consumer: the consumer name (e.g. 'fsp', 'claim')
        spec:     parsed output of `<x> spec --json`
        network:  if provided, passed to the non-json spec call for C3

    Returns:
        VerifyResult with all check outcomes.
    """
    result = VerifyResult(consumer=consumer)

    # C1: keyless — needs running consumer+fwd
    result.checks.append(
        _skip("C1", "keyless",
              "needs doctor --json from a running consumer; verify .keyless==true manually")
    )

    # C2: spec --json schema (implemented from spec dict)
    result.checks.append(_check_c2(spec, consumer))

    # C3: custody diff renders (calls CLI subprocess)
    result.checks.append(_check_c3(consumer, network))

    # C4: doctor exit codes — needs running consumer+fwd
    result.checks.append(
        _skip("C4", "doctor exit codes",
              "needs a running fwd stack to probe exit 0 vs 2")
    )

    # C5: status states + codes — needs running consumer
    result.checks.append(
        _skip("C5", "status states + codes",
              "needs a running daemon to probe exit 0/2/3 states")
    )

    # C6: import idempotent + id-keyed + one-shot — needs running consumer
    result.checks.append(
        _skip("C6", "import idempotent + id-keyed + one-shot",
              "needs a real bundle from fwd to test import semantics")
    )

    # C7: no token-value leak (implemented from spec dict)
    result.checks.append(_check_c7(spec))

    # C8: compat tuple present (implemented from spec dict)
    result.checks.append(_check_c8(spec))

    # C9: consumer never authors fwd policy — needs source code inspection or runtime
    result.checks.append(
        _skip("C9", "consumer never authors fwd policy",
              "static check deferred; inspect consumer source for fwd policy write paths")
    )

    return result

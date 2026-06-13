"""Tests for provider.conflict — cross-consumer conflict detection."""

import json
from pathlib import Path

import pytest
from provider.conflict import detect


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Injected conflict: shared wallet across consumers
# ---------------------------------------------------------------------------


def test_conflict_detected_shared_wallet():
    """A wallet shared across two consumers is flagged."""
    fsp_spec = {
        "consumer": "fsp",
        "network": "flare",
        "compat": {"fwd_contract_expected": "v1.1.0a69", "fsp": "0.1.0"},
        "capabilities": [
            {
                "capability_id": "fsp/flare/signing-policy-sign",
                "role": "signing-policy-sign",
                "endpoint": "/v1/sign-fsp-message",
                "caller_token_env": "FWD_SIGNING_POLICY_SIGN_TOKEN",
                "wallet_name": "shared-wallet",  # <-- shared
                "wallet_env": "FWD_SIGNING_ADDRESS",
                "contract": None,
                "contract_name": None,
                "method": "SIGNING_POLICY",
                "value_wei": None,
                "recipient_pinned": None,
                "suggested_rate": "per-round",
            }
        ],
    }
    claim_spec = {
        "consumer": "claim",
        "network": "flare",
        "compat": {"fwd_contract_expected": "v1.1.0a69", "fwd_client": "0.1.3", "claim": "0.5.38"},
        "capabilities": [
            {
                "capability_id": "claim/flare/ftso-reward-claim",
                "role": "ftso-reward-claim",
                "endpoint": "/v1/sign-transaction",
                "caller_token_env": "FWD_CALLER_TOKEN",
                "wallet_env": "FWD_WALLET_NAME",
                "wallet_name": "shared-wallet",  # <-- same wallet, different consumer
                "contract": "0xC8f55c5aA2C752eE285Bd872855C749f4ee6239B",
                "contract_name": "RewardManager",
                "method": "claim(...)",
                "value_wei": "0",
                "recipient_pinned": None,
                "suggested_rate": "8/day",
            }
        ],
    }

    result = detect([fsp_spec, claim_spec])

    assert not result.ok
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.wallet_name == "shared-wallet"
    assert "claim" in conflict.consumers
    assert "fsp" in conflict.consumers


# ---------------------------------------------------------------------------
# Real specs: fsp + claim should NOT conflict (claim has null wallet_names)
# ---------------------------------------------------------------------------


def test_real_specs_no_conflict():
    """
    Real fsp (flare) + claim (flare) specs from fixtures.

    fsp has named wallet_names; claim has wallet_name=null for all capabilities.
    Null wallet_names are ignored (unconfigured, not a custody identity yet).
    Therefore there must be NO conflict between fsp and claim.
    """
    fsp_spec = load_fixture("fsp_flare_spec.json")
    claim_spec = load_fixture("claim_flare_spec.json")

    result = detect([fsp_spec, claim_spec])

    assert result.ok, (
        f"Unexpected wallet conflicts between fsp and claim: "
        f"{[c.as_dict() for c in result.conflicts]}"
    )
    assert len(result.conflicts) == 0


def test_null_wallet_names_ignored():
    """Capabilities with wallet_name=null do not trigger conflict detection."""
    spec_a = {
        "consumer": "claim",
        "network": "flare",
        "compat": {},
        "capabilities": [
            {
                "capability_id": "claim/flare/ftso-reward-claim",
                "wallet_name": None,  # null — unconfigured
                "role": "ftso-reward-claim",
                "endpoint": "/v1/sign-transaction",
                "caller_token_env": "FWD_CALLER_TOKEN",
                "wallet_env": "FWD_WALLET_NAME",
                "contract": None,
                "contract_name": None,
                "method": None,
                "value_wei": None,
                "recipient_pinned": None,
                "suggested_rate": None,
            }
        ],
    }
    spec_b = {
        "consumer": "other",
        "network": "flare",
        "compat": {},
        "capabilities": [
            {
                "capability_id": "other/flare/some-role",
                "wallet_name": None,  # null — same null, should not conflict
                "role": "some-role",
                "endpoint": "/v1/sign-transaction",
                "caller_token_env": "OTHER_TOKEN",
                "wallet_env": "OTHER_WALLET",
                "contract": None,
                "contract_name": None,
                "method": None,
                "value_wei": None,
                "recipient_pinned": None,
                "suggested_rate": None,
            }
        ],
    }

    result = detect([spec_a, spec_b])
    assert result.ok


def test_same_wallet_same_consumer_no_conflict():
    """Multiple capabilities of the same consumer sharing a wallet is fine."""
    fsp_spec = load_fixture("fsp_flare_spec.json")

    # fsp has multiple capabilities sharing fsp-signing-flare — that's correct
    result = detect([fsp_spec])
    assert result.ok


def test_empty_specs():
    result = detect([])
    assert result.ok


def test_as_dict():
    """ConflictResult.as_dict() round-trips."""
    fsp_spec = load_fixture("fsp_flare_spec.json")
    claim_spec = load_fixture("claim_flare_spec.json")
    result = detect([fsp_spec, claim_spec])
    d = result.as_dict()
    assert isinstance(d, dict)
    assert "ok" in d
    assert "conflicts" in d

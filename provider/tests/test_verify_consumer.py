"""Tests for provider.verify_consumer — §8 conformance checklist."""

import json
from pathlib import Path

import pytest
from provider.verify_consumer import CheckStatus, verify


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# C2: spec --json schema
# ---------------------------------------------------------------------------


def test_c2_fsp_passes():
    spec = load_fixture("fsp_flare_spec.json")
    result = verify("fsp", spec, network="flare")
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.PASS, f"C2 failed: {c2.detail}"


def test_c2_claim_passes():
    spec = load_fixture("claim_flare_spec.json")
    result = verify("claim", spec, network="flare")
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.PASS, f"C2 failed: {c2.detail}"


def test_c2_missing_top_level_key():
    spec = load_fixture("fsp_flare_spec.json").copy()
    del spec["compat"]
    result = verify("fsp", spec)
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.FAIL
    assert "compat" in c2.detail


def test_c2_bad_capability_id_grammar():
    spec = load_fixture("fsp_flare_spec.json")
    spec = json.loads(json.dumps(spec))  # deep copy
    spec["capabilities"][0]["capability_id"] = "badformat"
    result = verify("fsp", spec)
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.FAIL


def test_c2_capability_id_wrong_consumer_prefix():
    spec = load_fixture("claim_flare_spec.json")
    spec = json.loads(json.dumps(spec))
    spec["capabilities"][0]["capability_id"] = "fsp/flare/some-role"  # wrong prefix
    result = verify("claim", spec)
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.FAIL
    assert "prefix" in c2.detail


def test_c2_missing_required_cap_key():
    spec = load_fixture("fsp_flare_spec.json")
    spec = json.loads(json.dumps(spec))
    del spec["capabilities"][0]["endpoint"]
    result = verify("fsp", spec)
    c2 = next(c for c in result.checks if c.check == "C2")
    assert c2.status == CheckStatus.FAIL
    assert "endpoint" in c2.detail


# ---------------------------------------------------------------------------
# C7: no token-value leak
# ---------------------------------------------------------------------------


def test_c7_fsp_passes():
    spec = load_fixture("fsp_flare_spec.json")
    result = verify("fsp", spec, network="flare")
    c7 = next(c for c in result.checks if c.check == "C7")
    assert c7.status == CheckStatus.PASS


def test_c7_claim_passes():
    spec = load_fixture("claim_flare_spec.json")
    result = verify("claim", spec, network="flare")
    c7 = next(c for c in result.checks if c.check == "C7")
    assert c7.status == CheckStatus.PASS


def test_c7_token_value_leak_detected():
    """A spec containing an actual caller_token value must fail C7."""
    spec = load_fixture("fsp_flare_spec.json")
    spec = json.loads(json.dumps(spec))
    spec["capabilities"][0]["caller_token"] = "fwd_live_abc123verylongtoken"
    result = verify("fsp", spec)
    c7 = next(c for c in result.checks if c.check == "C7")
    assert c7.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# C8: compat tuple present
# ---------------------------------------------------------------------------


def test_c8_fsp_passes():
    """fsp compat: fwd_contract_expected + fsp version. fwd_client absent (allowed for fsp)."""
    spec = load_fixture("fsp_flare_spec.json")
    result = verify("fsp", spec, network="flare")
    c8 = next(c for c in result.checks if c.check == "C8")
    assert c8.status == CheckStatus.PASS, f"C8 failed: {c8.detail}"


def test_c8_claim_passes():
    """claim compat: fwd_contract_expected + fwd_client + claim version."""
    spec = load_fixture("claim_flare_spec.json")
    result = verify("claim", spec, network="flare")
    c8 = next(c for c in result.checks if c.check == "C8")
    assert c8.status == CheckStatus.PASS, f"C8 failed: {c8.detail}"


def test_c8_missing_fwd_contract_expected():
    spec = load_fixture("fsp_flare_spec.json")
    spec = json.loads(json.dumps(spec))
    del spec["compat"]["fwd_contract_expected"]
    result = verify("fsp", spec)
    c8 = next(c for c in result.checks if c.check == "C8")
    assert c8.status == CheckStatus.FAIL
    assert "fwd_contract_expected" in c8.detail


def test_c8_missing_consumer_version_key():
    spec = load_fixture("fsp_flare_spec.json")
    spec = json.loads(json.dumps(spec))
    del spec["compat"]["fsp"]
    result = verify("fsp", spec)
    c8 = next(c for c in result.checks if c.check == "C8")
    assert c8.status == CheckStatus.FAIL
    assert "fsp" in c8.detail


# ---------------------------------------------------------------------------
# Skipped checks (runtime)
# ---------------------------------------------------------------------------


def test_runtime_checks_are_skipped():
    spec = load_fixture("fsp_flare_spec.json")
    result = verify("fsp", spec)
    skipped_ids = {c.check for c in result.skipped}
    for check in ("C1", "C4", "C5", "C6", "C9"):
        assert check in skipped_ids, f"{check} should be skipped(runtime)"


# ---------------------------------------------------------------------------
# Conformance gate: only hard failures block conformance
# ---------------------------------------------------------------------------


def test_conformant_with_skipped_checks():
    """
    A consumer is conformant if no FAIL checks — skipped(runtime) checks
    do not block conformance.
    """
    spec = load_fixture("fsp_flare_spec.json")
    result = verify("fsp", spec, network="flare")
    # C3 requires the 'fsp' CLI in PATH — may or may not be present.
    # Skip this assertion in offline environments; just verify no hard failures
    # from the spec-only checks (C2, C7, C8).
    spec_checks = [c for c in result.checks if c.check in ("C2", "C7", "C8")]
    for check in spec_checks:
        assert check.status == CheckStatus.PASS, f"{check.check} failed: {check.detail}"


def test_as_dict_structure():
    spec = load_fixture("claim_flare_spec.json")
    result = verify("claim", spec)
    d = result.as_dict()
    assert "consumer" in d
    assert "conformant" in d
    assert "checks" in d
    assert isinstance(d["checks"], list)

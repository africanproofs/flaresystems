"""Tests for provider.doctor — three-way reconciliation."""

import pytest
from provider.doctor import DriftType, reconcile


# ---------------------------------------------------------------------------
# All four drift types
# ---------------------------------------------------------------------------


def test_pending_gate():
    """desired but not granted → pending-gate."""
    desired = {"fsp/flare/protocol-message-sign"}
    granted: set[str] = set()
    configured: set[str] = set()

    result = reconcile(desired, granted, configured)

    assert not result.ok
    items = result.by_type(DriftType.PENDING_GATE)
    assert len(items) == 1
    assert items[0].capability_id == "fsp/flare/protocol-message-sign"


def test_pending_handoff():
    """desired + granted but consumer hasn't imported → pending-handoff."""
    desired = {"fsp/flare/signing-policy-sign"}
    granted = {"fsp/flare/signing-policy-sign"}
    configured: set[str] = set()

    result = reconcile(desired, granted, configured)

    assert not result.ok
    items = result.by_type(DriftType.PENDING_HANDOFF)
    assert len(items) == 1
    assert items[0].capability_id == "fsp/flare/signing-policy-sign"
    # Should NOT appear as pending-gate (it IS granted)
    assert len(result.by_type(DriftType.PENDING_GATE)) == 0


def test_orphaned():
    """consumer using it but manifest dropped it → orphaned."""
    desired: set[str] = set()
    granted: set[str] = set()
    configured = {"claim/flare/ftso-reward-claim"}

    result = reconcile(desired, granted, configured)

    assert not result.ok
    items = result.by_type(DriftType.ORPHANED)
    assert len(items) == 1
    assert items[0].capability_id == "claim/flare/ftso-reward-claim"


def test_ungoverned_grant():
    """fwd granted but manifest never asked and consumer didn't import → ungoverned-grant."""
    desired: set[str] = set()
    granted = {"fsp/flare/mystery-capability"}
    configured: set[str] = set()

    result = reconcile(desired, granted, configured)

    assert not result.ok
    items = result.by_type(DriftType.UNGOVERNED_GRANT)
    assert len(items) == 1
    assert items[0].capability_id == "fsp/flare/mystery-capability"
    assert "HAND-EDITED" in items[0].detail


def test_all_four_drift_types_together():
    """Construct a scenario that triggers all four drift types simultaneously."""
    desired = {
        "fsp/flare/protocol-message-sign",  # pending-gate: desired, not granted
        "fsp/flare/signing-policy-sign",    # pending-handoff: desired+granted, not configured
    }
    granted = {
        "fsp/flare/signing-policy-sign",    # pending-handoff
        "fsp/flare/mystery-capability",     # ungoverned-grant
    }
    configured = {
        "claim/flare/ftso-reward-claim",    # orphaned: configured, not desired
    }

    result = reconcile(desired, granted, configured)

    assert not result.ok
    assert len(result.by_type(DriftType.PENDING_GATE)) == 1
    assert len(result.by_type(DriftType.PENDING_HANDOFF)) == 1
    assert len(result.by_type(DriftType.ORPHANED)) == 1
    assert len(result.by_type(DriftType.UNGOVERNED_GRANT)) == 1


def test_aligned_no_drift():
    """All three agree → aligned, no drift."""
    cap = "fsp/flare/uptime-vote-sign"
    result = reconcile({cap}, {cap}, {cap})

    assert result.ok
    assert cap in result.aligned
    assert len(result.drift) == 0


def test_aligned_partial():
    """Some aligned, some drifted."""
    aligned = "fsp/flare/relay-submit"
    pending = "fsp/flare/ftso-price-submit"

    result = reconcile(
        desired={aligned, pending},
        granted={aligned},       # pending not granted
        configured={aligned},
    )

    assert aligned in result.aligned
    assert not result.ok
    assert len(result.by_type(DriftType.PENDING_GATE)) == 1


def test_empty_all_three():
    """Empty on all sides — trivially ok."""
    result = reconcile(set(), set(), set())
    assert result.ok
    assert result.aligned == []
    assert result.drift == []

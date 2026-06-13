"""
provider.doctor — three-way reconciliation (§7.2 of consumer-contract-v1).

Three independent holders claim "what exists," joined on capability_id:
  manifest (desired) · fwd (granted) · consumer (imported / in-use)

provider doctor diffs all three and classifies drift per §7.2.

READ AND CLASSIFY ONLY. This module never writes, never calls fwdctl,
never mutates any state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class DriftType(str, Enum):
    """§7.2 drift taxonomy — four canonical classes."""

    PENDING_GATE = "pending-gate"
    """In manifest (desired), NOT granted in fwd. Needs human → fwdctl."""

    PENDING_HANDOFF = "pending-handoff"
    """Granted in fwd, NOT imported in consumer. Needs <x>ctl import-credentials."""

    ORPHANED = "orphaned"
    """Consumer is using it, manifest no longer wants it. Needs human → fwdctl revoke."""

    UNGOVERNED_GRANT = "ungoverned-grant"
    """fwd has granted it, manifest never asked. Hand-edited policy — surface loudly."""


@dataclass(frozen=True)
class DriftItem:
    """A single capability_id classified into a drift type."""

    capability_id: str
    drift: DriftType
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "capability_id": self.capability_id,
            "drift": self.drift.value,
            "detail": self.detail,
        }


@dataclass
class DoctorResult:
    """The full three-way reconciliation result."""

    aligned: list[str] = field(default_factory=list)
    """capability_ids present in all three sources (manifest ∩ fwd ∩ consumer)."""

    drift: list[DriftItem] = field(default_factory=list)
    """Classified drift items."""

    @property
    def ok(self) -> bool:
        """True iff no drift detected (aligned only, or all three empty)."""
        return len(self.drift) == 0

    def by_type(self, dtype: DriftType) -> list[DriftItem]:
        return [d for d in self.drift if d.drift == dtype]

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "aligned": sorted(self.aligned),
            "drift": [d.as_dict() for d in self.drift],
        }


def reconcile(
    desired: set[str],
    granted: set[str],
    configured: set[str],
) -> DoctorResult:
    """
    Three-way reconciliation per §7.2.

    Args:
        desired:    capability_ids the manifest wants (from ManifestSource.desired())
        granted:    capability_ids fwd has granted (from FwdGrantSource.granted())
        configured: capability_ids the consumer has imported (from ConsumerSource.configured())

    Returns:
        DoctorResult with aligned ids and classified drift items.

    Classification rules (disjoint, evaluated in priority order):
      1. pending-gate:     in desired, NOT in granted
         (regardless of consumer — fwd hasn't granted it yet)
      2. pending-handoff:  in desired AND granted, NOT in configured
         (fwd granted it but consumer hasn't imported it)
      3. orphaned:         in configured, NOT in desired
         (consumer using it but manifest dropped it)
      4. ungoverned-grant: in granted, NOT in desired AND NOT in configured
         (fwd has it but nobody asked for it — surface loudly)

    Aligned: in desired AND granted AND configured.
    """
    result = DoctorResult()

    # Aligned: all three agree
    aligned = desired & granted & configured
    result.aligned = sorted(aligned)

    # 1. pending-gate: manifest wants, fwd hasn't granted
    #    (covers both configured and not — if fwd hasn't granted, it's gated)
    for cid in sorted(desired - granted):
        result.drift.append(
            DriftItem(
                capability_id=cid,
                drift=DriftType.PENDING_GATE,
                detail="manifest desires but fwd has not granted — needs human → fwdctl",
            )
        )

    # 2. pending-handoff: desired AND granted, but consumer hasn't imported
    for cid in sorted((desired & granted) - configured):
        result.drift.append(
            DriftItem(
                capability_id=cid,
                drift=DriftType.PENDING_HANDOFF,
                detail="fwd has granted but consumer has not imported — needs <x>ctl import-credentials",
            )
        )

    # 3. orphaned: consumer using it, manifest dropped it
    for cid in sorted(configured - desired):
        result.drift.append(
            DriftItem(
                capability_id=cid,
                drift=DriftType.ORPHANED,
                detail="consumer has imported but manifest no longer desires — needs human → fwdctl revoke",
            )
        )

    # 4. ungoverned-grant: fwd has it, manifest never asked, consumer didn't import
    #    (granted but neither desired nor configured)
    for cid in sorted(granted - desired - configured):
        result.drift.append(
            DriftItem(
                capability_id=cid,
                drift=DriftType.UNGOVERNED_GRANT,
                detail="fwd has granted but manifest never asked — HAND-EDITED POLICY; surface loudly",
            )
        )

    return result

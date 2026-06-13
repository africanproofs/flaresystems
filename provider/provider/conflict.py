"""
provider.conflict — cross-consumer conflict detection (ADR-0004).

Tree invariant: no wallet_name appears in two consumers' capabilities.

A wallet_name is a custody identity in fwd. Sharing one across consumers
would mean two consumers hold tokens for the same fwd wallet — a custody
boundary violation (ADR-0004: "shared signing key ⟹ same consumer").

This module ingests N consumer specs (from `<x> spec --json`) and flags
any wallet_name shared across consumers.

READ + CLASSIFY ONLY. Never writes, never mutates anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WalletConflict:
    """A wallet_name shared by two or more consumers."""

    wallet_name: str
    consumers: tuple[str, ...]  # sorted consumer names sharing this wallet

    def as_dict(self) -> dict:
        return {
            "wallet_name": self.wallet_name,
            "consumers": list(self.consumers),
        }


@dataclass
class ConflictResult:
    """Result of cross-consumer conflict detection."""

    conflicts: list[WalletConflict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.conflicts) == 0

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "conflicts": [c.as_dict() for c in self.conflicts],
        }


def detect(specs: list[dict[str, Any]]) -> ConflictResult:
    """
    Detect wallet_name conflicts across consumer specs.

    Args:
        specs: list of parsed `<x> spec --json` dicts (one per consumer×network).
               Multiple specs for the same consumer (different networks) are merged
               under the same consumer name.

    Returns:
        ConflictResult listing any wallet_name shared across consumers.

    A `wallet_name` of None is ignored — null means unconfigured/not-yet-set,
    not a shared identity.
    """
    # wallet_name -> set of consumer names using it
    wallet_to_consumers: dict[str, set[str]] = {}

    for spec in specs:
        consumer = spec.get("consumer", "unknown")
        for cap in spec.get("capabilities", []):
            wallet = cap.get("wallet_name")
            if wallet is None:
                continue  # null = unconfigured, not a custody identity yet
            wallet_to_consumers.setdefault(wallet, set()).add(consumer)

    result = ConflictResult()
    for wallet, consumers in sorted(wallet_to_consumers.items()):
        if len(consumers) > 1:
            result.conflicts.append(
                WalletConflict(
                    wallet_name=wallet,
                    consumers=tuple(sorted(consumers)),
                )
            )

    return result

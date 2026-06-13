"""
provider.manifest — parse provider-manifest.yaml (§7.1 schema).

The manifest is the source of truth for which consumers and networks exist
and their compat pins. Capabilities are NOT declared here — they are
discovered from each consumer's `spec --json`.

This module is READ ONLY. It never writes the manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class ConsumerCompat(BaseModel):
    """Per-consumer compat pin (§6 of consumer-contract-v1)."""

    fwd_contract_expected: str
    fwd_client: str | None = None  # fsp does not carry fwd_client; allowed
    extra: dict[str, str] = {}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConsumerCompat":
        known = {"fwd_contract_expected", "fwd_client"}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            fwd_contract_expected=d["fwd_contract_expected"],
            fwd_client=d.get("fwd_client"),
            extra=extra,
        )


class ConsumerEntry(BaseModel):
    """One consumer row in the manifest."""

    ref: str  # consumer name — joins to <consumer> in capability_id
    networks: list[str]
    compat: ConsumerCompat

    @field_validator("networks")
    @classmethod
    def nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("consumer.networks must be non-empty")
        return v


class Manifest(BaseModel):
    """Parsed provider-manifest.yaml."""

    version: int
    networks: list[str]
    consumers: list[ConsumerEntry]

    def consumer(self, ref: str) -> ConsumerEntry | None:
        for c in self.consumers:
            if c.ref == ref:
                return c
        return None

    def capability_ids(self) -> set[str]:
        """
        The set of capability_ids the manifest *desires* — one per
        (consumer, network, role) triple declared.

        NOTE: the manifest does NOT list roles explicitly (§7.1). This method
        returns an empty set; the desired set is populated by intersecting with
        the live consumer spec (roles come from `<x> spec --json`).

        The manifest governs WHICH consumers/networks exist; the consumer owns
        its role set. provider doctor discovers the desired capability_ids by
        calling `<x> spec --json` for each declared consumer+network.
        """
        return set()


def load(path: Path | str) -> Manifest:
    """Load and validate provider-manifest.yaml from *path*."""
    path = Path(path)
    with path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    consumers = []
    for c in raw.get("consumers", []):
        compat_raw = c.get("compat", {})
        consumers.append(
            ConsumerEntry(
                ref=c["ref"],
                networks=c["networks"],
                compat=ConsumerCompat.from_dict(compat_raw),
            )
        )

    return Manifest(
        version=raw["version"],
        networks=raw["networks"],
        consumers=consumers,
    )

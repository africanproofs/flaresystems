"""
provider.sources — the three independent sources joined on capability_id.

Sources (§7.2 of consumer-contract-v1):
  - manifest (desired)  — parsed from YAML by manifest.py
  - fwd     (granted)   — callers granted in fwd policy
  - consumer (imported) — from `<x> doctor --json` capabilities[].configured

This module is READ ONLY. No source writes anything.

The real fwd-admin adapter is deferred (fwd does not yet expose a
`capability_id`-keyed grant list). A file-backed stub is provided for testing
and runbook simulation; the interface is stable so the real adapter can be
dropped in later without changing doctor.py.
"""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Abstract interfaces
# ---------------------------------------------------------------------------


class FwdGrantSource(ABC):
    """Returns the set of capability_ids fwd has granted (custody side)."""

    @abstractmethod
    def granted(self) -> set[str]:
        """Return capability_ids currently granted in fwd policy."""
        ...


class ConsumerSource(ABC):
    """Returns a consumer's imported/in-use capability_ids from doctor --json."""

    @abstractmethod
    def configured(self) -> set[str]:
        """Return capability_ids the consumer has imported (configured==true)."""
        ...


# ---------------------------------------------------------------------------
# Manifest source (desired)
# ---------------------------------------------------------------------------


class ManifestSource:
    """
    Derives the desired capability_id set from the manifest + live consumer specs.

    The manifest (§7.1) lists which consumers/networks are desired but NOT which
    roles — roles are owned by the consumer's spec. This source calls
    `<x> spec --json` for each consumer×network declared in the manifest and
    collects the capability_ids from those specs.

    If spec cannot be called (consumer not installed), the set for that
    consumer/network is empty (logged as a warning).
    """

    def __init__(
        self,
        consumers: list[tuple[str, list[str]]],
        spec_runner: "SpecRunner | None" = None,
    ) -> None:
        """
        consumers: list of (consumer_ref, [network, ...]) from manifest.
        spec_runner: callable(consumer, network) -> dict | None. Defaults to
                     LiveSpecRunner.
        """
        self._consumers = consumers
        self._runner = spec_runner or LiveSpecRunner()

    def desired(self) -> set[str]:
        ids: set[str] = set()
        for ref, networks in self._consumers:
            for net in networks:
                spec = self._runner.run(ref, net)
                if spec:
                    for cap in spec.get("capabilities", []):
                        cid = cap.get("capability_id")
                        if cid:
                            ids.add(cid)
        return ids


# ---------------------------------------------------------------------------
# Spec runner
# ---------------------------------------------------------------------------


class SpecRunner(ABC):
    @abstractmethod
    def run(self, consumer: str, network: str) -> dict[str, Any] | None:
        ...


class LiveSpecRunner(SpecRunner):
    """Calls `<consumer> spec --json --network <network>` as a subprocess."""

    def run(self, consumer: str, network: str) -> dict[str, Any] | None:
        try:
            result = subprocess.run(
                [consumer, "spec", "--json", "--network", network],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return None
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            return None


class DictSpecRunner(SpecRunner):
    """Fixture-backed spec runner for tests and offline use."""

    def __init__(self, specs: dict[tuple[str, str], dict[str, Any]]) -> None:
        # key: (consumer, network)
        self._specs = specs

    def run(self, consumer: str, network: str) -> dict[str, Any] | None:
        return self._specs.get((consumer, network))


# ---------------------------------------------------------------------------
# fwd grant source implementations
# ---------------------------------------------------------------------------


class StubFwdGrantSource(FwdGrantSource):
    """
    Stub fwd grant source backed by an explicit set.

    Used for tests and offline simulation. The real fwd-admin adapter
    is deferred pending fwd exposing a capability_id-keyed grant list.
    """

    def __init__(self, granted_ids: set[str]) -> None:
        self._granted = granted_ids

    def granted(self) -> set[str]:
        return set(self._granted)


class FileFwdGrantSource(FwdGrantSource):
    """
    File-backed fwd grant source.

    Reads a JSON file containing {"granted": ["cap/net/role", ...]}.
    Suitable for operator-maintained runbook snapshots.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def granted(self) -> set[str]:
        with self._path.open() as f:
            data = json.load(f)
        return set(data.get("granted", []))


# ---------------------------------------------------------------------------
# Consumer source implementations
# ---------------------------------------------------------------------------


class StubConsumerSource(ConsumerSource):
    """Stub consumer source backed by an explicit set. For tests."""

    def __init__(self, configured_ids: set[str]) -> None:
        self._configured = configured_ids

    def configured(self) -> set[str]:
        return set(self._configured)


class DoctorConsumerSource(ConsumerSource):
    """
    Live consumer source: calls `<x> doctor --json [--network <net>]`.

    Collects capability_ids where configured==true from the doctor output.
    """

    def __init__(self, consumer: str, network: str | None = None) -> None:
        self._consumer = consumer
        self._network = network

    def configured(self) -> set[str]:
        cmd = [self._consumer, "doctor", "--json"]
        if self._network:
            cmd += ["--network", self._network]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode not in (0, 2):  # 0=ok, 2=degraded but still parseable
                return set()
            data = json.loads(result.stdout)
            return {
                c["capability_id"]
                for c in data.get("capabilities", [])
                if c.get("configured")
            }
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            return set()


class FileDoctorConsumerSource(ConsumerSource):
    """
    File-backed consumer source.

    Reads a saved `<x> doctor --json` output from a file. Suitable for
    offline reconciliation against a saved snapshot.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def configured(self) -> set[str]:
        with self._path.open() as f:
            data = json.load(f)
        return {
            c["capability_id"]
            for c in data.get("capabilities", [])
            if c.get("configured")
        }

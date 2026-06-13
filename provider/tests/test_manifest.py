"""Tests for provider.manifest — parse provider-manifest.yaml."""

import textwrap
from pathlib import Path

import pytest
import yaml

from provider.manifest import Manifest, load


@pytest.fixture
def manifest_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        version: 1
        networks: [flare, songbird]
        consumers:
          - ref: fsp
            networks: [flare, songbird]
            compat:
              fwd_contract_expected: v1.1.0a69
              fsp: ">=0.1.0"
          - ref: claim
            networks: [flare, songbird]
            compat:
              fwd_contract_expected: v1.1.0a69
              fwd_client: ">=0.1.3"
              claim: ">=0.5.38"
    """)
    p = tmp_path / "provider-manifest.yaml"
    p.write_text(content)
    return p


def test_load_parses_consumers(manifest_yaml):
    mf = load(manifest_yaml)
    assert mf.version == 1
    assert set(mf.networks) == {"flare", "songbird"}
    assert len(mf.consumers) == 2


def test_load_consumer_refs(manifest_yaml):
    mf = load(manifest_yaml)
    refs = {c.ref for c in mf.consumers}
    assert refs == {"fsp", "claim"}


def test_load_fsp_compat(manifest_yaml):
    mf = load(manifest_yaml)
    fsp = mf.consumer("fsp")
    assert fsp is not None
    assert fsp.compat.fwd_contract_expected == "v1.1.0a69"
    assert fsp.compat.fwd_client is None  # fsp doesn't carry fwd_client


def test_load_claim_compat(manifest_yaml):
    mf = load(manifest_yaml)
    claim = mf.consumer("claim")
    assert claim is not None
    assert claim.compat.fwd_contract_expected == "v1.1.0a69"
    assert claim.compat.fwd_client == ">=0.1.3"
    assert claim.compat.extra.get("claim") == ">=0.5.38"


def test_consumer_lookup_missing(manifest_yaml):
    mf = load(manifest_yaml)
    assert mf.consumer("nonexistent") is None


def test_networks_per_consumer(manifest_yaml):
    mf = load(manifest_yaml)
    fsp = mf.consumer("fsp")
    assert set(fsp.networks) == {"flare", "songbird"}

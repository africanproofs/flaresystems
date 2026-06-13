"""
provider CLI — bare-verb coordinator (§7.4 of consumer-contract-v1).

Verbs:
  provider doctor             — three-way reconciliation
  provider conflict           — cross-consumer conflict detection
  provider verify-consumer    — §8 conformance checklist
  provider review             — render pending custody diffs
  provider plan               — stub (deferred)
  provider next               — stub (deferred)
  provider verify             — stub (deferred)

AUTHORITY: NONE. This CLI reads, classifies, and presents only.
It holds no fwd admin credential and has no code path that mutates custody.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml

from provider.conflict import detect as conflict_detect
from provider.doctor import DriftType, reconcile
from provider.manifest import load as load_manifest
from provider.sources import (
    DictSpecRunner,
    FileDoctorConsumerSource,
    FileFwdGrantSource,
    LiveSpecRunner,
    ManifestSource,
    StubConsumerSource,
    StubFwdGrantSource,
)
from provider.verify_consumer import verify

app = typer.Typer(
    name="provider",
    help=(
        "Neutral runbook coordinator for the fwd ecosystem. "
        "Reads, classifies, and plans only — no custody authority."
    ),
    no_args_is_help=True,
)


def _find_manifest(manifest_path: Optional[Path]) -> Path:
    """Resolve manifest path: arg > ./provider-manifest.yaml > ../provider-manifest.yaml."""
    if manifest_path and manifest_path.exists():
        return manifest_path
    candidates = [
        Path("provider-manifest.yaml"),
        Path("../provider-manifest.yaml"),
        Path(__file__).parent.parent.parent / "provider-manifest.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    raise typer.BadParameter(
        "provider-manifest.yaml not found. Pass --manifest or place it in the current directory."
    )


@app.command("doctor")
def cmd_doctor(
    manifest: Optional[Path] = typer.Option(None, "--manifest", "-m", help="Path to provider-manifest.yaml"),
    fwd_grants: Optional[Path] = typer.Option(None, "--fwd-grants", help="Path to JSON file of fwd granted capability_ids"),
    doctor_json: Optional[list[Path]] = typer.Option(None, "--consumer-doctor", help="Path to saved <x> doctor --json output(s)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Three-way reconciliation: manifest vs fwd vs consumer (§7.2)."""
    mpath = _find_manifest(manifest)
    mf = load_manifest(mpath)

    # Desired: from manifest + live consumer specs
    consumer_pairs = [(c.ref, c.networks) for c in mf.consumers]
    desired_source = ManifestSource(consumer_pairs, LiveSpecRunner())
    desired = desired_source.desired()

    # Granted: from file if provided, else stub empty (fwd adapter deferred)
    if fwd_grants:
        granted = FileFwdGrantSource(fwd_grants).granted()
    else:
        typer.echo(
            "NOTE: --fwd-grants not provided; fwd grant source is empty (adapter deferred). "
            "All desired ids will appear as pending-gate.",
            err=True,
        )
        granted: set[str] = set()

    # Configured: from saved doctor --json files if provided
    configured: set[str] = set()
    if doctor_json:
        for p in doctor_json:
            configured |= FileDoctorConsumerSource(p).configured()

    result = reconcile(desired, granted, configured)

    if json_output:
        typer.echo(json.dumps(result.as_dict(), indent=2))
    else:
        if result.ok:
            typer.echo("OK — no drift detected.")
        else:
            typer.echo(f"DRIFT DETECTED — {len(result.drift)} item(s):\n")
            for item in result.drift:
                prefix = "  [LOUD] " if item.drift == DriftType.UNGOVERNED_GRANT else "  "
                typer.echo(f"{prefix}{item.drift.value:20s}  {item.capability_id}")
                typer.echo(f"           {item.detail}")
            if result.aligned:
                typer.echo(f"\nAligned ({len(result.aligned)}): {', '.join(result.aligned[:5])}" +
                           (" ..." if len(result.aligned) > 5 else ""))

    if not result.ok:
        raise typer.Exit(code=1)


@app.command("conflict")
def cmd_conflict(
    manifest: Optional[Path] = typer.Option(None, "--manifest", "-m", help="Path to provider-manifest.yaml"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Cross-consumer conflict detection: no wallet shared across consumers (ADR-0004)."""
    mpath = _find_manifest(manifest)
    mf = load_manifest(mpath)

    specs: list[dict] = []
    runner = LiveSpecRunner()
    for consumer in mf.consumers:
        for net in consumer.networks:
            spec = runner.run(consumer.ref, net)
            if spec:
                specs.append(spec)
            else:
                typer.echo(
                    f"WARNING: could not fetch spec for {consumer.ref}/{net} — skipped",
                    err=True,
                )

    result = conflict_detect(specs)

    if json_output:
        typer.echo(json.dumps(result.as_dict(), indent=2))
    else:
        if result.ok:
            typer.echo("OK — no wallet conflicts detected across consumers.")
        else:
            typer.echo(f"CONFLICT — {len(result.conflicts)} wallet(s) shared across consumers:\n")
            for conflict in result.conflicts:
                typer.echo(f"  wallet: {conflict.wallet_name!r}")
                typer.echo(f"  consumers: {', '.join(conflict.consumers)}")

    if not result.ok:
        raise typer.Exit(code=1)


@app.command("verify-consumer")
def cmd_verify_consumer(
    consumer: str = typer.Argument(..., help="Consumer name (e.g. fsp, claim)"),
    network: Optional[str] = typer.Option(None, "--network", "-n", help="Network for spec call"),
    spec_file: Optional[Path] = typer.Option(None, "--spec-file", help="Path to saved spec --json output (offline mode)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Run §8 conformance checklist against a consumer."""
    if spec_file:
        with spec_file.open() as f:
            spec = json.load(f)
    else:
        # Call live spec
        cmd = [consumer, "spec", "--json"]
        if network:
            cmd += ["--network", network]
        try:
            result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result_proc.returncode != 0:
                typer.echo(f"ERROR: {consumer} spec --json failed (exit {result_proc.returncode})", err=True)
                typer.echo(result_proc.stderr, err=True)
                raise typer.Exit(code=2)
            spec = json.loads(result_proc.stdout)
        except FileNotFoundError:
            typer.echo(f"ERROR: consumer CLI {consumer!r} not found in PATH", err=True)
            raise typer.Exit(code=2)
        except json.JSONDecodeError as e:
            typer.echo(f"ERROR: spec output is not valid JSON: {e}", err=True)
            raise typer.Exit(code=2)

    result = verify(consumer, spec, network)

    if json_output:
        typer.echo(json.dumps(result.as_dict(), indent=2))
    else:
        status = "CONFORMANT" if result.conformant else "NON-CONFORMANT"
        typer.echo(f"{consumer}: {status}\n")
        for check in result.checks:
            icon = {"pass": "✓", "fail": "✗", "skipped(runtime)": "·"}[check.status.value]
            typer.echo(f"  {icon} {check.check}: {check.name}")
            if check.detail:
                typer.echo(f"       {check.detail}")
        typer.echo(
            f"\n  {len(result.passed)} passed, {len(result.failed)} failed, "
            f"{len(result.skipped)} skipped(runtime)"
        )

    if not result.conformant:
        raise typer.Exit(code=1)


@app.command("review")
def cmd_review(
    manifest: Optional[Path] = typer.Option(None, "--manifest", "-m", help="Path to provider-manifest.yaml"),
    fwd_grants: Optional[Path] = typer.Option(None, "--fwd-grants", help="Path to JSON file of fwd granted capability_ids"),
) -> None:
    """Render pending custody diffs awaiting the human gate (pending-gate items)."""
    mpath = _find_manifest(manifest)
    mf = load_manifest(mpath)

    consumer_pairs = [(c.ref, c.networks) for c in mf.consumers]
    desired = ManifestSource(consumer_pairs, LiveSpecRunner()).desired()

    granted: set[str] = set()
    if fwd_grants:
        granted = FileFwdGrantSource(fwd_grants).granted()

    pending = desired - granted
    if not pending:
        typer.echo("No pending custody gates — all desired capabilities are granted.")
        return

    typer.echo(f"Pending custody gates ({len(pending)} capability_ids):\n")
    typer.echo("Run `<consumer> spec` to see the full adjudicable diff for each.")
    typer.echo("After review, use `fwdctl capability grant --approve ...` to grant.\n")

    runner = LiveSpecRunner()
    rendered_consumers: set[str] = set()
    for cid in sorted(pending):
        consumer = cid.split("/")[0]
        net = cid.split("/")[1] if "/" in cid else "unknown"
        key = f"{consumer}/{net}"
        if key in rendered_consumers:
            continue
        rendered_consumers.add(key)
        typer.echo(f"--- spec: {consumer} --network {net} ---")
        spec_output = runner.run(consumer, net)
        if spec_output is None:
            # Fall back to showing the capability_ids
            for p in sorted(pending):
                if p.startswith(f"{consumer}/{net}/"):
                    typer.echo(f"  {p}")
        else:
            # Show non-json spec output
            cmd = [consumer, "spec", "--network", net]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.stdout:
                    typer.echo(proc.stdout)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                for p in sorted(pending):
                    if p.startswith(f"{consumer}/{net}/"):
                        typer.echo(f"  {p}")


@app.command("plan")
def cmd_plan() -> None:
    """[STUB] Deployment actions to converge toward the manifest."""
    typer.echo("provider plan: not yet implemented (deferred until consumer #2 is named).")
    raise typer.Exit(code=0)


@app.command("next")
def cmd_next() -> None:
    """[STUB] Next single runbook step (cursor-advised, ground-truth-checked)."""
    typer.echo("provider next: not yet implemented (deferred until consumer #2 is named).")
    raise typer.Exit(code=0)


@app.command("verify")
def cmd_verify() -> None:
    """[STUB] Run membrane invariants across the deployment."""
    typer.echo("provider verify: not yet implemented (deferred until consumer #2 is named).")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()

"""The clif bridge — transport only (ADR-0006 §2: "CLI is the substrate; MCP wraps it").

Every tool is a thin wrapper over a `clif <cmd> --json` invocation run INSIDE the
already-deployed, already-scoped clif container via `docker exec`. Consequences,
by construction:

- The MCP server holds **no keys and no caller tokens** — the read tokens and the
  scoped funding token live only in the container's env; fwd's policy is the final
  gate regardless of any bug here (ADR-0006 §3/§58). This is strictly stronger than
  "holds only the scoped token": it holds none.
- `epoch status` reads the daemon's on-disk `CLIF_STATE_DIR`, which lives inside the
  container — exec is the only way to see it (a separate `clif` process would not).

No business logic is duplicated here: clif owns validation, execution, exit codes,
and the JSON schemas. This module runs the command and returns its JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

_DEFAULT_NETWORKS = ("flare", "songbird")


class BridgeError(RuntimeError):
    """A transport failure (container down, docker missing, non-JSON output, timeout)."""


@dataclass(frozen=True)
class ClifResult:
    """A clif invocation's outcome: its parsed --json body + the process exit code.

    clif emits JSON on stdout even for non-zero exits (e.g. `epoch status` exits 2
    when degraded but still prints the report), so `data` is populated whenever
    stdout parsed, independent of `exit_code`."""

    data: dict
    exit_code: int


# The default runner. Split out so tests inject a fake without a real docker/clif.
def _subprocess_runner(cmd: Sequence[str], timeout: float) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(  # noqa: S603 — args are constructed, never shell-interpolated
            list(cmd), capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as exc:  # docker binary missing
        raise BridgeError(f"docker not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BridgeError(f"clif call timed out after {timeout}s: {' '.join(cmd)}") from exc
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class ClifBridge:
    """Runs `clif ... --json` inside a clif container. All config is env-overridable.

    read_container/fund_container are `.format(net=...)` templates. Reads route to the
    epoch daemon container (it carries every token AND the state file); funding routes
    to the fund daemon container (which carries the scoped funding token)."""

    docker: str = "docker"
    read_container: str = "clif-epoch-{net}"
    fund_container: str = "clif-fund-{net}"
    networks: tuple[str, ...] = _DEFAULT_NETWORKS
    timeout: float = 90.0
    allow_apply: bool = False
    runner: Callable[[Sequence[str], float], tuple[int, str, str]] = field(
        default=_subprocess_runner, repr=False
    )

    @classmethod
    def from_env(cls) -> ClifBridge:
        nets = os.environ.get("FLARESYSTEMS_MCP_NETWORKS")
        return cls(
            docker=os.environ.get("FLARESYSTEMS_MCP_DOCKER", "docker"),
            read_container=os.environ.get("FLARESYSTEMS_MCP_READ_CONTAINER", "clif-epoch-{net}"),
            fund_container=os.environ.get("FLARESYSTEMS_MCP_FUND_CONTAINER", "clif-fund-{net}"),
            networks=tuple(n.strip() for n in nets.split(",") if n.strip()) if nets else _DEFAULT_NETWORKS,
            timeout=float(os.environ.get("FLARESYSTEMS_MCP_TIMEOUT", "90")),
            allow_apply=os.environ.get("FLARESYSTEMS_MCP_ALLOW_APPLY", "false").lower() == "true",
        )

    def _check_network(self, network: str) -> None:
        if network not in self.networks:
            raise BridgeError(
                f"unknown/disabled network {network!r}; configured: {', '.join(self.networks)}"
            )

    def run(self, args: Sequence[str], *, network: str, fund: bool = False) -> ClifResult:
        """Exec `clif <args> --json` in the network's container. `fund=True` routes to
        the fund container (funding token). Parses stdout JSON regardless of exit code."""
        self._check_network(network)
        template = self.fund_container if fund else self.read_container
        container = template.format(net=network)
        cmd = [self.docker, "exec", container, "clif", *args, "--json"]
        code, out, errtxt = self.runner(cmd, self.timeout)
        out = (out or "").strip()
        if not out:
            raise BridgeError(
                f"clif produced no JSON (container={container}, exit={code}): "
                f"{(errtxt or '').strip()[:400] or 'no stderr'}"
            )
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            raise BridgeError(
                f"clif output was not JSON (container={container}, exit={code}): {out[:400]}"
            ) from exc
        return ClifResult(data=data, exit_code=code)

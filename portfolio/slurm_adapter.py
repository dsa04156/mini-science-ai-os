from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
JOB_ID = re.compile(r"[0-9]+")


class SlurmValidationError(ValueError):
    """Raised before any scheduler command is attempted."""


class SlurmCommandError(RuntimeError):
    """Raised when a scheduler command returns an unusable result."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, timeout_seconds: int = 30) -> CommandResult: ...


class SubprocessRunner:
    """Run an argv vector without a shell or caller-controlled environment."""

    def run(self, argv: Sequence[str], *, timeout_seconds: int = 30) -> CommandResult:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            env=env,
            shell=False,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class SlurmJobSpec:
    name: str
    script: str
    gpus: int = 0
    cpus: int = 1
    memory_mb: int = 1024
    partition: str | None = None

    def validate(self) -> None:
        if not SAFE_NAME.fullmatch(self.name):
            raise SlurmValidationError("name must be 1-64 safe identifier characters")
        if self.partition is not None and not SAFE_NAME.fullmatch(self.partition):
            raise SlurmValidationError("partition must be a safe identifier")
        if not 0 <= self.gpus <= 64:
            raise SlurmValidationError("gpus must be between 0 and 64")
        if not 1 <= self.cpus <= 4096:
            raise SlurmValidationError("cpus must be between 1 and 4096")
        if not 128 <= self.memory_mb <= 16 * 1024 * 1024:
            raise SlurmValidationError("memory_mb must be between 128 MiB and 16 TiB")


@dataclass(frozen=True)
class SlurmNode:
    name: str
    state: str
    cpus: int
    memory_mb: int
    gres: str


@dataclass(frozen=True)
class SlurmJob:
    job_id: str
    state: str
    reason: str


class SlurmCliAdapter:
    """Small SLURM CLI boundary; not connected to the product control plane."""

    def __init__(self, *, runner: CommandRunner | None = None, script_root: Path | str = ".") -> None:
        self.runner = runner or SubprocessRunner()
        self.script_root = Path(script_root).resolve()

    def plan_submit(self, spec: SlurmJobSpec) -> list[str]:
        spec.validate()
        script = self._resolve_script(spec.script)
        argv = [
            "sbatch",
            "--parsable",
            f"--job-name={spec.name}",
            f"--cpus-per-task={spec.cpus}",
            f"--mem={spec.memory_mb}M",
        ]
        if spec.partition:
            argv.append(f"--partition={spec.partition}")
        if spec.gpus:
            argv.append(f"--gres=gpu:{spec.gpus}")
        argv.append(str(script))
        return argv

    def submit(self, spec: SlurmJobSpec) -> str:
        result = self._checked(self.plan_submit(spec))
        candidate = result.stdout.strip().split(";", 1)[0]
        return self._validated_job_id(candidate)

    def list_nodes(self) -> list[SlurmNode]:
        result = self._checked(["sinfo", "-h", "-N", "-o", "%N|%a|%c|%m|%G"])
        nodes: list[SlurmNode] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            fields = line.strip().split("|", 4)
            if len(fields) != 5:
                raise SlurmCommandError(f"unexpected sinfo row: {line!r}")
            name, state, cpus, memory_mb, gres = fields
            try:
                nodes.append(SlurmNode(name, state, int(cpus), int(memory_mb), gres))
            except ValueError as exc:
                raise SlurmCommandError(f"invalid numeric value in sinfo row: {line!r}") from exc
        return nodes

    def status(self, job_id: str) -> SlurmJob:
        validated = self._validated_job_id(job_id)
        current = self._checked(["squeue", "-h", "-j", validated, "-o", "%i|%T|%R"])
        row = self._single_row(current.stdout)
        if row:
            return self._parse_job_row(row, source="squeue")

        history = self._checked(
            ["sacct", "-n", "-X", "-P", "-j", validated, "-o", "JobIDRaw,State,ExitCode"]
        )
        row = self._single_row(history.stdout)
        if not row:
            raise SlurmCommandError(f"job {validated} was not found in squeue or sacct")
        return self._parse_job_row(row, source="sacct")

    def cancel(self, job_id: str) -> None:
        validated = self._validated_job_id(job_id)
        self._checked(["scancel", validated])

    def _resolve_script(self, script: str) -> Path:
        candidate = (self.script_root / script).resolve()
        if candidate != self.script_root and self.script_root not in candidate.parents:
            raise SlurmValidationError("script must stay inside script_root")
        if not candidate.is_file():
            raise SlurmValidationError(f"script does not exist: {script}")
        return candidate

    @staticmethod
    def _validated_job_id(job_id: str) -> str:
        if not JOB_ID.fullmatch(job_id):
            raise SlurmValidationError("job_id must contain digits only")
        return job_id

    def _checked(self, argv: Sequence[str]) -> CommandResult:
        result = self.runner.run(argv)
        if result.returncode != 0:
            detail = result.stderr.strip() or "no error detail"
            raise SlurmCommandError(f"{argv[0]} failed with {result.returncode}: {detail}")
        return result

    @staticmethod
    def _single_row(output: str) -> str | None:
        return next((line.strip() for line in output.splitlines() if line.strip()), None)

    @staticmethod
    def _parse_job_row(row: str, *, source: str) -> SlurmJob:
        fields = row.split("|", 2)
        if len(fields) != 3:
            raise SlurmCommandError(f"unexpected {source} row: {row!r}")
        job_id, state, reason = fields
        return SlurmJob(job_id=job_id, state=state, reason=reason)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a safe SLURM sbatch invocation without executing it")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--name", required=True)
    plan.add_argument("--script", required=True)
    plan.add_argument("--script-root", default=".")
    plan.add_argument("--gpus", type=int, default=0)
    plan.add_argument("--cpus", type=int, default=1)
    plan.add_argument("--memory-mb", type=int, default=1024)
    plan.add_argument("--partition")
    return parser


def main() -> int:
    args = _parser().parse_args()
    adapter = SlurmCliAdapter(script_root=args.script_root)
    spec = SlurmJobSpec(
        name=args.name,
        script=args.script,
        gpus=args.gpus,
        cpus=args.cpus,
        memory_mb=args.memory_mb,
        partition=args.partition,
    )
    print(json.dumps({"executes": False, "argv": adapter.plan_submit(spec)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

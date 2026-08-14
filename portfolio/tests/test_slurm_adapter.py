from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pytest

from portfolio.slurm_adapter import (
    CommandResult,
    SlurmCliAdapter,
    SlurmCommandError,
    SlurmJobSpec,
    SlurmValidationError,
)


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.calls: list[list[str]] = []

    def run(self, argv: Sequence[str], *, timeout_seconds: int = 30) -> CommandResult:
        self.calls.append(list(argv))
        return self.results.pop(0)


@pytest.fixture
def script_root(tmp_path: Path) -> Path:
    script = tmp_path / "train.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return tmp_path


def test_plan_submit_is_an_argv_vector_with_validated_resources(script_root: Path) -> None:
    adapter = SlurmCliAdapter(script_root=script_root)
    command = adapter.plan_submit(
        SlurmJobSpec("spectroscopy", "train.sh", gpus=2, cpus=8, memory_mb=32768, partition="gpu")
    )

    assert command == [
        "sbatch",
        "--parsable",
        "--job-name=spectroscopy",
        "--cpus-per-task=8",
        "--mem=32768M",
        "--partition=gpu",
        "--gres=gpu:2",
        str(script_root / "train.sh"),
    ]


def test_script_cannot_escape_the_approved_root(script_root: Path) -> None:
    adapter = SlurmCliAdapter(script_root=script_root)

    with pytest.raises(SlurmValidationError, match="script must stay inside"):
        adapter.plan_submit(SlurmJobSpec("escape", "../outside.sh"))


def test_submit_returns_only_a_numeric_job_id(script_root: Path) -> None:
    runner = FakeRunner([CommandResult(0, "9182;cluster-a\n")])
    adapter = SlurmCliAdapter(runner=runner, script_root=script_root)

    assert adapter.submit(SlurmJobSpec("analysis", "train.sh")) == "9182"
    assert runner.calls[0][0] == "sbatch"


def test_list_nodes_parses_scheduler_inventory(script_root: Path) -> None:
    runner = FakeRunner([CommandResult(0, "gpu01|up|64|512000|gpu:a100:4\ncpu01|up|32|128000|(null)\n")])
    adapter = SlurmCliAdapter(runner=runner, script_root=script_root)

    nodes = adapter.list_nodes()

    assert [(node.name, node.cpus, node.gres) for node in nodes] == [
        ("gpu01", 64, "gpu:a100:4"),
        ("cpu01", 32, "(null)"),
    ]


def test_status_falls_back_to_accounting_for_completed_job(script_root: Path) -> None:
    runner = FakeRunner([CommandResult(0, ""), CommandResult(0, "9182|COMPLETED|0:0\n")])
    adapter = SlurmCliAdapter(runner=runner, script_root=script_root)

    status = adapter.status("9182")

    assert status.state == "COMPLETED"
    assert [call[0] for call in runner.calls] == ["squeue", "sacct"]


def test_job_id_rejects_command_injection_without_calling_runner(script_root: Path) -> None:
    runner = FakeRunner([])
    adapter = SlurmCliAdapter(runner=runner, script_root=script_root)

    with pytest.raises(SlurmValidationError, match="digits only"):
        adapter.cancel("9182;rm")
    assert runner.calls == []


def test_scheduler_failure_is_reported_without_stdout_guessing(script_root: Path) -> None:
    runner = FakeRunner([CommandResult(1, stderr="controller unavailable")])
    adapter = SlurmCliAdapter(runner=runner, script_root=script_root)

    with pytest.raises(SlurmCommandError, match="controller unavailable"):
        adapter.list_nodes()

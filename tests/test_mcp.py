from __future__ import annotations

import asyncio

from science_os import mcp_server


def test_mcp_server_exposes_required_tools() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "list_available_resources",
        "submit_science_job",
        "get_job_status",
        "get_run_metrics",
        "list_experiment_runs",
        "cancel_own_job",
    } <= names

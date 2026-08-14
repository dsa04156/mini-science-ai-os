from __future__ import annotations

from science_os.kfp_launcher import _last_result


def test_last_result_parses_json_and_python_client_log_forms() -> None:
    expected = {"science_job_id": "abc", "metrics": {"loss": 0.1}}
    assert _last_result('{"science_job_id":"abc","metrics":{"loss":0.1}}') == expected
    assert _last_result("{'science_job_id': 'abc', 'metrics': {'loss': 0.1}}") == expected

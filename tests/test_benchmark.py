import json
from pathlib import Path

import pytest

from graphsentinel.graph import FixtureGraph
from scripts.run_benchmark import run_benchmark


def test_runner_writes_before_and_after_artifacts(tmp_path):
    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    manifest = [
        {"case_id": "sample_01", "transaction_id": "T100", "trigger": "risk_model", "additional_evidence": {"kind": "customer_confirmation", "value": "denied"}},
        {"case_id": "sample_02", "transaction_id": "T102", "trigger": "analyst_request"},
    ]
    report = run_benchmark(manifest, graph, tmp_path, require_20=False)
    first = json.loads((tmp_path / "sample_01" / "final_answer.json").read_text())
    assert first["before_additional_evidence"]["action"] == "REQUEST_CUSTOMER_CONFIRMATION"
    assert first["after_additional_evidence"]["action"] == "BLOCK_CARD"
    assert first["after_additional_evidence"]["approval_required"] is True
    assert (tmp_path / "sample_01" / "investigation.json").exists()
    assert (tmp_path / "sample_01" / "sar_draft.md").exists()
    assert report["case_count"] == 2
    assert report["accuracy"] is None


def test_submission_mode_refuses_incomplete_or_duplicate_manifest(tmp_path):
    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    one = [{"case_id": "case_01", "transaction_id": "T100"}]
    with pytest.raises(ValueError, match="20"):
        run_benchmark(one, graph, tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        run_benchmark(one + one, graph, tmp_path, require_20=False)

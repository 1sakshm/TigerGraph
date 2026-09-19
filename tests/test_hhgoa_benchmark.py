from pathlib import Path

import pytest

from graphsentinel.hhgoa.contracts import Answer
from graphsentinel.hhgoa.dataset import DatasetQueries
from graphsentinel.hhgoa.engine import BenchmarkInvestigator
from graphsentinel.hhgoa.policy import validate_actions


PRIVATE = Path(__file__).resolve().parents[1] / "data" / "private" / "analysis.duckdb"


@pytest.mark.skipif(not PRIVATE.exists(), reason="HHGOA data is private and not committed")
def test_all_20_real_cases_are_evidence_cited_and_policy_valid():
    data = DatasetQueries(PRIVATE)
    investigator = BenchmarkInvestigator(data)
    answers = [investigator.investigate(trigger) for trigger in data.triggers()]
    assert len(answers) == 20
    assert len({item.case_id for item in answers}) == 20
    for answer in answers:
        assert isinstance(answer, Answer)
        trigger = data.trigger(answer.case_id)
        assert answer.case.evidence
        assert any(trigger["flagged_txn_id"] in e.entity_ids for e in answer.case.evidence)
        assert answer.tool_calls > 0
        assert answer.tokens == 0
        assert not answer.case.written_to_graph  # local analysis cannot claim TigerGraph writeback
        assert not answer.case.graph_case_id
        validate_actions(answer.next_best_actions.initial, answer.case.exposure_usd)
        validate_actions(answer.next_best_actions.final, answer.case.exposure_usd)
        if answer.case.verdict == "legitimate":
            assert not answer.case.affected_txn_ids
            assert not answer.sar.file
        for evidence in answer.case.evidence:
            assert all(data.entity_exists(identifier) for identifier in evidence.entity_ids)

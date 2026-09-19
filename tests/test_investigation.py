from pathlib import Path

import pytest

from graphsentinel.graph import FixtureGraph
from graphsentinel.investigator import Investigator
from graphsentinel.policy import PolicyEngine


@pytest.fixture
def investigator():
    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    return Investigator(graph, PolicyEngine())


def test_initial_investigation_requests_valuable_evidence(investigator):
    case = investigator.investigate("T100", "risk_model")
    assert case.data_provenance == "SYNTHETIC_DEMO_ONLY"
    assert case.risk > 0.7
    assert case.confidence < 0.8
    assert case.recommendations[0].action == "REQUEST_CUSTOMER_CONFIRMATION"
    assert case.status == "WAITING_FOR_EVIDENCE"
    assert "customer confirmation" in case.stop_reason.lower()
    assert {e.kind for e in case.evidence} >= {"shared_device", "new_device", "amount_anomaly"}
    assert case.related_cases[0].id == "HIST-1"
    assert 0 < case.related_cases[0].similarity < 1
    assert case.recommendations[0].evidence_ids
    assert any(event.tool == "graph.neighborhood" for event in case.trace)
    assert next(event for event in case.trace if event.tool == "graph.neighborhood").parameters["transaction_id"] == "T100"


def test_customer_denial_changes_action_but_requires_approval(investigator):
    case = investigator.investigate("T100", "risk_model")
    updated = investigator.add_evidence(case, "customer_confirmation", "denied")
    assert [r.action for r in updated.recommendations] == [
        "REQUEST_CUSTOMER_CONFIRMATION", "BLOCK_CARD"
    ]
    assert updated.confidence >= 0.9
    assert updated.status == "APPROVAL_REQUIRED"
    assert "human approval" in updated.stop_reason.lower()
    assert updated.recommendations[-1].approval_required
    assert updated.recommendations[-1].status == "pending_approval"
    assert "BLOCK_CARD" not in updated.actions_taken
    assert sum(event.tool == "graph.neighborhood" for event in updated.trace) == 2


def test_customer_confirmation_reduces_risk(investigator):
    case = investigator.investigate("T100", "risk_model")
    updated = investigator.add_evidence(case, "customer_confirmation", "confirmed")
    assert updated.risk < 0.3
    assert updated.confidence >= 0.9
    assert updated.recommendations[-1].action == "MONITOR_ACCOUNT"


def test_analyst_approval_controls_execution(investigator):
    case = investigator.add_evidence(
        investigator.investigate("T100", "risk_model"), "customer_confirmation", "denied"
    )
    with pytest.raises(PermissionError):
        investigator.decide(case, "approve", analyst_id="")
    assert "BLOCK_CARD" not in case.actions_taken
    decided = investigator.decide(case, "approve", analyst_id="analyst-7")
    assert "BLOCK_CARD" in decided.actions_taken
    assert decided.recommendations[-1].status == "executed"


def test_invalid_evidence_cannot_force_card_block(investigator):
    case = investigator.investigate("T100", "risk_model")
    with pytest.raises(ValueError):
        investigator.add_evidence(case, "customer_confirmation", "maybe")
    assert len(case.recommendations) == 1


def test_unapproved_block_is_denied_by_policy(investigator):
    with pytest.raises(PermissionError):
        investigator.policy.execute("BLOCK_CARD")
    with pytest.raises(PermissionError):
        investigator.policy.execute("WIPE_ACCOUNT")

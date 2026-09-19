import pytest
from pydantic import ValidationError

from graphsentinel.hhgoa.contracts import Action, Answer, CasePart, EvidenceItem, NextActions, Sar
from graphsentinel.hhgoa.policy import route_for, validate_actions


def test_exact_policy_routes_and_high_impact_gate():
    assert route_for("BLOCK_CARD", 2500) == "L1"
    assert route_for("BLOCK_CARD", 2500.01) == "L2"
    assert route_for("FILE_REPORT", 20) == "L2"
    assert route_for("VERIFY_WITH_CUSTOMER", 20) == "auto"
    with pytest.raises(ValueError):
        validate_actions([Action(action="BLOCK_ALL_CARDS", route="L2", reason="R10")], 100, 1, False)


def test_answer_rejects_invented_ids_and_inconsistent_report():
    case = CasePart(
        status="open", verdict="uncertain", fraud_probability=0.5, pattern="none",
        pattern_description="", affected_txn_ids=[], first_suspicious_txn_id="",
        connected_card_ids=[], connected_device_profiles=[], exposure_usd=0,
        evidence=[EvidenceItem(claim="Flagged score", source="graph", ref="query:transaction",
                               entity_ids=["3514030"])], similar_prior_cases=[],
        summary="The model flagged a transaction. Its origin remains uncertain.",
        written_to_graph=False, graph_case_id="",
    )
    answer = Answer(
        case_id="HHG-001", case=case, evidence_requests=[],
        next_best_actions=NextActions(
            initial=[Action(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1: weak signal")],
            final=[Action(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1: weak signal")],
            what_changed="nothing",
        ), sar=Sar(file=False, reason="R3: no report threshold met", narrative="",
                   subjects=[], total_amount_usd=0, activity_dates=[]),
        stop_reason="Waiting for evidence", tool_calls=1, tokens=0, latency_s=0.1,
    )
    assert answer.model_dump()["case"]["evidence"][0]["entity_ids"] == ["3514030"]
    with pytest.raises(ValidationError):
        answer.model_copy(update={"case_id": "FAKE-001"}).model_validate(
            {**answer.model_dump(), "case_id": "FAKE-001"}
        )
    with pytest.raises(ValidationError):
        Answer.model_validate({**answer.model_dump(), "sar": {**answer.sar.model_dump(), "file": True}})

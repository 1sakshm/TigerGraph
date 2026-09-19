import json
from pathlib import Path

import httpx

from graphsentinel.graph import FixtureGraph
from graphsentinel.investigator import Investigator
from graphsentinel.policy import PolicyEngine
from graphsentinel.synthesis import OpenAISummarizer


def test_summary_uses_structured_evidence_and_validates_citations():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        response = {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"summary": "Device links multiple accounts [E-003].", "cited_evidence_ids": ["E-003"]})}]}]}
        return httpx.Response(200, json=response)

    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    summarizer = OpenAISummarizer("test-key", "test-model", client=httpx.Client(transport=httpx.MockTransport(handler)))
    case = Investigator(graph, PolicyEngine(), summarizer=summarizer).investigate("T100", "risk_model")
    assert case.reasoning_summary == "Device links multiple accounts [E-003]."
    assert calls[0]["text"]["format"]["type"] == "json_schema"
    assert "D_NEW" in calls[0]["input"]


def test_invalid_llm_citation_falls_back_to_grounded_summary():
    def handler(request):
        response = {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"summary": "A claim [E-999].", "cited_evidence_ids": ["E-999"]})}]}]}
        return httpx.Response(200, json=response)

    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    summarizer = OpenAISummarizer("test-key", "test-model", client=httpx.Client(transport=httpx.MockTransport(handler)))
    case = Investigator(graph, PolicyEngine(), summarizer=summarizer).investigate("T100", "risk_model")
    assert "E-999" not in case.reasoning_summary
    assert "E-" in case.reasoning_summary
    assert any(event.state == "LLM_SYNTHESIS" and "fallback" in event.result for event in case.trace)

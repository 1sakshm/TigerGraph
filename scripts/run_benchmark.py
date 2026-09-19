"""Run a supplied benchmark manifest without embedding answers in the code."""

import argparse
import json
import os
import re
import time
from pathlib import Path

from graphsentinel.graph import FixtureGraph, GraphPort
from graphsentinel.investigator import Investigator
from graphsentinel.models import CaseRecord, Recommendation
from graphsentinel.policy import PolicyEngine
from graphsentinel.store import CaseStore
from graphsentinel.tigergraph import TigerGraphGraph


SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _action(recommendation: Recommendation | None) -> dict | None:
    if recommendation is None:
        return None
    return recommendation.model_dump(mode="json")


def _sar_draft(case: CaseRecord) -> str:
    lines = [
        f"# Draft suspicious activity report — {case.id}", "",
        "Draft for analyst review only. No report was filed.", "",
        f"Transaction: {case.transaction_id}",
        f"Risk estimate: {case.risk:.0%}; evidence confidence heuristic: {case.confidence:.0%}",
        "", "## Supported observations", "",
    ]
    lines.extend(f"- [{e.id}] {e.claim} (source: {e.source})" for e in case.evidence)
    lines.extend(["", "## Proposed action", "", case.recommendations[-1].action,
                  "", "Analyst authorization is required before filing or any card block."])
    return "\n".join(lines) + "\n"


def run_benchmark(manifest: list[dict], graph: GraphPort, output: Path, require_20: bool = True) -> dict:
    if require_20 and len(manifest) != 20:
        raise ValueError("Submission benchmark requires exactly 20 cases")
    names = [item.get("case_id", "") for item in manifest]
    if len(names) != len(set(names)):
        raise ValueError("Manifest contains duplicate case IDs")
    if any(not SAFE_ID.fullmatch(name) for name in names):
        raise ValueError("Each case_id must be a safe alphanumeric path component")
    if any(not item.get("transaction_id") for item in manifest):
        raise ValueError("Every case needs a transaction_id")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    store = CaseStore(output / "cases.sqlite")
    investigator = Investigator(graph, PolicyEngine())
    failures = []
    query_count = 0
    latencies = []
    for item in manifest:
        start = time.perf_counter()
        folder = output / item["case_id"]
        folder.mkdir(exist_ok=True)
        try:
            case = investigator.investigate(item["transaction_id"], item.get("trigger", "benchmark"))
            before = _action(case.recommendations[-1])
            store.save(case)
            graph.save_case(case)
            additional = item.get("additional_evidence")
            if additional:
                case = investigator.add_evidence(case, additional["kind"], additional["value"])
                store.save(case)
                graph.save_case(case)
            after = _action(case.recommendations[-1])
            query_count += sum(bool(event.tool) for event in case.trace)
            latencies.append(round((time.perf_counter() - start) * 1000, 2))
            final = {
                "benchmark_case_id": item["case_id"],
                "internal_case_id": case.id,
                "transaction_id": case.transaction_id,
                "risk": case.risk,
                "confidence": case.confidence,
                "hypotheses": case.hypotheses,
                "patterns": case.patterns,
                "evidence": [e.model_dump(mode="json") for e in case.evidence],
                "missing_evidence": case.missing_evidence,
                "before_additional_evidence": before,
                "after_additional_evidence": after,
                "approval_route": "human_analyst" if after and after["approval_required"] else "automated_proposal",
                "actions_taken": case.actions_taken,
            }
            (folder / "investigation.json").write_text(case.model_dump_json(indent=2), encoding="utf-8")
            (folder / "final_answer.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
            if case.risk >= 0.9 and any(e.kind == "customer_confirmation" and "denied" in e.claim for e in case.evidence):
                (folder / "sar_draft.md").write_text(_sar_draft(case), encoding="utf-8")
        except (KeyError, ValueError, RuntimeError) as error:
            failures.append({"case_id": item["case_id"], "error": str(error)})
            (folder / "error.json").write_text(json.dumps({"error": str(error)}, indent=2), encoding="utf-8")
    report = {
        "case_count": len(manifest),
        "completed": len(manifest) - len(failures),
        "failures": failures,
        "graph_queries": query_count,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "accuracy": None,
        "accuracy_note": "Unavailable without benchmark ground truth and the actual dataset",
        "mode": "synthetic_demo" if isinstance(graph, FixtureGraph) else "tigergraph",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("cases/generated"))
    parser.add_argument("--allow-incomplete", action="store_true", help="Only for tests or exploratory runs")
    arguments = parser.parse_args()
    raw = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    manifest = raw["cases"] if isinstance(raw, dict) else raw
    if os.environ.get("GRAPHSENTINEL_MODE") == "demo":
        graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    else:
        graph = TigerGraphGraph(os.environ["TIGERGRAPH_URL"], os.environ.get("TIGERGRAPH_GRAPH", "GraphSentinel"), os.environ["TIGERGRAPH_TOKEN"])
    report = run_benchmark(manifest, graph, arguments.output, require_20=not arguments.allow_incomplete)
    print(json.dumps(report, indent=2))
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

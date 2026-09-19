"""Produce the exact 20 HHGOA answer files from the supplied private CSVs.

Offline mode is honest about TigerGraph writeback: written_to_graph stays false.
"""

import argparse
import json
import os
from pathlib import Path

from graphsentinel.hhgoa.dataset import DatasetQueries
from graphsentinel.hhgoa.engine import BenchmarkInvestigator
from graphsentinel.hhgoa.live import TigerGraphDatasetQueries
from graphsentinel.hhgoa.tigergraph import HHGOATigerGraph


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=ROOT / "data/private/analysis.duckdb")
    parser.add_argument("--output", type=Path, default=ROOT / "cases")
    parser.add_argument("--tigergraph", action="store_true",
                        help="Retrieve through installed GSQL and verify each case writeback")
    args = parser.parse_args()
    graph = None
    if args.tigergraph:
        graph = HHGOATigerGraph(os.environ["TIGERGRAPH_URL"], os.environ["TIGERGRAPH_TOKEN"],
                                os.environ.get("TIGERGRAPH_GRAPH", "HHGOA"))
        data = TigerGraphDatasetQueries(args.index, graph)
    else:
        data = DatasetQueries(args.index)
    investigator = BenchmarkInvestigator(data)
    triggers = data.triggers()
    if len(triggers) != 20 or len({row["case_id"] for row in triggers}) != 20:
        raise ValueError("HHGOA benchmark requires exactly 20 distinct cases")
    args.output.mkdir(parents=True, exist_ok=True)
    traces = args.output / "investigations"
    traces.mkdir(exist_ok=True)
    answers = []
    traces_by_case = {}
    for trigger in triggers:
        answer = investigator.investigate(trigger)
        if graph:
            answer = graph.write_answer(answer, trigger)
        answers.append(answer)
        traces_by_case[answer.case_id] = list(investigator.last_trace)
        print(f"{answer.case_id} {answer.case.verdict:9} p={answer.case.fraud_probability:.3f} "
              f"{answer.case.pattern:29} {','.join(a.action for a in answer.next_best_actions.final)}")
    for answer in answers:
        (args.output / f"{answer.case_id}.json").write_text(
            answer.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (traces / f"{answer.case_id}.json").write_text(
            json.dumps(traces_by_case[answer.case_id], indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(answers)} benchmark answers to {args.output}")
    if not graph:
        print("TigerGraph writeback: unavailable in offline mode; each answer reports written_to_graph=false")
    else:
        print("TigerGraph writeback verified for all 20 answers")


if __name__ == "__main__":
    main()

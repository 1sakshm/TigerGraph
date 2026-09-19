"""Check the 20 submitted answers without inventing hidden outcome labels."""

import argparse
from collections import Counter
from pathlib import Path
from statistics import mean

from graphsentinel.hhgoa.contracts import Answer
from graphsentinel.hhgoa.dataset import DatasetQueries
from graphsentinel.hhgoa.policy import validate_actions


ROOT = Path(__file__).resolve().parents[1]


def evaluate(case_dir: Path, index: Path) -> tuple[str, list[str]]:
    data = DatasetQueries(index)
    expected = {row["case_id"] for row in data.triggers()}
    found = {path.stem for path in case_dir.glob("HHG-???.json")}
    failures = []
    if found != expected:
        failures.append(f"Case IDs differ: missing={sorted(expected-found)}, extra={sorted(found-expected)}")
    answers = []
    for case_id in sorted(found & expected):
        answer = Answer.model_validate_json((case_dir / f"{case_id}.json").read_text(encoding="utf-8"))
        answers.append(answer)
        trigger = data.trigger(case_id)
        if answer.case_id != case_id:
            failures.append(f"{case_id}: file and embedded case ID differ")
        if not any(trigger["flagged_txn_id"] in item.entity_ids for item in answer.case.evidence):
            failures.append(f"{case_id}: flagged transaction is not cited")
        for item in answer.case.evidence:
            for entity_id in item.entity_ids:
                if not data.entity_exists(entity_id):
                    failures.append(f"{case_id}: unknown evidence entity {entity_id}")
        for stage in (answer.next_best_actions.initial, answer.next_best_actions.final):
            try:
                validate_actions(stage, answer.case.exposure_usd)
            except ValueError as error:
                failures.append(f"{case_id}: {error}")
        if answer.sar.file:
            sentences = [part.strip() for part in answer.sar.narrative.split(". ") if part.strip()]
            if not 6 <= len(sentences) <= 12:
                failures.append(f"{case_id}: SAR has {len(sentences)} sentences, expected 6–12")
        if answer.case.written_to_graph and not answer.case.graph_case_id:
            failures.append(f"{case_id}: graph write claimed without ID")
    patterns = Counter(answer.case.pattern for answer in answers)
    verdicts = Counter(answer.case.verdict for answer in answers)
    changing = sum(answer.next_best_actions.initial != answer.next_best_actions.final for answer in answers)
    reports = sum(answer.sar.file for answer in answers)
    writes = sum(answer.case.written_to_graph for answer in answers)
    evidence = sum(len(answer.case.evidence) for answer in answers)
    historical = data._rows(
        """WITH seeds AS (
             SELECT outcome,
               CASE WHEN first_fraud_txn_id IS NOT NULL AND first_fraud_txn_id<>''
                    THEN first_fraud_txn_id ELSE split_part(txn_ids,'|',1) END AS id
             FROM history)
           SELECT h.outcome, count(*) AS cases,
                  round(avg(t.risk),3) AS mean_model_score,
                  round(avg(CASE WHEN i.identity_status='New' THEN 1 ELSE 0 END),3)
                    AS new_identity_fraction
           FROM seeds h JOIN tx t USING(id) LEFT JOIN identity i USING(id)
           GROUP BY h.outcome ORDER BY h.outcome"""
    )
    lines = [
        "# Benchmark results",
        "",
        "This report checks answer format, provenance, cited IDs, approval routes, and case coverage. "
        "The challenge does not provide current-case outcome labels, so classification accuracy and "
        "confidence calibration cannot be measured locally.",
        "",
        f"- Cases: **{len(answers)}/20**",
        f"- Contract or evidence validation failures: **{len(failures)}**",
        f"- Evidence items: **{evidence}**",
        f"- Cases with changed next-best-action lists: **{changing}**",
        f"- SAR drafts recommended for L2 approval: **{reports}**",
        f"- Verified TigerGraph case writes: **{writes}**",
        f"- Average recorded retrieval calls: **{mean(a.tool_calls for a in answers):.1f}**" if answers else "- Average recorded retrieval calls: n/a",
        f"- Average recorded latency: **{mean(a.latency_s for a in answers):.3f}s**" if answers else "- Average recorded latency: n/a",
        "",
        "## Historical closed-case diagnostic",
        "",
        "These are selected closed cases, not a representative transaction sample. The table "
        "explains why the engine gives the upstream score and `New` identity flag little weight; "
        "it is not used as a direct probability lookup or a hidden benchmark label.",
        "",
        "| Closed outcome | Cases | Mean upstream score | New identity fraction |",
        "| --- | ---: | ---: | ---: |",
        *[f"| {row['outcome']} | {row['cases']} | {row['mean_model_score']:.3f} | "
          f"{row['new_identity_fraction']:.3f} |" for row in historical],
        "",
        "## Verdicts",
        "",
        *[f"- {key}: {count}" for key, count in sorted(verdicts.items())],
        "",
        "## Patterns",
        "",
        *[f"- {key}: {count}" for key, count in sorted(patterns.items())],
        "",
        "## Case matrix",
        "",
        "| Case | Verdict | Probability | Pattern | Initial actions | Final actions | Graph write |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
        *[
            f"| {a.case_id} | {a.case.verdict} | {a.case.fraud_probability:.3f} | {a.case.pattern} | "
            f"{', '.join(x.action for x in a.next_best_actions.initial)} | "
            f"{', '.join(x.action for x in a.next_best_actions.final)} | "
            f"{'yes' if a.case.written_to_graph else 'no'} |"
            for a in answers
        ],
        "",
        "## Known measurement limits",
        "",
        "- Offline answers cite the supplied CSV index as `external` evidence; they do not claim TigerGraph traversal.",
        "- `customer_id` groups transactions, but the transaction CSV has no explicit `card_id` or merchant ID. "
        "The engine does not infer a specific physical card or merchant from issuer attributes.",
        "- Fraud probabilities and confidence are transparent heuristics; no hidden labels are used for tuning.",
        "- Customer nonresponse in risk-score cases is simulated and labeled in each evidence request.",
        "- The installed GSQL and REST import paths need a live TigerGraph instance for compile and integration verification.",
    ]
    if failures:
        lines += ["", "## Failures", "", *[f"- {failure}" for failure in failures]]
    return "\n".join(lines) + "\n", failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "cases")
    parser.add_argument("--index", type=Path, default=ROOT / "data/private/analysis.duckdb")
    parser.add_argument("--report", type=Path, default=ROOT / "BENCHMARK_RESULTS.md")
    args = parser.parse_args()
    report, failures = evaluate(args.cases, args.index)
    args.report.write_text(report, encoding="utf-8")
    print(f"Wrote {args.report}; validation failures={len(failures)}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

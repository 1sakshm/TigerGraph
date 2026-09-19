"""Import explicit canonical JSONL after a separately reviewed dataset mapping.

No HHGOA column mapping is implied by this script.
"""

import argparse
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from graphsentinel.models import Transaction
from graphsentinel.tigergraph import TigerGraphGraph


class HistoricalCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    account_ids: list[str] = Field(default_factory=list)
    device_ids: list[str] = Field(default_factory=list)
    transaction_ids: list[str] = Field(default_factory=list)
    pattern: str
    outcome: str
    action: str
    summary: str
    updated_at: str = ""


def _edge(edges: dict, source_type: str, source_id: str, edge: str,
          target_type: str, target_id: str) -> None:
    edges.setdefault(source_type, {}).setdefault(source_id, {}).setdefault(edge, {}).setdefault(target_type, {})[target_id] = {}


def build_transaction_payload(transactions: list[Transaction]) -> tuple[dict, int]:
    vertices: dict = {name: {} for name in ("Customer", "Account", "Device", "Merchant", "Transaction")}
    edges: dict = {}
    for tx in transactions:
        vertices["Account"][tx.account_id] = {}
        values = tx.model_dump(mode="json", exclude={"id"}, exclude_none=True)
        vertices["Transaction"][tx.id] = {key: {"value": value} for key, value in values.items()}
        _edge(edges, "Account", tx.account_id, "PERFORMED", "Transaction", tx.id)
        if tx.customer_id:
            vertices["Customer"][tx.customer_id] = {}
            _edge(edges, "Customer", tx.customer_id, "OWNS", "Account", tx.account_id)
        if tx.device_id:
            vertices["Device"][tx.device_id] = {}
            _edge(edges, "Transaction", tx.id, "USED_DEVICE", "Device", tx.device_id)
        if tx.merchant_id:
            vertices["Merchant"][tx.merchant_id] = {}
            _edge(edges, "Transaction", tx.id, "AT_MERCHANT", "Merchant", tx.merchant_id)
    count = sum(len(targets) for sources in edges.values() for relations in sources.values()
                for target_types in relations.values() for targets in target_types.values())
    return {"vertices": {key: value for key, value in vertices.items() if value}, "edges": edges}, count


def import_canonical(source: Path, graph: TigerGraphGraph, batch_size: int = 1000) -> dict:
    if batch_size < 1 or batch_size > 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    total = 0
    batches = 0
    pending: list[Transaction] = []
    with Path(source).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                pending.append(Transaction.model_validate_json(line))
            except (ValidationError, ValueError) as error:
                raise ValueError(f"Line {line_number} is not a canonical transaction: {error}") from error
            if len(pending) >= batch_size:
                payload, edge_count = build_transaction_payload(pending)
                graph.upsert_payload(payload, edge_count)
                total += len(pending)
                batches += 1
                pending.clear()
    if pending:
        payload, edge_count = build_transaction_payload(pending)
        graph.upsert_payload(payload, edge_count)
        total += len(pending)
        batches += 1
    return {"transactions": total, "batches": batches}


def import_historical_cases(source: Path, graph: TigerGraphGraph, batch_size: int = 1000) -> dict:
    if batch_size < 1 or batch_size > 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    total = 0
    pending: list[HistoricalCaseInput] = []

    def flush() -> None:
        nonlocal total
        vertices: dict = {"FraudCase": {}}
        edges: dict = {}
        for item in pending:
            ids = sorted(set(item.account_ids + item.device_ids + item.transaction_ids))
            if not ids:
                raise ValueError(f"Historical case {item.id} has no typed graph entities")
            attributes = {
                "status": "CLOSED", "transaction_id": item.transaction_ids[0] if item.transaction_ids else "",
                "pattern": item.pattern, "outcome": item.outcome, "action": item.action,
                "summary": item.summary, "entity_ids_json": json.dumps(ids),
                "payload_json": item.model_dump_json(), "updated_at": item.updated_at,
            }
            vertices["FraudCase"][item.id] = {key: {"value": value} for key, value in attributes.items()}
            for kind, edge, targets in (("Account", "CASE_ACCOUNT", item.account_ids),
                                         ("Device", "CASE_DEVICE", item.device_ids),
                                         ("Transaction", "CASE_TX", item.transaction_ids)):
                for target in targets:
                    _edge(edges, "FraudCase", item.id, edge, kind, target)
        count = sum(len(targets) for sources in edges.values() for relations in sources.values()
                    for target_types in relations.values() for targets in target_types.values())
        graph.upsert_payload({"vertices": vertices, "edges": edges}, count)
        total += len(pending)
        pending.clear()

    with Path(source).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                pending.append(HistoricalCaseInput.model_validate_json(line))
            except (ValidationError, ValueError) as error:
                raise ValueError(f"Line {line_number} is not a canonical historical case: {error}") from error
            if len(pending) >= batch_size:
                flush()
    if pending:
        flush()
    return {"historical_cases": total}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Canonical transaction JSONL")
    parser.add_argument("--history", type=Path, help="Canonical historical case JSONL")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if not args.input and not args.history:
        parser.error("At least --input or --history is required")
    graph = TigerGraphGraph(os.environ["TIGERGRAPH_URL"], os.environ.get("TIGERGRAPH_GRAPH", "GraphSentinel"), os.environ["TIGERGRAPH_TOKEN"])
    results = {}
    if args.input:
        results.update(import_canonical(args.input, graph, args.batch_size))
    if args.history:
        results.update(import_historical_cases(args.history, graph, args.batch_size))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

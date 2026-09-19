import json
from pathlib import Path
from typing import Protocol

from graphsentinel.models import DevicePeer, Neighborhood, PriorCase, Transaction


class GraphPort(Protocol):
    def neighborhood(self, transaction_id: str, limit: int = 50) -> Neighborhood: ...

    def prior_cases(self, account_id: str, device_id: str | None) -> list[PriorCase]: ...

    def save_case(self, case: object) -> None: ...


class FixtureGraph:
    """Explicit synthetic graph for offline development, never benchmark data."""

    def __init__(self, transactions: list[Transaction], cases: list[PriorCase]):
        self.transactions = {transaction.id: transaction for transaction in transactions}
        self.cases = {case.id: case for case in cases}

    @classmethod
    def from_file(cls, path: Path) -> "FixtureGraph":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("provenance") != "SYNTHETIC_DEMO_ONLY":
            raise ValueError("Offline fixture must declare synthetic provenance")
        return cls(
            [Transaction.model_validate(item) for item in raw["transactions"]],
            [PriorCase.model_validate(item) for item in raw["historical_cases"]],
        )

    def neighborhood(self, transaction_id: str, limit: int = 50) -> Neighborhood:
        if limit < 0 or limit > 200:
            raise ValueError("limit must be between 0 and 200")
        seed = self.transactions[transaction_id]
        history = sorted(
            (t for t in self.transactions.values() if t.account_id == seed.account_id and t.id != seed.id),
            key=lambda t: t.occurred_at,
            reverse=True,
        )
        peers = sorted(
            (
                DevicePeer(
                    transaction_id=t.id,
                    account_id=t.account_id,
                    customer_id=t.customer_id,
                    device_id=t.device_id,
                    model_score=t.model_score,
                )
                for t in self.transactions.values()
                if seed.device_id and t.device_id == seed.device_id and t.account_id != seed.account_id
            ),
            key=lambda p: p.transaction_id,
        )
        history = history[:limit]
        peers = peers[: max(0, limit - len(history))]
        entities = {seed.account_id, seed.id}
        if seed.device_id:
            entities.add(seed.device_id)
        return Neighborhood(
            transaction=seed,
            account_history=history,
            device_peers=peers,
            related_cases=self.prior_cases(seed.account_id, seed.device_id),
        )

    def prior_cases(self, account_id: str, device_id: str | None) -> list[PriorCase]:
        entity_ids = {account_id}
        if device_id:
            entity_ids.add(device_id)
        return sorted(
            (case for case in self.cases.values() if entity_ids.intersection(case.entity_ids)),
            key=lambda case: (-len(entity_ids.intersection(case.entity_ids)), case.id),
        )[:10]

    def save_case(self, case: object) -> None:
        # Offline case persistence is handled by the SQLite store; this collection
        # enables related-case retrieval immediately after case resolution.
        from graphsentinel.models import CaseRecord

        if isinstance(case, CaseRecord) and case.outcome:
            transaction = self.transactions.get(case.transaction_id)
            if transaction:
                ids = [transaction.account_id, transaction.id]
                if transaction.device_id:
                    ids.append(transaction.device_id)
                self.cases[case.id] = PriorCase(
                    id=case.id,
                    entity_ids=ids,
                    pattern=case.patterns[0] if case.patterns else "unclassified",
                    outcome=case.outcome,
                    action=case.recommendations[-1].action if case.recommendations else "NONE",
                    summary=case.analyst_feedback or "Resolved investigation",
                )

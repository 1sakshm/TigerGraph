import json
from urllib.parse import quote

import httpx

from graphsentinel.models import CaseRecord, DevicePeer, Neighborhood, PriorCase, Transaction


class TigerGraphError(RuntimeError):
    pass


def _attrs(values: dict) -> dict:
    return {key: {"value": value} for key, value in values.items()}


class TigerGraphGraph:
    """Only fixed, installed GSQL procedures may be invoked by the investigator."""

    ALLOWED_QUERIES = {
        "gs_transaction_neighborhood", "gs_cases_by_account", "gs_cases_by_device"
    }

    def __init__(self, base_url: str, graph_name: str, token: str, client: httpx.Client | None = None):
        if not base_url.startswith(("https://", "http://")) or not graph_name or not token:
            raise ValueError("TigerGraph URL, graph name and token are required")
        self.base_url = base_url.rstrip("/")
        self.graph_name = graph_name
        self.token = token
        self.client = client or httpx.Client(timeout=10)

    def _post(self, path: str, body: dict) -> dict:
        try:
            response = self.client.post(
                f"{self.base_url}{path}", json=body,
                headers={"Authorization": f"Bearer {self.token}"}, timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TigerGraphError(f"TigerGraph request failed: {error}") from error
        if payload.get("error"):
            raise TigerGraphError(payload.get("message") or "TigerGraph returned an error")
        return payload

    def run_query(self, name: str, params: dict) -> list[dict]:
        if name not in self.ALLOWED_QUERIES:
            raise ValueError(f"Query {name} is not in the allowlist")
        graph = quote(self.graph_name, safe="")
        query = quote(name, safe="")
        return self._post(f"/query/{graph}/{query}", params).get("results", [])

    @staticmethod
    def _items(results: list[dict], label: str) -> list[dict]:
        for result in results:
            if label in result:
                return result[label]
        return []

    @staticmethod
    def _transaction(vertex: dict) -> Transaction:
        data = {**vertex.get("attributes", {}), "id": vertex["v_id"]}
        return Transaction.model_validate(data)

    def neighborhood(self, transaction_id: str, limit: int = 50) -> Neighborhood:
        if limit < 0 or limit > 200:
            raise ValueError("limit must be between 0 and 200")
        results = self.run_query("gs_transaction_neighborhood", {"tx": transaction_id, "max_results": limit})
        seeds = self._items(results, "transaction")
        if not seeds:
            raise KeyError(transaction_id)
        seed = self._transaction(seeds[0])
        history = [self._transaction(vertex) for vertex in self._items(results, "account_history")]
        peers = [
            DevicePeer(
                transaction_id=vertex["v_id"],
                account_id=vertex["attributes"]["account_id"],
                customer_id=vertex["attributes"].get("customer_id"),
                device_id=vertex["attributes"]["device_id"],
                model_score=vertex["attributes"].get("model_score"),
            )
            for vertex in self._items(results, "device_peers")
        ]
        return Neighborhood(transaction=seed, account_history=history[:limit],
                            device_peers=peers[:max(0, limit - len(history))])

    def prior_cases(self, account_id: str, device_id: str | None) -> list[PriorCase]:
        requests = [("gs_cases_by_account", {"account": account_id, "max_results": 10})]
        if device_id:
            requests.append(("gs_cases_by_device", {"device": device_id, "max_results": 10}))
        found: dict[str, PriorCase] = {}
        for name, params in requests:
            for vertex in self._items(self.run_query(name, params), "cases"):
                data = vertex.get("attributes", {})
                if not data.get("outcome"):
                    continue
                try:
                    entity_ids = json.loads(data.get("entity_ids_json", "[]"))
                except (TypeError, json.JSONDecodeError):
                    entity_ids = []
                found[vertex["v_id"]] = PriorCase(
                    id=vertex["v_id"], entity_ids=entity_ids,
                    pattern=data.get("pattern") or "unclassified",
                    outcome=data["outcome"], action=data.get("action") or "NONE",
                    summary=data.get("summary") or "Resolved investigation",
                )
        return sorted(found.values(), key=lambda case: case.id)[:10]

    def save_case(self, case: CaseRecord) -> None:
        account_ids = {n["id"] for n in case.graph.get("nodes", []) if n.get("type") == "Account"}
        device_ids = {n["id"] for n in case.graph.get("nodes", []) if n.get("type") == "Device"}
        tx_ids = {case.transaction_id}
        entity_ids = sorted(account_ids | device_ids | tx_ids)
        current = case.recommendations[-1] if case.recommendations else None
        vertices = {
            "FraudCase": {case.id: _attrs({
                "status": case.status, "transaction_id": case.transaction_id,
                "pattern": case.patterns[0] if case.patterns else "",
                "outcome": case.outcome or "", "action": current.action if current else "",
                "summary": case.analyst_feedback or (current.reason if current else ""),
                "entity_ids_json": json.dumps(entity_ids),
                "payload_json": case.model_dump_json(),
                "updated_at": case.updated_at.isoformat(),
            })},
            "Evidence": {
                f"{case.id}:{evidence.id}": _attrs({
                    "kind": evidence.kind, "claim": evidence.claim,
                    "source": evidence.source, "strength": evidence.strength,
                    "entity_ids_json": json.dumps(evidence.entity_ids),
                }) for evidence in case.evidence
            },
        }
        case_edges: dict = {
            "CASE_TX": {"Transaction": {tx: {} for tx in tx_ids}},
            "CASE_ACCOUNT": {"Account": {account: {} for account in account_ids}},
            "CASE_DEVICE": {"Device": {device: {} for device in device_ids}},
            "CASE_EVIDENCE": {"Evidence": {f"{case.id}:{item.id}": {} for item in case.evidence}},
        }
        expected_edges = len(tx_ids) + len(account_ids) + len(device_ids) + len(case.evidence)
        payload = {"vertices": vertices, "edges": {"FraudCase": {case.id: case_edges}}}
        self.upsert_payload(payload, expected_edges)

    def upsert_payload(self, payload: dict, expected_edges: int) -> None:
        result = self._post(f"/graph/{quote(self.graph_name, safe='')}?atomic_post=true&vertex_must_exist=true", payload)
        stats = result.get("results", [{}])[0]
        if stats.get("accepted_edges", 0) < expected_edges:
            raise TigerGraphError(f"Graph write incomplete: {stats.get('accepted_edges', 0)}/{expected_edges} edges")

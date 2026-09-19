"""HHGOA TigerGraph RESTPP payloads, fixed query API, and verified writeback."""

from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import quote

import httpx

from graphsentinel.hhgoa.contracts import Answer


def _attrs(values: dict) -> dict:
    return {key: {"value": value} for key, value in values.items() if value is not None}


def device_profile_id(row: dict) -> str:
    parts = [row.get(key) or "" for key in ("device_info", "os", "browser", "screen")]
    if not any(parts):
        raise ValueError("No device profile attributes")
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"DP-{digest}"


class GraphPayload:
    def __init__(self):
        self.vertices: dict = {}
        self.edges: dict = {}

    def vertex(self, kind: str, identifier: str, attributes: dict | None = None) -> None:
        self.vertices.setdefault(kind, {}).setdefault(str(identifier), {}).update(_attrs(attributes or {}))

    def edge(self, source_kind: str, source_id: str, name: str,
             target_kind: str, target_id: str) -> None:
        self.edges.setdefault(source_kind, {}).setdefault(str(source_id), {}).setdefault(
            name, {}
        ).setdefault(target_kind, {})[str(target_id)] = {}

    def add_transaction(self, row: dict) -> None:
        tx_id, customer = str(row["id"]), row["customer_id"]
        self.vertex("Customer", customer)
        self.vertex("Transaction", tx_id, {
            "customer_id": customer, "ts": row["ts"], "amount": row["amount"],
            "product": row["product"], "channel": row["channel"], "risk": row["risk"],
            "card1": row.get("card1"), "card2": row.get("card2"),
            "card3": row.get("card3"), "card4": row.get("card4"),
            "card5": row.get("card5"), "card6": row.get("card6"),
            "billing_region": row.get("addr1"), "billing_country": row.get("addr2"),
            "purchaser_email": row.get("email"), "recipient_email": row.get("recipient_email"),
        })
        self.edge("Customer", customer, "MADE", "Transaction", tx_id)
        if row.get("addr1"):
            region = f"{row['addr1']}|{row.get('addr2') or ''}"
            self.vertex("BillingRegion", region)
            self.edge("Transaction", tx_id, "BILLED_IN", "BillingRegion", region)
        for field, edge_name in (("email", "PURCHASER_EMAIL"),
                                 ("recipient_email", "RECIPIENT_EMAIL")):
            if row.get(field):
                domain = row[field]
                self.vertex("EmailDomain", domain)
                self.edge("Transaction", tx_id, edge_name, "EmailDomain", domain)

    def add_identity(self, row: dict) -> None:
        tx_id = str(row["id"])
        self.vertex("Transaction", tx_id, {
            "identity_status": row.get("identity_status"),
            "proxy_status": row.get("proxy_status"),
            "match_status": row.get("match_status"),
            "device_type": row.get("device_type"),
        })
        if any(row.get(key) for key in ("device_info", "os", "browser", "screen")):
            profile = device_profile_id(row)
            parts = [row.get(k) for k in ("device_info", "os", "browser", "screen")]
            self.vertex("DeviceProfile", profile, {
                "label": " | ".join(value or "unknown" for value in parts),
                "device_info": row.get("device_info"), "os": row.get("os"),
                "browser": row.get("browser"), "screen": row.get("screen"),
                "specificity": sum(bool(value) for value in parts),
            })
            self.vertex("Transaction", tx_id, {"device_profile_id": profile})
            self.edge("Transaction", tx_id, "FROM_DEVICE", "DeviceProfile", profile)

    def add_closed_case(self, row: dict) -> None:
        case_id, customer, card = row["case_id"], row["customer_id"], row["card_id"]
        self.vertex("Customer", customer)
        self.vertex("Card", card)
        self.vertex("ClosedCase", case_id, {
            "customer_id": customer, "card_id": card, "outcome": row["outcome"],
            "pattern": row["pattern"], "closed_at": row["closed_at"],
            "exposure": float(row["exposure_usd"] or 0), "notes": row["analyst_notes"],
        })
        self.edge("Customer", customer, "OWNS", "Card", card)
        self.edge("ClosedCase", case_id, "CLOSED_CUSTOMER", "Customer", customer)
        self.edge("ClosedCase", case_id, "CLOSED_CARD", "Card", card)
        for tx_id in filter(None, (row.get("txn_ids") or "").split("|")):
            self.edge("ClosedCase", case_id, "CLOSED_TX", "Transaction", tx_id)
            self.edge("Card", card, "CARD_TX", "Transaction", tx_id)

    def add_anchor(self, row: dict) -> None:
        customer, card, tx_id = row["customer_id"], row["card_id"], row["flagged_txn_id"]
        self.vertex("Customer", customer)
        self.vertex("Card", card)
        self.edge("Customer", customer, "OWNS", "Card", card)
        self.edge("Card", card, "CARD_TX", "Transaction", tx_id)

    def add_answer(self, answer: Answer, trigger: dict) -> None:
        case_id = answer.case_id
        self.vertex("InvestigationCase", case_id, {
            "status": answer.case.status, "verdict": answer.case.verdict,
            "pattern": answer.case.pattern, "probability": answer.case.fraud_probability,
            "summary": answer.case.summary, "answer_json": answer.model_dump_json(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        self.edge("InvestigationCase", case_id, "CASE_CUSTOMER", "Customer", trigger["customer_id"])
        self.edge("InvestigationCase", case_id, "CASE_CARD", "Card", trigger["card_id"])
        for tx_id in set(answer.case.affected_txn_ids + [trigger["flagged_txn_id"]]):
            self.edge("InvestigationCase", case_id, "CASE_TX", "Transaction", tx_id)
        for index, item in enumerate(answer.case.evidence, start=1):
            evidence_id = f"{case_id}:E{index:03d}"
            self.vertex("CaseEvidence", evidence_id, {
                "claim": item.claim, "source": item.source, "reference": item.ref,
                "entity_ids_json": json.dumps(item.entity_ids),
            })
            self.edge("InvestigationCase", case_id, "CASE_EVIDENCE", "CaseEvidence", evidence_id)

    def body(self) -> dict:
        return {"vertices": self.vertices, "edges": self.edges}

    def vertex_count(self) -> int:
        return sum(len(vertices) for vertices in self.vertices.values())

    def edge_count(self) -> int:
        return sum(len(targets) for sources in self.edges.values()
                   for edge_types in sources.values()
                   for target_types in edge_types.values()
                   for targets in target_types.values())


class HHGOATigerGraph:
    ALLOWED_QUERIES = {"hh_transaction_context", "hh_customer_window",
                       "hh_profile_neighbors", "hh_prior_cases", "hh_case_transactions"}

    def __init__(self, base_url: str, token: str, graph: str = "HHGOA",
                 client: httpx.Client | None = None):
        if not base_url.startswith(("http://", "https://")) or not token or not graph:
            raise ValueError("TigerGraph URL, token and graph are required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.graph = graph
        self.client = client or httpx.Client(timeout=60)

    def _post(self, path: str, body: dict, atomic: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"}
        if atomic:
            headers["gsql-atomic-level"] = "atomic"
        response = self.client.post(f"{self.base_url}{path}", json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload.get("message") or "TigerGraph returned an error")
        return payload

    def upsert(self, payload: GraphPayload, require_existing: bool = False) -> dict:
        required = "true" if require_existing else "false"
        return self._post(f"/graph/{quote(self.graph, safe='')}?vertex_must_exist={required}",
                          payload.body(), atomic=True)

    def query(self, name: str, params: dict) -> list[dict]:
        if name not in self.ALLOWED_QUERIES:
            raise ValueError("Only installed HHGOA queries may be invoked")
        response = self._post(f"/query/{quote(self.graph, safe='')}/{quote(name, safe='')}", params)
        return response.get("results", [])

    def write_answer(self, answer: Answer, trigger: dict) -> Answer:
        candidate = Answer.model_validate({
            **answer.model_dump(),
            "case": {**answer.case.model_dump(), "written_to_graph": True, "graph_case_id": answer.case_id},
        })
        # With vertex_must_exist=true, RESTPP does not count vertices created in
        # the same request as existing edge endpoints. Stage a truthful case,
        # attach every edge, then mark the stored answer as graph-backed.
        staged = GraphPayload()
        staged.add_answer(answer, trigger)
        vertices = GraphPayload()
        vertices.vertices = staged.vertices
        result = self.upsert(vertices)
        stats = result.get("results", [{}])[0]
        if stats.get("accepted_vertices", 0) < vertices.vertex_count():
            raise RuntimeError(f"Case vertex writeback incomplete: {stats}")

        edges = GraphPayload()
        edges.edges = staged.edges
        result = self.upsert(edges, require_existing=True)
        stats = result.get("results", [{}])[0]
        if stats.get("accepted_edges", 0) < edges.edge_count():
            raise RuntimeError(f"Case edge writeback incomplete: {stats}")

        committed = GraphPayload()
        committed.vertex("InvestigationCase", answer.case_id, {
            "answer_json": candidate.model_dump_json(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        result = self.upsert(committed)
        stats = result.get("results", [{}])[0]
        if stats.get("accepted_vertices", 0) < 1:
            raise RuntimeError(f"Case completion writeback incomplete: {stats}")
        return candidate

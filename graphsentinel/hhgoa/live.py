"""TigerGraph-backed implementation of the HHGOA investigation query port."""

from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from graphsentinel.hhgoa.dataset import DatasetQueries
from graphsentinel.hhgoa.tigergraph import HHGOATigerGraph, device_profile_id


def _items(results: list[dict], name: str) -> list[dict]:
    for item in results:
        if name in item:
            return item[name]
    return []


def _vertex(vertex: dict) -> dict:
    return {"id": str(vertex["v_id"]), **vertex.get("attributes", {})}


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


class TigerGraphDatasetQueries(DatasetQueries):
    source = "graph"
    reference_prefix = "query"

    def __init__(self, trigger_index: Path, graph: HHGOATigerGraph):
        super().__init__(trigger_index)
        self.graph = graph

    def _query(self, name: str, params: dict) -> list[dict]:
        self.calls += 1
        return self.graph.query(name, params)

    @staticmethod
    def _tx(vertex: dict) -> dict:
        row = _vertex(vertex)
        return {
            "id": row["id"], "customer_id": row.get("customer_id"), "ts": row.get("ts"),
            "amount": float(row.get("amount") or 0), "product": row.get("product"),
            "channel": row.get("channel"), "risk": float(row.get("risk") or 0),
            "card1": row.get("card1"), "card2": row.get("card2"),
            "card3": row.get("card3"), "card4": row.get("card4"),
            "card5": row.get("card5"), "card6": row.get("card6"),
            "addr1": row.get("billing_region"), "addr2": row.get("billing_country"),
            "email": row.get("purchaser_email"), "recipient_email": row.get("recipient_email"),
            "identity_status": row.get("identity_status"), "proxy_status": row.get("proxy_status"),
            "match_status": row.get("match_status"), "device_type": row.get("device_type"),
            "device_profile_id": row.get("device_profile_id"),
            "device_info": None, "os": None, "browser": None, "screen": None,
        }

    def transaction(self, transaction_id: str) -> dict:
        results = self._query("hh_transaction_context", {"tx": transaction_id, "max_results": 1})
        seeds = _items(results, "transaction")
        if not seeds:
            raise LookupError(f"Unknown TigerGraph transaction {transaction_id}")
        row = self._tx(seeds[0])
        device = _items(results, "device")
        if device:
            attrs = device[0].get("attributes", {})
            for key in ("device_info", "os", "browser", "screen"):
                row[key] = attrs.get(key)
        return row

    def _window(self, customer: str, start: str, end: str, limit: int) -> list[dict]:
        results = self._query("hh_customer_window", {
            "customer": customer, "start_ts": start, "end_ts": end,
            "max_results": min(limit, 10000),
        })
        return [self._tx(vertex) for vertex in _items(results, "window")]

    def history_stats(self, customer_id: str, before: str, region: str | None) -> dict:
        start = _timestamp(datetime.fromisoformat(before) - timedelta(days=30))
        history = [row for row in self._window(customer_id, start, before, 10000) if row["ts"] < before]
        amounts = [row["amount"] for row in history]
        return {"count": len(history), "median_amount": median(amounts) if amounts else None,
                "region_count": sum(row["addr1"] == region for row in history),
                "distinct_regions": len({row["addr1"] for row in history if row["addr1"]})}

    def customer_window(self, customer_id: str, start: str, end: str, hours: int = 48,
                        limit: int = 200) -> list[dict]:
        lower = _timestamp(datetime.fromisoformat(start) - timedelta(hours=hours))
        return self._window(customer_id, lower, end, limit)

    def profile_peers(self, seed: dict, end: str, days: int = 7,
                      limit: int = 120) -> list[dict]:
        if sum(bool(seed.get(key)) for key in ("device_info", "os", "browser", "screen")) < 2:
            return []
        profile = seed.get("device_profile_id") or device_profile_id(seed)
        lower = _timestamp(datetime.fromisoformat(end) - timedelta(days=days))
        results = self._query("hh_profile_neighbors", {
            "profile": profile, "start_ts": lower, "end_ts": end,
            "max_results": min(limit + 1, 200),
        })
        peers = [self._tx(vertex) for vertex in _items(results, "peers")]
        for row in peers:
            for key in ("device_info", "os", "browser", "screen"):
                row[key] = seed.get(key)
        return [row for row in peers if row["id"] != seed["id"]][:limit]

    def prior_cases(self, customer_id: str, before: str, limit: int = 6) -> list[dict]:
        results = self._query("hh_prior_cases", {
            "customer": customer_id, "before_ts": before, "max_results": min(limit, 30),
        })
        return [{"case_id": row["id"], "customer_id": row.get("customer_id"),
                 "card_id": row.get("card_id"), "closed_at": row.get("closed_at"),
                 "outcome": row.get("outcome"), "pattern": row.get("pattern"),
                 "txn_ids": "", "exposure_usd": row.get("exposure")}
                for row in map(_vertex, _items(results, "past"))]

    def known_cards(self, customer_ids: list[str], before: str) -> list[dict]:
        found = set()
        for customer in customer_ids[:120]:
            for row in self.prior_cases(customer, before, limit=30):
                if row["card_id"]:
                    found.add((customer, row["card_id"]))
        return [{"customer_id": customer, "card_id": card}
                for customer, card in sorted(found)]

"""Read-only index over the supplied files for reproducible offline analysis.

The index is not a replacement for the TigerGraph production graph. It exists to
develop and inspect benchmark logic when graph credentials are unavailable.
"""

from pathlib import Path

import duckdb


class DatasetQueries:
    source = "external"
    reference_prefix = "index"

    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Build the HHGOA index first: {path}")
        self.connection = duckdb.connect(str(path), read_only=True)
        self.calls = 0

    def _rows(self, sql: str, params: list | None = None) -> list[dict]:
        self.calls += 1
        cursor = self.connection.execute(sql, params or [])
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def triggers(self) -> list[dict]:
        return self._rows("SELECT * FROM case_pack ORDER BY case_id")

    def trigger(self, case_id: str) -> dict:
        rows = self._rows("SELECT * FROM case_pack WHERE case_id=?", [case_id])
        if len(rows) != 1:
            raise LookupError(f"Unknown benchmark case {case_id}")
        return rows[0]

    def transaction(self, transaction_id: str) -> dict:
        rows = self._rows(
            """SELECT t.*, i.identity_status, i.proxy_status, i.os, i.browser,
                      i.screen, i.device_info
               FROM tx t LEFT JOIN identity i ON t.id=i.id WHERE t.id=?""",
            [transaction_id],
        )
        if len(rows) != 1:
            raise LookupError(f"Unknown transaction {transaction_id}")
        return rows[0]

    def history_stats(self, customer_id: str, before: str, region: str | None) -> dict:
        return self._rows(
            """SELECT count(*) AS count, median(amount) AS median_amount,
                      sum(CASE WHEN addr1 IS NOT DISTINCT FROM ? THEN 1 ELSE 0 END)
                          AS region_count,
                      count(DISTINCT addr1) AS distinct_regions
               FROM tx WHERE customer_id=? AND ts<?
                 AND cast(ts AS timestamp)>=cast(? AS timestamp)-interval '30 days'""",
            [region, customer_id, before, before],
        )[0]

    def customer_window(self, customer_id: str, start: str, end: str, hours: int = 48,
                        limit: int = 200) -> list[dict]:
        return self._rows(
            """SELECT t.*, i.identity_status, i.proxy_status, i.os, i.browser,
                      i.screen, i.device_info
               FROM tx t LEFT JOIN identity i ON t.id=i.id
               WHERE t.customer_id=? AND t.ts<=?
                 AND cast(t.ts AS timestamp)>=cast(? AS timestamp)-(? * interval '1 hour')
               ORDER BY t.ts DESC LIMIT ?""",
            [customer_id, end, start, hours, limit],
        )

    def profile_peers(self, seed: dict, end: str, days: int = 7,
                      limit: int = 120) -> list[dict]:
        fields = ("device_info", "os", "browser", "screen")
        if sum(bool(seed.get(field)) for field in fields) < 2:
            return []
        return self._rows(
            """SELECT t.id, t.customer_id, t.ts, t.amount, t.product, t.risk,
                      t.email, t.recipient_email, t.channel, i.identity_status,
                      i.proxy_status, i.device_info, i.os, i.browser, i.screen
               FROM identity i JOIN tx t ON t.id=i.id
               WHERE i.device_info IS NOT DISTINCT FROM ?
                 AND i.os IS NOT DISTINCT FROM ?
                 AND i.browser IS NOT DISTINCT FROM ?
                 AND i.screen IS NOT DISTINCT FROM ?
                 AND t.id<>? AND t.ts<=?
                 AND cast(t.ts AS timestamp)>=cast(? AS timestamp)-(? * interval '1 day')
               ORDER BY t.ts DESC LIMIT ?""",
            [*(seed.get(field) for field in fields), seed["id"], end, end, days, limit],
        )

    def prior_cases(self, customer_id: str, before: str, limit: int = 6) -> list[dict]:
        return self._rows(
            """SELECT case_id, customer_id, card_id, closed_at, outcome,
                      pattern, txn_ids, exposure_usd
               FROM history WHERE customer_id=? AND closed_at<=?
               ORDER BY closed_at DESC LIMIT ?""",
            [customer_id, before, limit],
        )

    def known_cards(self, customer_ids: list[str], before: str) -> list[dict]:
        if not customer_ids:
            return []
        return self._rows(
            """SELECT DISTINCT customer_id, card_id FROM history
               WHERE customer_id IN (SELECT unnest(?)) AND closed_at<=?
               ORDER BY customer_id, card_id""",
            [customer_ids[:120], before],
        )

    def entity_exists(self, entity_id: str) -> bool:
        if entity_id.startswith("HHG-"):
            return bool(self._rows("SELECT 1 FROM case_pack WHERE case_id=?", [entity_id]))
        if entity_id.startswith("CC-"):
            return bool(self._rows("SELECT 1 FROM history WHERE case_id=?", [entity_id]))
        if entity_id.startswith("C"):
            customer = entity_id.split("-K", 1)[0]
            return bool(self._rows("SELECT 1 FROM tx WHERE customer_id=? LIMIT 1", [customer]))
        return bool(self._rows("SELECT 1 FROM tx WHERE id=?", [entity_id]))

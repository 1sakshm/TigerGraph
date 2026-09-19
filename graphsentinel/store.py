import sqlite3
from pathlib import Path

from graphsentinel.models import CaseRecord


class CaseStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, case: CaseRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO cases(id, updated_at, body) VALUES(?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, body=excluded.body",
                (case.id, case.updated_at.isoformat(), case.model_dump_json()),
            )

    def get(self, case_id: str) -> CaseRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT body FROM cases WHERE id = ?", (case_id,)).fetchone()
        return CaseRecord.model_validate_json(row[0]) if row else None

    def list(self) -> list[CaseRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT body FROM cases ORDER BY updated_at DESC").fetchall()
        return [CaseRecord.model_validate_json(row[0]) for row in rows]

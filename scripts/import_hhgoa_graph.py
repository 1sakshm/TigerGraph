"""Idempotently import the supplied HHGOA files into the HHGOA TigerGraph schema.

Install graph/hhgoa_schema.gsql and graph/hhgoa_queries.gsql first. Credentials
come only from environment variables; --dry-run permits payload inspection.
"""

import argparse
import os
from pathlib import Path

import duckdb

from graphsentinel.hhgoa.tigergraph import GraphPayload, HHGOATigerGraph


ROOT = Path(__file__).resolve().parents[1]


def batches(connection, sql: str, size: int, limit: int | None):
    cursor = connection.execute(sql)
    names = [field[0] for field in cursor.description]
    remaining = limit
    while True:
        count = size if remaining is None else min(size, remaining)
        if count <= 0:
            break
        rows = cursor.fetchmany(count)
        if not rows:
            break
        yield [dict(zip(names, row)) for row in rows]
        if remaining is not None:
            remaining -= len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=ROOT / "data/private/analysis.duckdb")
    parser.add_argument("--phase", choices=["all", "tx", "identity", "history", "anchors"], default="all")
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 1000:
        raise ValueError("batch size must be 1–1000")
    if args.limit is not None and args.limit < 1:
        raise ValueError("limit must be positive")
    connection = duckdb.connect(str(args.index), read_only=True)
    graph = None
    if not args.dry_run:
        graph = HHGOATigerGraph(
            os.environ["TIGERGRAPH_URL"], os.environ["TIGERGRAPH_TOKEN"],
            os.environ.get("TIGERGRAPH_GRAPH", "HHGOA"),
        )
    phases = [args.phase] if args.phase != "all" else ["tx", "identity", "history", "anchors"]
    sources = {
        "tx": ("SELECT * FROM tx ORDER BY id", GraphPayload.add_transaction),
        "identity": ("SELECT * FROM identity ORDER BY id", GraphPayload.add_identity),
        "history": ("SELECT * FROM history ORDER BY case_id", GraphPayload.add_closed_case),
        "anchors": ("SELECT * FROM case_pack ORDER BY case_id", GraphPayload.add_anchor),
    }
    for phase in phases:
        sql, add = sources[phase]
        total = 0
        for rows in batches(connection, sql, args.batch_size, args.limit):
            payload = GraphPayload()
            for row in rows:
                add(payload, row)
            if graph:
                result = graph.upsert(payload)
                stats = result.get("results", [{}])[0]
                if (stats.get("accepted_vertices", 0) < payload.vertex_count() or
                        stats.get("accepted_edges", 0) < payload.edge_count()):
                    raise RuntimeError(f"Incomplete {phase} batch: {stats}")
            total += len(rows)
            if total % 10000 < args.batch_size:
                print(f"{phase}: {total} source rows")
        print(f"{phase}: {total} source rows {'validated' if args.dry_run else 'upserted'}")


if __name__ == "__main__":
    main()

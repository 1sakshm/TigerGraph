"""Build a disposable local index of the supplied HHGOA CSVs for inspection.

This index is development tooling. Production investigation uses TigerGraph.
The output lives under data/private and must never be committed.
"""

from pathlib import Path
import time

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "private"


def main() -> None:
    started = time.perf_counter()
    connection = duckdb.connect(str(DATA / "analysis.duckdb"))
    connection.execute(
        """
        CREATE OR REPLACE TABLE tx AS
        SELECT TransactionID AS id, customer_id, ts,
               TRY_CAST(TransactionAmt AS DOUBLE) AS amount,
               ProductCD AS product, card1, card2, card3, card4, card5, card6,
               addr1, addr2, P_emaildomain AS email,
               R_emaildomain AS recipient_email, channel,
               TRY_CAST(risk_score AS DOUBLE) AS risk
        FROM read_csv(?, all_varchar=true, auto_detect=true)
        """,
        [str(DATA / "transactions.csv")],
    )
    connection.execute(
        """
        CREATE OR REPLACE TABLE identity AS
        SELECT TransactionID AS id, id_15 AS identity_status,
               id_23 AS proxy_status, id_30 AS os, id_31 AS browser,
               id_33 AS screen, DeviceInfo AS device_info
        FROM read_csv(?, all_varchar=true, auto_detect=true)
        """,
        [str(DATA / "identity.csv")],
    )
    connection.execute(
        """
        CREATE OR REPLACE TABLE history AS
        SELECT * FROM read_csv(?, all_varchar=true, auto_detect=true)
        """,
        [str(DATA / "closed_cases_history.csv")],
    )
    connection.execute(
        """
        CREATE OR REPLACE TABLE case_pack AS
        SELECT * FROM read_csv(?, all_varchar=true, auto_detect=true)
        """,
        [str(DATA / "case_pack.csv")],
    )
    counts = connection.execute(
        "SELECT (SELECT count(*) FROM tx), (SELECT count(*) FROM identity), "
        "(SELECT count(*) FROM history), (SELECT count(*) FROM case_pack)"
    ).fetchone()
    if counts != (590742, 144432, 5565, 20):
        raise ValueError(f"Unexpected HHGOA file counts: {counts}")
    identity_missing = connection.execute(
        "SELECT count(*) FROM identity i LEFT JOIN tx t USING(id) WHERE t.id IS NULL"
    ).fetchone()[0]
    history_missing = connection.execute(
        """SELECT count(*) FROM
             (SELECT unnest(str_split(txn_ids, '|')) AS id FROM history) h
             LEFT JOIN tx t USING(id) WHERE t.id IS NULL"""
    ).fetchone()[0]
    anchors_missing = connection.execute(
        """SELECT count(*) FROM case_pack p LEFT JOIN tx t
             ON p.flagged_txn_id=t.id WHERE t.id IS NULL"""
    ).fetchone()[0]
    if identity_missing or history_missing or anchors_missing:
        raise ValueError(f"Broken references: identity={identity_missing}, "
                         f"history={history_missing}, anchors={anchors_missing}")
    print(f"transactions, identity, history, benchmark: {counts}")
    print("identity, historical case, and benchmark transaction references: verified")
    print(f"elapsed: {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()

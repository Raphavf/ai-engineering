"""
scripts/seed_oracle.py

Loads synthetic legacy records into the docker-compose Oracle container.
Requires: pip install .[oracle]
"""

from __future__ import annotations

import datetime
import os

import oracledb

from fiscal_recon.synthetic import generate

DSN = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")


def main() -> None:
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    dates = [yesterday - datetime.timedelta(days=i) for i in range(3)]
    legacy, _, _ = generate(dates, docs_per_day=100)

    with oracledb.connect(user="recon", password="recon_dev", dsn=DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM legacy_fiscal_documents")
            cur.executemany(
                "INSERT INTO legacy_fiscal_documents VALUES (:1, :2, :3, :4, :5, :6, :7)",
                [
                    (r.origin_branch, r.destination_branch, r.document_number, r.series,
                     r.issue_date, r.net_value, r.tax_value)
                    for r in legacy
                ],
            )
        conn.commit()
    print(f"Seeded {len(legacy)} records into Oracle.")


if __name__ == "__main__":
    main()

"""
synthetic.py

Generates realistic-looking but entirely fake fiscal documents for both
systems, with a known, seeded set of divergences. Nothing here comes from
a real company: branch codes, document numbers and values are random.

    fiscal-recon-seed --days 7 --out data/synthetic.db

The returned GroundTruth lists exactly which documents were made missing
or divergent, so tests (and, later, agent evals) can check answers
against it.
"""

from __future__ import annotations

import argparse
import datetime
import random
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from fiscal_recon.models import FiscalRecord

BRANCHES = [f"B{n:03d}" for n in range(1, 13)]
SERIES = ["1", "2", "890"]

_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    origin_branch      TEXT NOT NULL,
    destination_branch TEXT NOT NULL,
    document_number    TEXT NOT NULL,
    series             TEXT NOT NULL,
    issue_date         TEXT NOT NULL,
    net_value          REAL NOT NULL,
    tax_value          REAL NOT NULL,
    PRIMARY KEY (origin_branch, destination_branch, document_number, series)
);
CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(issue_date);
"""


@dataclass
class GroundTruth:
    missing_in_erp: set[tuple] = field(default_factory=set)
    value_divergent: set[tuple] = field(default_factory=set)


def _key(r: FiscalRecord) -> tuple:
    return (r.origin_branch, r.destination_branch, r.document_number, r.series)


def generate(
    dates: list[datetime.date],
    docs_per_day: int = 200,
    missing_rate: float = 0.03,
    divergent_rate: float = 0.04,
    seed: int = 42,
) -> tuple[list[FiscalRecord], list[FiscalRecord], GroundTruth]:
    rng = random.Random(seed)
    legacy: list[FiscalRecord] = []
    erp: list[FiscalRecord] = []
    truth = GroundTruth()
    doc_counter = rng.randint(100_000, 900_000)

    for date in dates:
        for _ in range(docs_per_day):
            doc_counter += 1
            origin, destination = rng.sample(BRANCHES, 2)
            net = round(rng.uniform(50, 25_000), 2)
            record = FiscalRecord(
                origin_branch=origin,
                destination_branch=destination,
                document_number=str(doc_counter),
                series=rng.choice(SERIES),
                issue_date=date,
                net_value=net,
                tax_value=round(net * rng.choice([0.07, 0.12, 0.18]), 2),
            )
            legacy.append(record)

            roll = rng.random()
            if roll < missing_rate:
                truth.missing_in_erp.add(_key(record))
                continue
            if roll < missing_rate + divergent_rate:
                truth.value_divergent.add(_key(record))
                # Mix of realistic error shapes: rounding drift, wrong tax rate, typo'd value
                kind = rng.choice(["cents", "tax", "net"])
                if kind == "cents":
                    record = record.model_copy(update={"net_value": round(record.net_value + 0.01, 2)})
                elif kind == "tax":
                    record = record.model_copy(update={"tax_value": round(record.net_value * 0.04, 2)})
                else:
                    record = record.model_copy(update={"net_value": round(record.net_value * 10, 2)})
            erp.append(record)

    return legacy, erp, truth


def write_sqlite(path: Path, legacy: list[FiscalRecord], erp: list[FiscalRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for table, records in (("legacy_fiscal_documents", legacy), ("erp_fiscal_documents", erp)):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.executescript(_DDL.format(table=table))
            conn.executemany(
                f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (r.origin_branch, r.destination_branch, r.document_number, r.series,
                     r.issue_date.isoformat(), r.net_value, r.tax_value)
                    for r in records
                ],
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a SQLite DB with synthetic fiscal documents.")
    parser.add_argument("--days", type=int, default=7, help="days back from yesterday")
    parser.add_argument("--docs-per-day", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic.db"))
    args = parser.parse_args()

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    dates = [yesterday - datetime.timedelta(days=i) for i in range(args.days)]
    legacy, erp, truth = generate(dates, args.docs_per_day, seed=args.seed)
    write_sqlite(args.out, legacy, erp)
    print(
        f"Wrote {len(legacy)} legacy / {len(erp)} ERP records to {args.out} "
        f"({len(truth.missing_in_erp)} missing, {len(truth.value_divergent)} divergent) "
        f"for {dates[-1]} .. {dates[0]}"
    )


if __name__ == "__main__":
    main()

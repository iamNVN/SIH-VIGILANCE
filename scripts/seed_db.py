"""
seed_db.py -- loads the generator's CSVs (data/output/*.csv) into the
database defined by DATABASE_URL (Blueprint Section 5, Day 1 "Seed script
loads CSVs into Postgres"; runs against SQLite today, Postgres unchanged
once Docker is available -- see backend/app/core/config.py).

Run:
    python scripts/seed_db.py
    python scripts/seed_db.py --data-dir data/output --reset
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

BACKEND_APP = Path(__file__).resolve().parent.parent / "backend" / "app"
sys.path.insert(0, str(BACKEND_APP))

from core.db import Base, SessionLocal, engine  # noqa: E402
from models.orm import (  # noqa: E402
    Account,
    Complaint,
    FraudRing,
    Transaction,
    Victim,
    WithdrawalEvent,
    WithdrawalPoint,
)


def to_dt(series):
    import numpy as np
    return np.array(pd.to_datetime(series, format="%Y-%m-%dT%H:%M:%S").dt.to_pydatetime())


def none_if_nan(value):
    return None if pd.isna(value) else value


HOLDBACK_PER_CITY = 15


def compute_holdback_ids(complaints: pd.DataFrame, victims: pd.DataFrame) -> set:
    """The most-recent-by-filed_at HOLDBACK_PER_CITY complaints IN EACH
    CITY, held back as 'not yet arrived' for /stream/trigger-next to
    reveal. Per-city (not one global holdback) so ANY investigator's
    Simulate Complaint has something in their own jurisdiction to reveal,
    not just whichever city the globally-next complaint happens to be in."""
    merged = complaints.merge(victims[["id", "city"]], left_on="victim_id", right_on="id", suffixes=("", "_victim"))
    holdback_ids = set()
    for _city, group in merged.groupby("city"):
        newest = group.sort_values("filed_at", ascending=False).head(HOLDBACK_PER_CITY)
        holdback_ids.update(newest["id"].tolist())
    return holdback_ids


def seed(data_dir: Path, reset: bool):
    if reset:
        print("Dropping and recreating all tables...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Victim).first() is not None and not reset:
            print("Database already seeded (victims table non-empty). Use --reset to reseed.")
            return

        print("Loading CSVs...")
        victims = pd.read_csv(data_dir / "victims.csv")
        accounts = pd.read_csv(data_dir / "accounts.csv")
        complaints = pd.read_csv(data_dir / "complaints.csv")
        transactions = pd.read_csv(data_dir / "transactions.csv")
        withdrawal_points = pd.read_csv(data_dir / "withdrawal_points.csv")
        withdrawal_events = pd.read_csv(data_dir / "withdrawal_events.csv")
        fraud_rings = pd.read_csv(data_dir / "fraud_rings.csv")

        print("Inserting victims...")
        db.bulk_save_objects([
            Victim(id=r.id, name_fake=r.name_fake, city=r.city, state=r.state, phone_fake=str(r.phone_fake))
            for r in victims.itertuples()
        ])

        print("Inserting accounts...")
        db.bulk_save_objects([
            Account(
                id=r.id, account_number_fake=str(r.account_number_fake), holder_name_fake=r.holder_name_fake,
                bank_name=r.bank_name, account_type=r.account_type, ifsc_code=r.ifsc_code, opened_at=r.opened_at,
            )
            for r in accounts.itertuples()
        ])

        print("Inserting withdrawal points...")
        db.bulk_save_objects([
            WithdrawalPoint(id=r.id, name=r.name, type=r.type, lat=r.lat, lon=r.lon, city=r.city, bank_name=r.bank_name)
            for r in withdrawal_points.itertuples()
        ])

        db.commit()

        print("Inserting complaints...")
        holdback_ids = compute_holdback_ids(complaints, victims)
        complaints["filed_at"] = to_dt(complaints["filed_at"])
        db.bulk_save_objects([
            Complaint(
                id=r.id, victim_id=r.victim_id, filed_at=r.filed_at, amount_lost=r.amount_lost,
                narrative_text=r.narrative_text, bank_name=r.bank_name, status=r.status,
                revealed=r.id not in holdback_ids,
            )
            for r in complaints.itertuples()
        ])
        db.commit()
        print(f"  {len(holdback_ids)} complaints held back as 'not yet arrived' ({HOLDBACK_PER_CITY}/city) for Simulate Complaint")

        print("Inserting transactions...")
        transactions["timestamp"] = to_dt(transactions["timestamp"])
        db.bulk_save_objects([
            Transaction(
                id=r.id, from_account_id=r.from_account_id, to_account_id=r.to_account_id, amount=r.amount,
                timestamp=r.timestamp, complaint_id=none_if_nan(r.complaint_id),
                hop_index=none_if_nan(r.hop_index),
            )
            for r in transactions.itertuples()
        ])

        print("Inserting withdrawal events...")
        withdrawal_events["timestamp"] = to_dt(withdrawal_events["timestamp"])
        db.bulk_save_objects([
            WithdrawalEvent(
                id=r.id, account_id=r.account_id, withdrawal_point_id=r.withdrawal_point_id, amount=r.amount,
                timestamp=r.timestamp, ring_id=none_if_nan(r.ring_id), complaint_id=none_if_nan(r.complaint_id),
            )
            for r in withdrawal_events.itertuples()
        ])

        print("Inserting fraud rings (ground truth, evaluation-only)...")
        db.bulk_save_objects([
            FraudRing(
                id=r.id, name=r.name, city_cluster=r.city_cluster, typical_hops=r.typical_hops,
                typical_delay_hours_min=r.typical_delay_hours_min, typical_delay_hours_max=r.typical_delay_hours_max,
                mule_account_ids=r.mule_account_ids, withdrawal_point_ids=r.withdrawal_point_ids,
                hot_withdrawal_point_ids=r.hot_withdrawal_point_ids,
            )
            for r in fraud_rings.itertuples()
        ])

        db.commit()
        print("Seed complete.")
        print(f"  victims={db.query(Victim).count()} accounts={db.query(Account).count()} "
              f"complaints={db.query(Complaint).count()} transactions={db.query(Transaction).count()} "
              f"withdrawal_points={db.query(WithdrawalPoint).count()} withdrawal_events={db.query(WithdrawalEvent).count()} "
              f"fraud_rings={db.query(FraudRing).count()}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data" / "output"))
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed(Path(args.data_dir), reset=args.reset)


if __name__ == "__main__":
    main()

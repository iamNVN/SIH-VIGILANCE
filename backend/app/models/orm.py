"""
orm.py -- SQLAlchemy ORM models, directly mirroring Blueprint Section 6's
schema. Column types are plain/portable (Integer, String, Float, DateTime,
Boolean) so this runs unchanged against SQLite (today, see core/config.py's
note) or Postgres (via docker-compose.yml, once Docker is available).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Victim(Base):
    __tablename__ = "victims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_fake: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    phone_fake: Mapped[str] = mapped_column(String(20))

    complaints: Mapped[list["Complaint"]] = relationship(back_populates="victim")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    victim_id: Mapped[int] = mapped_column(ForeignKey("victims.id"))
    filed_at: Mapped[datetime] = mapped_column(DateTime)
    amount_lost: Mapped[float] = mapped_column(Float)
    narrative_text: Mapped[str] = mapped_column(Text)
    bank_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="open")
    # Live-replay gate (core/replay_state.py) -- False means "not arrived
    # yet" on Command Center's live-feed view (stats/feed/alerts/hotspots),
    # though still reachable via Cases/direct link, which are deliberately
    # the ungated full archive. seed_db.py sets this False for a per-city
    # holdback so /stream/trigger-next has something real to reveal for
    # ANY investigator's city, not just whichever city the global next-by-
    # date complaint happens to be in.
    revealed: Mapped[bool] = mapped_column(Boolean, default=True)

    victim: Mapped["Victim"] = relationship(back_populates="complaints")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="complaint")
    withdrawal_events: Mapped[list["WithdrawalEvent"]] = relationship(back_populates="complaint")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="complaint")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_number_fake: Mapped[str] = mapped_column(String(30))
    holder_name_fake: Mapped[str] = mapped_column(String(200))
    bank_name: Mapped[str] = mapped_column(String(100))
    account_type: Mapped[str] = mapped_column(String(20))  # victim | mule | normal -- GENERATOR-SIDE ONLY, never a model feature
    ifsc_code: Mapped[str] = mapped_column(String(20))
    opened_at: Mapped[str] = mapped_column(String(20))  # date, kept as string to match generator's .date().isoformat()


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    to_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    complaint_id: Mapped[int | None] = mapped_column(ForeignKey("complaints.id"), nullable=True)
    hop_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    complaint: Mapped["Complaint | None"] = relationship(back_populates="transactions")


class WithdrawalPoint(Base):
    __tablename__ = "withdrawal_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))  # ATM | Branch
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    city: Mapped[str] = mapped_column(String(100))
    bank_name: Mapped[str] = mapped_column(String(100))


class WithdrawalEvent(Base):
    __tablename__ = "withdrawal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    withdrawal_point_id: Mapped[int] = mapped_column(ForeignKey("withdrawal_points.id"))
    amount: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    ring_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # GENERATOR-SIDE GROUND TRUTH ONLY -- never a model feature
    complaint_id: Mapped[int | None] = mapped_column(ForeignKey("complaints.id"), nullable=True)

    complaint: Mapped["Complaint | None"] = relationship(back_populates="withdrawal_events")


class FraudRing(Base):
    """Generator-only ground truth, used solely for offline evaluation
    (Blueprint Section 6/18). Never queried by the live prediction path."""

    __tablename__ = "fraud_rings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    city_cluster: Mapped[str] = mapped_column(String(100))
    typical_hops: Mapped[int] = mapped_column(Integer)
    typical_delay_hours_min: Mapped[float] = mapped_column(Float)
    typical_delay_hours_max: Mapped[float] = mapped_column(Float)
    mule_account_ids: Mapped[str] = mapped_column(Text)
    withdrawal_point_ids: Mapped[str] = mapped_column(Text)
    hot_withdrawal_point_ids: Mapped[str] = mapped_column(Text)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"))
    withdrawal_point_id: Mapped[int] = mapped_column(ForeignKey("withdrawal_points.id"))
    rank: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    complaint: Mapped["Complaint"] = relationship(back_populates="predictions")


class InvestigatorFeedback(Base):
    """10 Sep+ active-learning stretch (Blueprint Section 15/23) -- table
    exists now so the feedback loop has somewhere to write to later."""

    __tablename__ = "investigator_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    correct_bool: Mapped[bool] = mapped_column(Boolean)
    investigator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

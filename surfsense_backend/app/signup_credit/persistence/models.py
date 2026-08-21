"""``signup_credit_claims`` table."""

from __future__ import annotations

from sqlalchemy import Column, String, UniqueConstraint

from app.db import BaseModel, TimestampMixin


class SignupCreditClaim(BaseModel, TimestampMixin):
    """An identity that has already taken the signup credit."""

    __tablename__ = "signup_credit_claims"
    __table_args__ = (
        UniqueConstraint(
            "identity_kind",
            "identity_fingerprint",
            name="uq_signup_credit_claims_identity",
        ),
    )

    # No foreign key to "user": the row must outlive the account that made it.
    identity_kind = Column(String, nullable=False)
    identity_fingerprint = Column(String(64), nullable=False)

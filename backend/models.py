"""
models.py
---------
This file defines our database tables using SQLAlchemy ORM models.

Each class below becomes an actual table in the SQLite database:
- Animal        -> stores registered livestock details
- Claim         -> stores insurance/ownership claims made for an animal
- Verification  -> stores the history of ML verification attempts (mocked for now)
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Animal(Base):
    """Represents a registered animal (e.g. a cow) in the system."""

    __tablename__ = "animals"

    id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(String, unique=True, index=True, nullable=False)  # e.g. "COW-1182"
    owner_name = Column(String, nullable=False)
    breed = Column(String, nullable=True)
    ear_tag = Column(String, nullable=True)
    registration_date = Column(DateTime, default=datetime.utcnow)

    # This lets us do animal.claims and animal.verifications in Python
    claims = relationship("Claim", back_populates="animal")
    verifications = relationship("Verification", back_populates="animal")


class Claim(Base):
    """Represents a claim (e.g. insurance claim) filed for an animal."""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(String, ForeignKey("animals.animal_id"), nullable=False)
    claim_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="PENDING")  # e.g. PENDING, APPROVED, REJECTED

    animal = relationship("Animal", back_populates="claims")


class Verification(Base):
    """Represents one biometric verification attempt for an animal (currently mocked)."""

    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(String, ForeignKey("animals.animal_id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    verdict = Column(String, nullable=False)  # e.g. MATCH, NO_MATCH
    created_at = Column(DateTime, default=datetime.utcnow)

    animal = relationship("Animal", back_populates="verifications")

"""
schemas.py
----------
This file defines Pydantic schemas.

Schemas control:
- What data the API expects to RECEIVE (request bodies)
- What data the API will SEND BACK (response bodies)

They are different from models.py (which defines the actual DB tables).
Schemas are about "shape of data over the API", models are about "shape of data in the DB".
"""

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


# ---------- Animal Schemas ----------

class AnimalCreate(BaseModel):
    """Data required to register a new animal."""
    animal_id: str
    owner_name: str
    breed: Optional[str] = None
    ear_tag: Optional[str] = None


class AnimalResponse(BaseModel):
    """Data returned when reading animal details."""
    id: int
    animal_id: str
    owner_name: str
    breed: Optional[str] = None
    ear_tag: Optional[str] = None
    registration_date: datetime

    class Config:
        # Allows Pydantic to read data directly from SQLAlchemy model objects
        from_attributes = True


# ---------- Claim Schemas ----------

class ClaimCreate(BaseModel):
    """Data required to create a new claim."""
    animal_id: str


class ClaimResponse(BaseModel):
    """Data returned when reading claim details."""
    id: int
    animal_id: str
    claim_date: datetime
    status: str

    class Config:
        from_attributes = True


# ---------- Verification Schemas ----------

class VerificationRequest(BaseModel):
    """Data required to request a verification (image upload will be added later)."""
    animal_id: str


class MatchResult(BaseModel):
    """A single candidate match returned by the (mock) ML model."""
    animal_id: str
    score: float


class VerificationResponse(BaseModel):
    """The result returned by POST /verify (mocked ML output for now)."""
    animal_id: str
    matches: List[MatchResult]
    verdict: str


class VerificationHistoryItem(BaseModel):
    """A single row of verification history, as stored in the DB."""
    id: int
    animal_id: str
    similarity_score: float
    verdict: str
    created_at: datetime

    class Config:
        from_attributes = True

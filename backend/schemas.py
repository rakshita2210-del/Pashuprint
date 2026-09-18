"""
schemas.py
----------
Pydantic schemas describing the shape of data going in/out of the API.

These describe the HTTP request/response bodies. The actual database
columns live in db.py -- these schemas are kept in sync with that schema
by hand, since we're not using an ORM to generate them automatically.
"""

from pydantic import BaseModel
from typing import Optional, List


# ---------- Animal ----------

class AnimalResponse(BaseModel):
    """Shape of an animal record as returned by the API."""
    cow_id: str
    breed: Optional[str] = None
    age: Optional[int] = None
    owner_name: str
    policy_id: Optional[str] = None
    registration_date: str
    muzzle_photo_path: Optional[str] = None
    status: str


class RegisterResponse(BaseModel):
    """
    Shape returned by POST /register.

    Includes the auto-generated cow_id directly at the top level (so a
    caller doesn't have to dig into `animal` just to find the id that was
    assigned), plus the full animal record for anything else the caller
    needs.
    """
    success: bool
    cow_id: str
    message: str
    animal: AnimalResponse


# ---------- Verification ----------

class VerificationResponse(BaseModel):
    """Shape returned by POST /verify and used inside register/claim responses."""
    cow_id: str
    top_match_cow_id: Optional[str] = None
    similarity_score: Optional[float] = None
    result_status: str


class VerificationHistoryItem(BaseModel):
    """One row of verification history, as returned by GET /verification/{cow_id}."""
    id: int
    cow_id: str
    verification_type: str
    photo_path: Optional[str] = None
    top_match_cow_id: Optional[str] = None
    similarity_score: Optional[float] = None
    result_status: str
    timestamp: str


# ---------- Claim ----------

class ClaimResponse(BaseModel):
    """Shape returned by POST /claim."""
    cow_id: str
    status: str
    verification: VerificationResponse


# ---------- Fraud flags ----------

class FraudFlagResponse(BaseModel):
    """One row from the fraud_flags table."""
    id: int
    cow_id: str
    flag_type: str
    details: Optional[str] = None
    created_at: str

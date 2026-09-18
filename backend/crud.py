"""
crud.py
-------
CRUD = Create, Read, Update, Delete.

This file contains helper functions that talk directly to the database.
Keeping this logic separate from routers/ keeps our API route files clean
and focused on handling HTTP requests/responses.
"""

from sqlalchemy.orm import Session
import random

import models
import schemas


# ---------- Animal CRUD ----------

def get_animal(db: Session, animal_id: str):
    """Fetch a single animal by its animal_id (e.g. 'COW-1182')."""
    return db.query(models.Animal).filter(models.Animal.animal_id == animal_id).first()


def create_animal(db: Session, animal: schemas.AnimalCreate):
    """Create and save a new animal record."""
    db_animal = models.Animal(
        animal_id=animal.animal_id,
        owner_name=animal.owner_name,
        breed=animal.breed,
        ear_tag=animal.ear_tag,
    )
    db.add(db_animal)
    db.commit()
    db.refresh(db_animal)  # refresh so we get the auto-generated id/date back
    return db_animal


# ---------- Claim CRUD ----------

def create_claim(db: Session, claim: schemas.ClaimCreate):
    """Create and save a new claim for an existing animal."""
    db_claim = models.Claim(
        animal_id=claim.animal_id,
        status="PENDING",
    )
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim


# ---------- Verification CRUD ----------

def create_mock_verification(db: Session, animal_id: str):
    """
    Generate a MOCK verification result and save it to the database.

    NOTE: This does NOT run any real ML model yet. It just generates a
    random-ish similarity score and matches so the frontend/team can build
    against a realistic API shape. Replace this later with real ResNet50
    inference logic.
    """
    # Fake a realistic-looking similarity score for the "self" match
    self_score = round(random.uniform(0.85, 0.99), 2)

    # Fake one or two other lower-confidence "lookalike" matches
    other_matches = [
        {"animal_id": "COW-1045", "score": round(random.uniform(0.30, 0.60), 2)},
    ]

    verdict = "MATCH" if self_score >= 0.75 else "NO_MATCH"

    # Save the main result to the verification history table
    db_verification = models.Verification(
        animal_id=animal_id,
        similarity_score=self_score,
        verdict=verdict,
    )
    db.add(db_verification)
    db.commit()
    db.refresh(db_verification)

    # Build the full response, including the mock candidate matches
    matches = [{"animal_id": animal_id, "score": self_score}] + other_matches

    return {
        "animal_id": animal_id,
        "matches": matches,
        "verdict": verdict,
    }


def get_verification_history(db: Session, animal_id: str):
    """Fetch all past verification attempts for a given animal, newest first."""
    return (
        db.query(models.Verification)
        .filter(models.Verification.animal_id == animal_id)
        .order_by(models.Verification.created_at.desc())
        .all()
    )

"""
routers/verification.py
------------------------
Handles biometric verification requests.

IMPORTANT: The actual ML model (ResNet50-based muzzle/biometric matching)
is NOT implemented yet. POST /verify currently returns a MOCK result
generated in crud.create_mock_verification(). Swap that function's internals
out later for real model inference without needing to change this router.

Endpoints in this file:
- POST /verify                      -> run a (mock) verification for an animal
- GET  /verification/{animal_id}    -> get verification history for an animal
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import crud
import schemas
from database import get_db

router = APIRouter(tags=["Verification"])


@router.post("/verify", response_model=schemas.VerificationResponse)
def verify_animal(request: schemas.VerificationRequest, db: Session = Depends(get_db)):
    """
    Run a (currently mocked) biometric verification for the given animal_id.

    In the future, this endpoint will accept an uploaded image and run it
    through the ResNet50 model. For now, it just checks the animal exists
    and returns a fake similarity score + matches so the frontend can be
    built against the final API shape.
    """
    db_animal = crud.get_animal(db, request.animal_id)
    if db_animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Animal with animal_id '{request.animal_id}' not found.",
        )

    result = crud.create_mock_verification(db, request.animal_id)
    return result


@router.get("/verification/{animal_id}", response_model=List[schemas.VerificationHistoryItem])
def get_verification_history(animal_id: str, db: Session = Depends(get_db)):
    """Return the full verification history for a given animal, newest first."""
    db_animal = crud.get_animal(db, animal_id)
    if db_animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Animal with animal_id '{animal_id}' not found.",
        )

    return crud.get_verification_history(db, animal_id)

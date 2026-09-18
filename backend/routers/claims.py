"""
routers/claims.py
------------------
Handles creation of claims (e.g. insurance claims) tied to an animal.

Endpoints in this file:
- POST /claim -> create a new claim for an existing animal
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(tags=["Claims"])


@router.post("/claim", response_model=schemas.ClaimResponse)
def create_claim(claim: schemas.ClaimCreate, db: Session = Depends(get_db)):
    """
    Create a new claim for an animal.

    The animal must already be registered, otherwise we return a 404 error.
    """
    db_animal = crud.get_animal(db, claim.animal_id)
    if db_animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cannot create claim: animal with animal_id '{claim.animal_id}' not found.",
        )

    return crud.create_claim(db, claim)

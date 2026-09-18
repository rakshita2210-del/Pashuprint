"""
routers/registration.py
------------------------
Handles everything related to registering animals and looking up their details.

Endpoints in this file:
- POST /register          -> register a new animal
- GET  /animal/{animal_id} -> get details of a specific animal
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(tags=["Registration"])


@router.post("/register", response_model=schemas.AnimalResponse)
def register_animal(animal: schemas.AnimalCreate, db: Session = Depends(get_db)):
    """
    Register a new animal in the system.

    If an animal with the same animal_id already exists, we return an error
    instead of creating a duplicate.
    """
    existing_animal = crud.get_animal(db, animal.animal_id)
    if existing_animal:
        raise HTTPException(
            status_code=400,
            detail=f"Animal with animal_id '{animal.animal_id}' is already registered.",
        )

    return crud.create_animal(db, animal)


@router.get("/animal/{animal_id}", response_model=schemas.AnimalResponse)
def get_animal_details(animal_id: str, db: Session = Depends(get_db)):
    """Fetch details of a single registered animal by its animal_id."""
    db_animal = crud.get_animal(db, animal_id)
    if db_animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Animal with animal_id '{animal_id}' not found.",
        )
    return db_animal

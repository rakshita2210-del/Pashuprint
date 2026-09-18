"""
routers/claims.py
------------------
Handles insurance/ownership claims for an existing animal.

Per the project spec, there is NO separate "claims" table. A claim is
represented by flipping the existing animals.status field from 'active'
to 'claimed', and the identity check behind that claim is logged as a
normal row in the existing verifications table (verification_type="claim").

Endpoints in this file:
- POST /claim -> verify identity (mock) and mark an animal as claimed
"""

import os
import shutil

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

import db
import schemas
from services.mock_ml import mock_muzzle_verification

router = APIRouter(tags=["Claims"])

UPLOAD_DIR = "uploads/claim_photos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/claim", response_model=schemas.ClaimResponse)
def create_claim(cow_id: str = Form(...), photo: UploadFile = File(...)):
    """
    Create a claim for an existing animal.

    Steps:
    1. Animal must already be registered (404 if not).
    2. Animal must not already be claimed (400 if it is).
    3. Run the (mocked) muzzle verification to confirm the photo matches
       this cow_id before approving the claim.
    4. Log the verification (verification_type="claim").
    5. If the mock check is a MATCH, flip animals.status to 'claimed'.
       Otherwise, reject the claim.
    """
    animal = db.get_animal(cow_id)
    if animal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cannot create claim: animal with cow_id '{cow_id}' not found.",
        )

    if animal["status"] == "claimed":
        raise HTTPException(
            status_code=400,
            detail=f"Animal '{cow_id}' has already been claimed.",
        )

    ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
    photo_path = os.path.join(UPLOAD_DIR, f"{cow_id}_claim_{os.urandom(4).hex()}{ext}")
    with open(photo_path, "wb") as f:
        shutil.copyfileobj(photo.file, f)

    # MOCK identity check: pretend to verify the photo is really this cow_id.
    mock_result = mock_muzzle_verification(photo_path, [cow_id])

    verification = db.log_verification(
        cow_id=cow_id,
        verification_type="claim",
        result_status=mock_result["result_status"],
        photo_path=photo_path,
        top_match_cow_id=mock_result["top_match_cow_id"],
        similarity_score=mock_result["similarity_score"],
    )

    if mock_result["result_status"] != "MATCH":
        raise HTTPException(
            status_code=400,
            detail=(
                "Claim rejected: mock identity check did not confirm a match "
                f"(mock similarity {mock_result['similarity_score']}). This is a "
                "MOCK result, not a real biometric decision."
            ),
        )

    updated_animal = db.update_animal_status(cow_id, "claimed")

    return {
        "cow_id": cow_id,
        "status": updated_animal["status"],
        "verification": {
            "cow_id": cow_id,
            "top_match_cow_id": verification["top_match_cow_id"],
            "similarity_score": verification["similarity_score"],
            "result_status": verification["result_status"],
        },
    }

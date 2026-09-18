"""
routers/fraud.py
-----------------
Read-only endpoint for reviewing fraud flags.

Note: nothing in the current /register, /verify, or /claim flow creates a
fraud flag automatically yet (the spec doesn't define when one should be
raised). This endpoint just exposes db.get_all_fraud_flags() so flags
added directly via db.add_fraud_flag() (e.g. by a future admin tool, or
manually during a demo) can be reviewed.

Endpoints in this file:
- GET /fraud-flags -> list all fraud flags
"""

from typing import List

from fastapi import APIRouter

import db
import schemas

router = APIRouter(tags=["Fraud"])


@router.get("/fraud-flags", response_model=List[schemas.FraudFlagResponse])
def list_fraud_flags():
    """Return every fraud flag on record, newest first."""
    return db.get_all_fraud_flags()

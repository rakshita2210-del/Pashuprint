"""
services/mock_ml.py
--------------------
TEMPORARY MOCK MODULE. This is NOT a real machine learning model.

It stands in for the future ResNet50-based muzzle-recognition model,
which a teammate will build separately. Every number this module produces
is randomly generated -- it exists only so the rest of the system (API,
database, and eventually a frontend) can be built and tested end-to-end
before the real model exists.

The real integration will look like:

    FastAPI -> muzzle image -> ML / ResNet50 module -> embedding
            -> similarity search -> database

When the real model is ready, only the *internals* of the two functions
below need to change. Routers only ever call these two functions by name,
so nothing else in the app has to be rewritten.
"""

import random
from typing import Optional


def generate_mock_embedding(photo_path: str) -> list:
    """
    MOCK: pretend to turn a muzzle photo into a numeric embedding vector.

    Real version: load the image, run it through ResNet50, return the
    resulting feature vector (e.g. a 128- or 512-dim list of floats).

    This mock seeds the random generator from the photo path so the same
    "photo" always produces the same fake embedding, which keeps demo
    behavior consistent.
    """
    rng = random.Random(photo_path)
    return [round(rng.uniform(-1, 1), 4) for _ in range(128)]


def mock_muzzle_verification(
    photo_path: str, candidate_cow_ids: list, threshold: float = 0.75
) -> dict:
    """
    MOCK: pretend to compare a muzzle photo against known animals.

    Real version: embed the incoming photo, compute similarity (e.g.
    cosine similarity) against every stored embedding in the `embeddings`
    table, and return the best real match.

    This mock just picks a random candidate (if any exist) and a random
    similarity score, and derives a result_status by comparing that score
    against `threshold`. It does NOT look at the photo content at all --
    do not treat its output as a real biometric result.

    `threshold` is exposed as a parameter (rather than hard-coded) purely
    so different callers can demo different outcomes -- e.g. /register's
    duplicate check uses a stricter threshold than /verify or /claim, so
    a normal registration usually goes through instead of being blocked
    by an unlucky random score. This is a mock convenience, not a stand-in
    for real model calibration.
    """
    if not candidate_cow_ids:
        return {
            "top_match_cow_id": None,
            "similarity_score": 0.0,
            "result_status": "NO_MATCH",
        }

    rng = random.Random(photo_path)
    top_match_cow_id = rng.choice(candidate_cow_ids)
    similarity_score = round(rng.uniform(0.55, 0.99), 2)
    result_status = "MATCH" if similarity_score >= threshold else "NO_MATCH"

    return {
        "top_match_cow_id": top_match_cow_id,
        "similarity_score": similarity_score,
        "result_status": result_status,
    }

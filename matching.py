"""
Nearest-neighbor muzzle matching against the embedding gallery built by
embedding.py (./data/embeddings.npy + ./data/embeddings_meta.csv).

find_matches() is the importable entry point for the Streamlit app:
    from matching import find_matches
    result = find_matches("path/to/new_photo.jpg")

It first runs a cheap OpenCV blur check (Laplacian variance) and refuses
to match a photo that's too out-of-focus to be trustworthy. Otherwise it
embeds the photo and ranks the gallery by cosine similarity.

THRESHOLDS BELOW ARE CALIBRATED, NOT GUESSED: see calibrate_thresholds.py,
which measures genuine (same-cow) vs impostor (different-cow) score
distributions on the test split and prints recommended thresholds.

Re-run calibration whenever the underlying model changes.
"""

from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from embedding import embed_image


# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

EMB_PATH = Path("data/embeddings.npy")
META_PATH = Path("data/embeddings_meta.csv")


# --------------------------------------------------------------------------
# IMAGE QUALITY
# --------------------------------------------------------------------------

# Laplacian-variance cutoff for "usable focus".
#
# This threshold was calibrated empirically from the test split.
# The muzzle images are high-resolution, so the textbook blur threshold
# of around 100 is not appropriate for this dataset.
#
# RE-CALIBRATED from 20.0 to 10.0 after measuring the full 942-image test
# split: 20.0 was rejecting 6.16% of genuinely good photos as "too blurry"
# (58/942), including 84.6% of drone-sourced shots (median variance 11.57
# -- lower local texture from shooting distance, not actual blur) and 5.1%
# of ordinary handheld photos purely from natural variance. 10.0 keeps a
# real quality gate (still rejects 12/942 = 1.27% of the lowest-variance
# tail, and a synthetic mild blur still measures ~3.4, clearly below this
# cutoff) while accepting the dataset's normal-quality range. Recompute if
# the camera/resolution pipeline changes.

BLUR_THRESHOLD = 10.0


# --------------------------------------------------------------------------
# MATCH-SCORE DECISION TIERS
# --------------------------------------------------------------------------
#
# Cosine similarity range: [-1, 1]
#
# These thresholds were calibrated using the REAL trained ResNet50 model
# and the 942-image test embedding gallery.
#
# Calibration results:
#
# HIGH_CONFIDENCE_THRESHOLD = 0.9520
#   Impostor false-accept rate = 0.93%
#   Genuine false-reject rate  = 14.83%
#
# LOW_CONFIDENCE_THRESHOLD = 0.9250
#   Impostor false-accept rate = 4.94%
#   Genuine false-reject rate  = 6.83%
#
# Re-run calibrate_thresholds.py whenever the underlying model changes.

HIGH_CONFIDENCE_THRESHOLD = 0.9520
LOW_CONFIDENCE_THRESHOLD = 0.9250


# Cached gallery
_embeddings = None
_meta = None


# --------------------------------------------------------------------------
# LOAD GALLERY
# --------------------------------------------------------------------------

def _load_gallery():
    global _embeddings, _meta

    if _embeddings is not None:
        return _embeddings, _meta

    if not EMB_PATH.exists() or not META_PATH.exists():
        raise FileNotFoundError(
            f"Missing {EMB_PATH} or {META_PATH}. "
            "Run embedding.py first to build the gallery."
        )

    embeddings = np.load(EMB_PATH)
    meta = pd.read_csv(META_PATH)

    if len(meta) != embeddings.shape[0]:
        raise ValueError(
            f"{EMB_PATH} has {embeddings.shape[0]} rows but "
            f"{META_PATH} has {len(meta)} rows -- "
            "they must correspond 1:1."
        )

    _embeddings, _meta = embeddings, meta

    return _embeddings, _meta


# --------------------------------------------------------------------------
# BLUR CHECK
# --------------------------------------------------------------------------

def _blur_variance(image_path) -> float:
    """
    Calculate Laplacian variance of the image.

    Lower variance generally means the image is blurrier.
    """

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_GRAYSCALE
    )

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    return float(
        cv2.Laplacian(
            image,
            cv2.CV_64F
        ).var()
    )


# --------------------------------------------------------------------------
# MATCH TIER
# --------------------------------------------------------------------------

def _tier_for_score(score: float) -> str:
    """
    Convert cosine similarity score into a confidence tier.
    """

    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high_confidence"

    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "low_confidence"

    return "no_match"


# --------------------------------------------------------------------------
# GALLERY RANKING
# --------------------------------------------------------------------------

def _rank_gallery(query: np.ndarray, top_k: int) -> dict:
    """
    Score an already-embedded and L2-normalized query vector
    against the gallery.

    Since both query and gallery embeddings are L2-normalized,
    their dot product is cosine similarity.
    """

    embeddings, meta = _load_gallery()

    # Cosine similarity because both sides are L2-normalized
    scores = embeddings @ query

    k = min(top_k, len(scores))

    top_idx = np.argsort(scores)[::-1][:k]

    top_matches = [
        {
            "cow_id": str(meta.iloc[i]["cow_id"]),
            "score": float(scores[i])
        }
        for i in top_idx
    ]

    status = _tier_for_score(
        top_matches[0]["score"]
    )

    return {
        "status": status,
        "top_matches": top_matches,
        "quality_ok": True
    }


# --------------------------------------------------------------------------
# SINGLE-PHOTO MATCHING
# --------------------------------------------------------------------------

def find_matches(new_image_path, top_k: int = 3) -> dict:
    """
    Identify the closest cow(s) in the gallery for a new muzzle photo.

    Returns:

        {
            "status":
                "unusable"
                | "high_confidence"
                | "low_confidence"
                | "no_match",

            "top_matches": [
                {
                    "cow_id": str,
                    "score": float
                },
                ...
            ],

            "quality_ok": bool
        }

    If the image fails the blur check, no matching is performed.
    """

    # --------------------------------------------------------------
    # Step 1: Image quality check
    # --------------------------------------------------------------

    variance = _blur_variance(
        new_image_path
    )

    if variance < BLUR_THRESHOLD:
        return {
            "status": "unusable",
            "top_matches": [],
            "quality_ok": False
        }

    # --------------------------------------------------------------
    # Step 2: Generate embedding
    # --------------------------------------------------------------

    query = embed_image(
        new_image_path
    )

    # --------------------------------------------------------------
    # Step 3: Match against gallery
    # --------------------------------------------------------------

    return _rank_gallery(
        query,
        top_k
    )


# --------------------------------------------------------------------------
# REGISTERED-ANIMAL REFERENCE MATCHING
# --------------------------------------------------------------------------
#
# Everything above this point matches against the ML REFERENCE GALLERY
# (data/embeddings.npy / embeddings_meta.csv -- internal dataset identities
# like "cattle_1200"). That gallery is intentionally never treated as
# PashuPrint-enrolled livestock (see pages/1_Register.py and
# pages/2_Verify.py).
#
# The two functions below are a SEPARATE, additive path: comparing a query
# against ACTUAL registered animals' own reference embeddings (stored via
# backend/db.py's add_embedding()/get_embedding(), which existed but was
# never wired up). Same embedding pipeline, same thresholds, same L2/cosine
# math -- just a different, smaller reference set.

def embed_query_average(image_paths) -> np.ndarray:
    """
    Quality-check, embed, and average multiple photos into one
    L2-normalized query vector. Same averaging approach as
    find_matches_multi() step 4/5, exposed standalone so the resulting
    query vector can be compared against something other than the ML
    gallery. Unusable/unreadable photos are skipped.

    Raises ValueError if no supplied photo is usable.
    """

    usable_vectors = []

    for path in image_paths:
        try:
            variance = _blur_variance(path)
        except ValueError:
            continue

        if variance < BLUR_THRESHOLD:
            continue

        usable_vectors.append(embed_image(path))

    if not usable_vectors:
        raise ValueError("No usable photo to embed.")

    query = np.mean(usable_vectors, axis=0)

    norm = np.linalg.norm(query)
    if norm > 0:
        query = query / norm

    return query


def rank_against_registered(query: np.ndarray, registered: list, top_k: int = 3) -> dict:
    """
    Compare a query embedding against ACTUAL PashuPrint-registered
    animals' own reference embeddings -- NOT the ML gallery.

    `registered` is a list of (cow_id, embedding_vector) pairs, e.g.
    built from backend.db.get_all_animals() + backend.db.get_embedding().
    Uses the SAME calibrated thresholds as gallery matching
    (_tier_for_score / HIGH_CONFIDENCE_THRESHOLD / LOW_CONFIDENCE_THRESHOLD).

    Returns {"status": "no_match", "top_matches": [], "quality_ok": True}
    if `registered` is empty (nothing to compare against).
    """

    if not registered:
        return {"status": "no_match", "top_matches": [], "quality_ok": True}

    cow_ids = [cow_id for cow_id, _ in registered]
    vectors = np.stack([np.asarray(vec, dtype=np.float32) for _, vec in registered])

    scores = vectors @ query

    k = min(top_k, len(scores))
    top_idx = np.argsort(scores)[::-1][:k]

    top_matches = [
        {"cow_id": cow_ids[i], "score": float(scores[i])}
        for i in top_idx
    ]

    status = _tier_for_score(top_matches[0]["score"])

    return {"status": status, "top_matches": top_matches, "quality_ok": True}


# --------------------------------------------------------------------------
# MULTI-PHOTO MATCHING
# --------------------------------------------------------------------------

def find_matches_multi(
    image_paths,
    top_k: int = 3
) -> dict:
    """
    Multi-photo variant of find_matches().

    Averaging embeddings BEFORE checking identity is unsafe: 2 photos of
    cow A + 1 photo of cow B can still average out close enough to cow A's
    gallery cluster to read as "high_confidence", silently hiding an
    animal swap. So before any averaging happens, each usable photo is
    independently ranked against the gallery (same logic as
    find_matches()) to get its own top-1 cow_id. Only if every photo's
    independent top-1 prediction agrees on the same cow do we average the
    embeddings and produce a normal verification result -- otherwise we
    return "inconsistent_images" and refuse to produce a match.

    Each photo goes through the blur-quality check; unusable photos are
    skipped. "unusable" is returned only when every supplied photo fails
    the quality check or cannot be read.

    Returns the same structure as find_matches(), plus:
        "per_image_matches": [{"cow_id": str, "score": float}, ...]
            One entry per usable photo (in input order), showing what that
            single photo alone matched to. Always present except on
            "unusable". On "inconsistent_images", "top_matches" is left
            empty ([]) and this is the only place to see what happened.
    """

    usable_vectors = []
    per_image_matches = []

    # --------------------------------------------------------------
    # Step 1: Process each photo -- quality check, embed, and get its
    # OWN independent top-1 prediction (before any averaging).
    # --------------------------------------------------------------

    for path in image_paths:

        try:
            variance = _blur_variance(path)

        except ValueError:
            # Skip unreadable photo
            continue

        # Skip blurry photo
        if variance < BLUR_THRESHOLD:
            continue

        # Generate embedding for usable photo
        vector = embed_image(path)
        usable_vectors.append(vector)

        # Independent single-image prediction for this photo alone, used
        # only for the cross-photo agreement check below -- not used for
        # the final averaged score.
        single_top = _rank_gallery(vector, top_k=1)["top_matches"][0]
        per_image_matches.append(
            {"cow_id": single_top["cow_id"], "score": single_top["score"]}
        )

    # --------------------------------------------------------------
    # Step 2: Make sure at least one photo is usable
    # --------------------------------------------------------------

    if not usable_vectors:
        return {
            "status": "unusable",
            "top_matches": [],
            "quality_ok": False,
            "per_image_matches": [],
        }

    # --------------------------------------------------------------
    # Step 3: Cross-photo agreement check. Compare cow_id (the animal's
    # identity), not gallery row -- the gallery holds several photos per
    # cow, so "different rows" does not mean "different cow".
    # --------------------------------------------------------------

    predicted_cow_ids = {m["cow_id"] for m in per_image_matches}

    if len(usable_vectors) > 1 and len(predicted_cow_ids) > 1:
        return {
            "status": "inconsistent_images",
            "top_matches": [],
            "quality_ok": True,
            "per_image_matches": per_image_matches,
        }

    # --------------------------------------------------------------
    # Step 4: All usable photos agree -- average embeddings
    # --------------------------------------------------------------

    query = np.mean(
        usable_vectors,
        axis=0
    )

    # --------------------------------------------------------------
    # Step 5: L2 normalize averaged embedding
    # --------------------------------------------------------------

    norm = np.linalg.norm(query)

    if norm > 0:
        query = query / norm

    # --------------------------------------------------------------
    # Step 6: Match averaged embedding
    # --------------------------------------------------------------

    result = _rank_gallery(
        query,
        top_k
    )
    result["per_image_matches"] = per_image_matches
    return result
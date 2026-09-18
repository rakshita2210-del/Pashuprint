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
distributions on the test split and prints a recommended cut. Re-run it
whenever the underlying model changes and update the two constants below.
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

# Laplacian-variance cutoff for "usable focus". This is a separate concern
# from match-score calibration (it's about the photo, not the model).
#
# NOTE: the textbook default of ~100 assumes small/moderate-resolution
# photos; it does NOT transfer to this dataset. These muzzle close-ups are
# high-res (~2000x1800) and measured variance runs much higher across the
# board (test-split median ~220, p90 ~700). Using 100 as-is would reject
# roughly a quarter of genuinely sharp photos. 20.0 was set empirically from
# the test split's own variance distribution (roughly its 8th percentile)
# and spot-checked visually: images below it were visibly out of focus,
# while the median-variance image was crisp. Recompute if the camera/
# resolution pipeline changes.
BLUR_THRESHOLD = 20.0

# --- Match-score decision tiers (cosine similarity, range [-1, 1]) --------
# Calibrated by calibrate_thresholds.py against genuine vs. impostor score
# distributions on the test split (see that script's output for the
# false-accept/false-reject rates at each cut). Update these two numbers if
# you re-run it after retraining.
#
# CURRENT VALUES ARE FROM AN UNTRAINED PLACEHOLDER CHECKPOINT, NOT THE REAL
# MODEL. embeddings.npy was built with a randomly-initialized resnet50 (the
# real Colab training run hadn't produced models/resnet50_muzzle.pt yet), so
# genuine and impostor scores barely separate (means 0.994 vs 0.951, heavy
# overlap) -- these thresholds reject 30-60% of genuine matches. That's
# expected for random features, not a calibration bug. RE-RUN
# calibrate_thresholds.py after training on real data and replace both
# numbers below before trusting this for actual matching.
HIGH_CONFIDENCE_THRESHOLD = 0.9990
LOW_CONFIDENCE_THRESHOLD = 0.9960

_embeddings = None
_meta = None


def _load_gallery():
    global _embeddings, _meta
    if _embeddings is not None:
        return _embeddings, _meta

    if not EMB_PATH.exists() or not META_PATH.exists():
        raise FileNotFoundError(
            f"Missing {EMB_PATH} or {META_PATH}. Run embedding.py first to build the gallery."
        )

    embeddings = np.load(EMB_PATH)
    meta = pd.read_csv(META_PATH)

    if len(meta) != embeddings.shape[0]:
        raise ValueError(
            f"{EMB_PATH} has {embeddings.shape[0]} rows but {META_PATH} has "
            f"{len(meta)} rows -- they must correspond 1:1."
        )

    _embeddings, _meta = embeddings, meta
    return _embeddings, _meta


def _blur_variance(image_path) -> float:
    """Laplacian variance of the image -- lower means blurrier."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def _tier_for_score(score: float) -> str:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high_confidence"
    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "low_confidence"
    return "no_match"


def _rank_gallery(query: np.ndarray, top_k: int) -> dict:
    """Shared ranking step for find_matches()/find_matches_multi(): score an
    already-embedded (and already L2-normalized) query vector against the
    gallery and tier the result."""
    embeddings, meta = _load_gallery()

    scores = embeddings @ query  # both sides are L2-normalized -> cosine similarity
    k = min(top_k, len(scores))
    top_idx = np.argsort(scores)[::-1][:k]

    top_matches = [
        {"cow_id": str(meta.iloc[i]["cow_id"]), "score": float(scores[i])}
        for i in top_idx
    ]

    status = _tier_for_score(top_matches[0]["score"])
    return {"status": status, "top_matches": top_matches, "quality_ok": True}


def find_matches(new_image_path, top_k: int = 3) -> dict:
    """
    Identify the closest cow(s) in the gallery for a new muzzle photo.

    Returns a dict:
        {
          "status": "unusable" | "high_confidence" | "low_confidence" | "no_match",
          "top_matches": [{"cow_id": str, "score": float}, ...],  # [] if unusable
          "quality_ok": bool,
        }
    """
    variance = _blur_variance(new_image_path)
    if variance < BLUR_THRESHOLD:
        return {"status": "unusable", "top_matches": [], "quality_ok": False}

    query = embed_image(new_image_path)
    return _rank_gallery(query, top_k)


def find_matches_multi(image_paths, top_k: int = 3) -> dict:
    """
    Multi-photo variant of find_matches(): average the embeddings of several
    photos of the same cow into one identity vector, then rank the gallery
    exactly like find_matches(). Mirrors its quality gate (per-photo blur
    check, skipping unusable photos rather than failing outright) and score
    tiers.

    Same return shape as find_matches(). "unusable" is returned only if
    every supplied photo failed the blur check.
    """
    usable_vectors = []
    for path in image_paths:
        try:
            variance = _blur_variance(path)
        except ValueError:
            continue  # unreadable photo -- skip it, keep going
        if variance < BLUR_THRESHOLD:
            continue
        usable_vectors.append(embed_image(path))

    if not usable_vectors:
        return {"status": "unusable", "top_matches": [], "quality_ok": False}

    query = np.mean(usable_vectors, axis=0)
    norm = np.linalg.norm(query)
    if norm > 0:
        query = query / norm

    return _rank_gallery(query, top_k)

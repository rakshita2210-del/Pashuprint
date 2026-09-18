"""
dup_check.py
------------
Duplicate-PHOTO detection for PashuPrint (NOT biometric/animal recognition).

This module only answers one narrow question: "has this exact photo (or a
near-identical copy of it) been uploaded before?" It does this with a
perceptual hash (pHash), which is a cheap, well-understood technique for
spotting the same or barely-modified image (re-saved, slightly compressed,
lightly cropped, etc). It has NOTHING to do with recognizing whether two
different muzzle photos belong to the same animal -- that is a separate,
much harder job for the future ML/ResNet50 module.

Responsibilities, kept deliberately separate:
    db.py          -> stores/retrieves animal data, photo paths, fraud flags
    dup_check.py    -> (this file) detects reused/near-identical photo files
    muzzle AI module -> decides if two different photos are the same animal
    FastAPI          -> wires all of the above together

Dependencies: Pillow (image loading) and ImageHash (pHash + hash distance).
No ResNet, no embeddings, no OpenCV, no neural network of any kind.
"""

from typing import List, Optional, TypedDict

from PIL import Image
import imagehash

# How close two pHashes need to be (in Hamming distance) to be considered
# the "same" photo. Lower = stricter. Kept as a constant so it's easy to
# tune later without hunting through the code.
DUPLICATE_THRESHOLD = 5


class DuplicateCheckResult(TypedDict):
    is_duplicate: bool
    matched_photo_path: Optional[str]
    hash_distance: Optional[int]


def compute_image_hash(image_path: str) -> imagehash.ImageHash:
    """
    Open an image and compute its perceptual hash (pHash).

    A perceptual hash boils an image down to a short fingerprint such that
    visually similar/near-identical images end up with similar fingerprints.
    This lets us compare two images cheaply (just subtracting two hashes)
    instead of comparing every pixel directly, which would be slow and
    overly sensitive to tiny, meaningless differences (recompression,
    minor resizing, etc).

    Raises whatever Pillow/imagehash raise if the file can't be opened --
    the caller decides what to do with that (see check_duplicate below).
    """
    with Image.open(image_path) as img:
        return imagehash.phash(img)


def check_duplicate(
    new_image_path: str, existing_photo_paths: List[str]
) -> DuplicateCheckResult:
    """
    Check whether new_image_path is the same/near-identical to any photo
    already in existing_photo_paths.

    Compares the new photo's pHash against every existing photo's pHash,
    keeps track of the closest (smallest-distance) match, and flags it as
    a duplicate if that closest distance is below DUPLICATE_THRESHOLD.

    Returns:
        {
            "is_duplicate": True/False,
            "matched_photo_path": path of the closest match, or None,
            "hash_distance": distance to the closest match, or None if
                              existing_photo_paths was empty
        }

    Error handling:
    - If the NEW image can't be opened, this raises a clear ValueError --
      there's nothing useful to check without it.
    - If an EXISTING image can't be opened (missing file, corrupted,
      unsupported format, etc), that one photo is skipped and checking
      continues with the rest. One bad file in the database shouldn't
      break duplicate-checking for everyone else.
    """
    try:
        new_hash = compute_image_hash(new_image_path)
    except Exception as exc:
        raise ValueError(
            f"Could not process the new image at '{new_image_path}': {exc}"
        ) from exc

    if not existing_photo_paths:
        return {
            "is_duplicate": False,
            "matched_photo_path": None,
            "hash_distance": None,
        }

    best_distance: Optional[int] = None
    best_match_path: Optional[str] = None

    for existing_path in existing_photo_paths:
        try:
            existing_hash = compute_image_hash(existing_path)
        except Exception:
            # Skip files that are missing/corrupted/unreadable and keep going.
            continue

        # imagehash hashes support subtraction directly: this returns the
        # Hamming distance between the two hashes (0 = identical).
        distance = new_hash - existing_hash

        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_match_path = existing_path

    if best_distance is None:
        # Every existing path failed to open -- nothing usable to compare against.
        return {
            "is_duplicate": False,
            "matched_photo_path": None,
            "hash_distance": None,
        }

    # imagehash returns numpy-flavored int/bool types from hash subtraction;
    # cast to plain Python types so this plays nicely with anything that
    # JSON-serializes the result later (e.g. a future FastAPI response).
    best_distance = int(best_distance)
    is_duplicate = bool(best_distance < DUPLICATE_THRESHOLD)

    return {
        "is_duplicate": is_duplicate,
        "matched_photo_path": best_match_path if is_duplicate else None,
        "hash_distance": best_distance,
    }

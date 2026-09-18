"""
cattle_gate.py
--------------
Domain-validation gate: "does this look like a plausible cattle/muzzle
photo?" -- run BEFORE embedding.embed_image() / matching.find_matches(),
so a photo of a person, dog, car, document, etc. can never reach the
ResNet50 muzzle matcher and can never produce a "MATCHED" result.

This module answers ONLY that question. It never decides which cow an
image belongs to -- that remains matching.py's job, entirely unchanged
(model, 320x320 input, 512-dim embeddings, L2 normalization, cosine
similarity, HIGH=0.9520/LOW=0.9250, blur threshold 20.0 are all untouched).

--------------------------------------------------------------------------
WHAT THIS ACTUALLY IS (read before trusting it)
--------------------------------------------------------------------------
This reuses a model ALREADY present in this project's cache: the standard
ImageNet-1k-pretrained "resnet50.a1_in1k" checkpoint that timm downloaded
the first time train_muzzle_id.py ran `timm.create_model("resnet50",
pretrained=True, ...)` to build the muzzle model's backbone. It is loaded
here WITH its original 1000-way ImageNet classification head (unlike
embedding.py's num_classes=0 headless variant used for muzzle embeddings)
-- no new architecture, no new download in the common case, no change to
the muzzle checkpoint or the muzzle model's own weights.

An earlier version of this gate tried to require a POSITIVE "this looks
bovine" signal (checking the probability mass on ImageNet's three
cattle-adjacent classes: 345 ox, 346 water buffalo, 347 bison). That
was measured empirically against 5 real muzzle-crop photos from this
project's own dataset and found to be UNRELIABLE: bovine-class
probability on genuine muzzle crops ranged from 0.00007 to 0.0097 --
indistinguishable from noise, because ImageNet's "ox"/"water buffalo"/
"bison" classes were trained on whole-animal photos in context (pasture,
full body), and a tight close-up muzzle crop is out-of-distribution for
that. Requiring positive bovine confirmation would have REJECTED
essentially all genuine cattle photos, which is worse than no gate at
all. That approach was abandoned.

What ships instead is the safer, ASYMMETRIC design the measurement
actually supports:
  - PERMISSIVE BY DEFAULT: an image is treated as plausibly-cattle
    unless the classifier gives a confident, specific reason to think
    otherwise. This is what makes "unknown/new cattle" pass (task
    requirement) even though the classifier cannot positively confirm
    "bovine".
  - REJECT ONLY on a confident top-1 hit against a curated blacklist of
    ImageNet classes that are unambiguously NOT cattle: the ~143 dog/
    cat/wild-canid/wild-felid classes (ImageNet's largest, most reliable
    block -- indices 151-293, contiguous, verified programmatically
    against this environment's timm.data.ImageNetInfo, not guessed from
    memory), plus curated vehicle, building/structure, electronics/
    document, and common-household-object classes.

--------------------------------------------------------------------------
KNOWN, REAL LIMITATIONS -- do not oversell this
--------------------------------------------------------------------------
1. This is a GENERIC ImageNet-1k domain classifier, not a trained
   cattle/muzzle detector. No such detector exists in this project or its
   dependencies; building one would require labeled non-cattle data and a
   training run, which this task explicitly says not to start.
2. ImageNet-1k has no "person" class at all (a well-known omission), so
   there is no reliable, direct signal for "this is a human photo". A
   face/selfie photo is rejected only if it happens to trip one of the
   blacklist categories (e.g. it's dominated by clothing, eyewear, or an
   object in-frame) -- there is no guarantee for an arbitrary human photo.
3. The blacklist covers the ImageNet categories that are large, reliable,
   and explicitly named in the task (dogs/cats/other common animals,
   vehicles, buildings, electronics/documents, common household objects).
   It is NOT exhaustive over "every possible non-cattle image" -- e.g.
   ImageNet has no generic "tree" class, so an outdoor plant/tree photo
   may not trip this gate. In that case the EXISTING calibrated cosine-
   similarity thresholds (HIGH=0.9520/LOW=0.9250) remain the second line
   of defense: unrelated content is very unlikely to score that high
   against any specific enrolled cow's embedding.
4. A photo of a different livestock species shot in the same tight
   muzzle-crop style (e.g. goat, horse) is the hardest case: it may not
   land in the blacklist (none of those are covered) and would reach the
   real matcher, relying on the same similarity-threshold backstop as (3).

Bottom line: this is a real, evidence-based, pretrained-classifier gate
that reliably blocks the cases the project's dependencies can actually
support (common animals, vehicles, buildings, electronics, documents,
generic objects) with a permissive fallback so it never breaks genuine
enrollment. It is not, and does not claim to be, a complete solution.
"""

from typing import Optional, TypedDict

import torch
from PIL import Image, UnidentifiedImageError

# --------------------------------------------------------------------------
# CURATED BLACKLIST -- ImageNet-1k class indices that are confident,
# specific evidence the image is NOT a cattle muzzle. Verified
# programmatically against this environment's timm.data.ImageNetInfo
# (see the exploration session that produced this list); not guessed.
# --------------------------------------------------------------------------

# Dogs (151-268), wild canids: wolves/coyote/dingo/foxes (269-280),
# cats (281-285), big cats (286-293). Contiguous block, ImageNet's
# largest and most reliably-classified animal category -- covers the
# task's "dog/cat/other animal" requirement well.
_DOGS_CATS_WILD_CARNIVORES = list(range(151, 294))

_VEHICLES = [
    403, 404, 428, 436, 444, 466, 475, 476, 479, 511, 555, 565, 569, 575,
    603, 609, 627, 656, 665, 670, 690, 705, 717, 751, 791, 817, 829, 864,
    867, 870, 874, 880, 895,
]

_BUILDINGS_STRUCTURES = [
    425, 449, 483, 497, 498, 525, 580, 624, 663, 668, 698, 727, 821, 839,
]

_ELECTRONICS_DOCUMENTS_OFFICE = [
    446, 487, 526, 527, 549, 553, 556, 605, 620, 664, 681, 742, 782, 872,
    904, 916, 921, 922,
]

_HOUSEHOLD_OBJECTS = [
    409, 414, 418, 440, 455, 461, 504, 508, 512, 515, 530, 532, 561, 608,
    610, 619, 623, 636, 647, 659, 673, 709, 710, 720, 729, 736, 737, 747,
    748, 765, 767, 770, 788, 806, 809, 826, 831, 836, 837, 841, 846, 878,
    879, 883, 892, 893, 896, 898, 907, 910, 923, 968,
]

_BLACKLIST_INDICES = frozenset(
    _DOGS_CATS_WILD_CARNIVORES
    + _VEHICLES
    + _BUILDINGS_STRUCTURES
    + _ELECTRONICS_DOCUMENTS_OFFICE
    + _HOUSEHOLD_OBJECTS
)

# ImageNet's 3 cattle-adjacent classes. Kept ONLY as a diagnostic field on
# the result (visible in logs/UI if useful) -- NOT used to gate anything,
# per the measurement described above.
_BOVINE_LABELS = {"ox", "water buffalo", "water ox", "asiatic buffalo", "bubalus bubalis", "bison"}

# Minimum top-1 confidence required before a blacklist hit is trusted as a
# real rejection signal, rather than classifier noise/uncertainty. Not
# rigorously calibrated like matching.py's genuine/impostor thresholds
# (no non-cattle labeled dataset exists to sweep against) -- chosen to be
# comfortably below every confident non-cattle hit observed during manual
# testing (0.63-0.9987) while still requiring a real, non-trivial signal.
BLACKLIST_CONFIDENCE_THRESHOLD = 0.15

_CLASSIFIER_NAME = "resnet50.a1_in1k"

_model = None
_transform = None
_bovine_indices = None


class CattleGateResult(TypedDict):
    is_cattle_like: bool
    reason: Optional[str]
    top1_label: Optional[str]
    top1_probability: Optional[float]
    bovine_probability: Optional[float]


def _load_classifier():
    global _model, _transform, _bovine_indices
    if _model is not None:
        return _model, _transform, _bovine_indices

    import timm

    model = timm.create_model(_CLASSIFIER_NAME, pretrained=True)
    model.eval()

    data_cfg = timm.data.resolve_data_config({}, model=model)
    transform = timm.data.create_transform(**data_cfg)

    info = timm.data.ImageNetInfo()
    bovine_indices = [
        i for i in range(info.num_classes())
        if {p.strip().lower() for p in info.index_to_description(i).split(",")} & _BOVINE_LABELS
    ]

    _model, _transform, _bovine_indices = model, transform, bovine_indices
    return _model, _transform, _bovine_indices


def _label_for(index: int) -> str:
    import timm
    return timm.data.ImageNetInfo().index_to_description(index)


def assess_cattle_likeness(image_path) -> CattleGateResult:
    """
    Domain-plausibility check for a single uploaded photo. Does not call
    embedding.embed_image() or matching.find_matches() -- entirely
    separate from the muzzle-identity pipeline.

    Permissive by design: only rejects on a confident hit against the
    curated non-cattle blacklist above. Everything else -- including a
    genuinely unfamiliar/unknown cow -- passes through as "cattle-like",
    consistent with this gate answering "what domain is this?", never
    "which cow is this?".
    """
    try:
        image = Image.open(image_path).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        return {
            "is_cattle_like": False,
            "reason": f"Could not open as an image: {exc}",
            "top1_label": None,
            "top1_probability": None,
            "bovine_probability": None,
        }

    model, transform, bovine_indices = _load_classifier()

    tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        probs = torch.softmax(model(tensor), dim=1)[0]

    top1_idx = int(torch.argmax(probs))
    top1_prob = float(probs[top1_idx])
    top1_label = _label_for(top1_idx)
    bovine_prob = float(probs[bovine_indices].sum())

    is_blacklisted = top1_idx in _BLACKLIST_INDICES and top1_prob >= BLACKLIST_CONFIDENCE_THRESHOLD

    return {
        "is_cattle_like": not is_blacklisted,
        "reason": (f"Detected as '{top1_label}' ({top1_prob*100:.1f}% confidence)" if is_blacklisted else None),
        "top1_label": top1_label,
        "top1_probability": top1_prob,
        "bovine_probability": bovine_prob,
    }

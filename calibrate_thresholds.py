"""
Calibrate matching.py's decision thresholds against real score distributions
instead of guessing.

Method: the gallery (./data/embeddings.npy + embeddings_meta.csv) already
holds one embedding per test-split image. For every test image, treat it as
a query and compare it against every OTHER test-split embedding (excluding
itself):
  - genuine pairs  = comparisons against other photos of the SAME cow
  - impostor pairs = comparisons against photos of DIFFERENT cows

This gives real cosine-similarity distributions for "should match" vs.
"should not match" without needing any new data collection. We then report
percentiles for both and recommend:
  - HIGH_CONFIDENCE_THRESHOLD: a score most genuine pairs clear and most
    impostor pairs don't (low false-accept rate)
  - LOW_CONFIDENCE_THRESHOLD: a lower score below which impostors dominate,
    used as the no_match floor

Run: python calibrate_thresholds.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

EMB_PATH = Path("data/embeddings.npy")
META_PATH = Path("data/embeddings_meta.csv")


def load_gallery():
    embeddings = np.load(EMB_PATH)
    meta = pd.read_csv(META_PATH)
    assert len(meta) == embeddings.shape[0], "embeddings/meta row count mismatch"
    return embeddings, meta


def compute_genuine_impostor_scores(embeddings, meta):
    cow_ids = meta["cow_id"].to_numpy()
    n = embeddings.shape[0]

    # Full pairwise cosine-similarity matrix (embeddings are L2-normalized,
    # so this is just the Gram matrix). n is the test-split size (hundreds),
    # so this is cheap.
    sim = embeddings @ embeddings.T

    same_cow = cow_ids[:, None] == cow_ids[None, :]
    iu = np.triu_indices(n, k=1)  # upper triangle, excluding diagonal (self-pairs)

    pair_same = same_cow[iu]
    pair_scores = sim[iu]

    genuine_scores = pair_scores[pair_same]
    impostor_scores = pair_scores[~pair_same]
    return genuine_scores, impostor_scores


def summarize(name, scores):
    pct = np.percentile(scores, [1, 5, 10, 25, 50, 75, 90, 95, 99])
    print(f"{name} (n={len(scores)})")
    print(f"  mean={scores.mean():.4f}  std={scores.std():.4f}")
    print(f"  min={scores.min():.4f}  max={scores.max():.4f}")
    labels = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
    print("  " + "  ".join(f"{l}={v:.4f}" for l, v in zip(labels, pct)))


def recommend_thresholds(genuine_scores, impostor_scores):
    """
    Sweep candidate cut points and pick thresholds by error rates:
      - HIGH_CONFIDENCE: smallest score where the false-accept rate
        (impostor pairs scoring >= threshold) drops to <= 1%.
      - LOW_CONFIDENCE: smallest score where the false-accept rate
        drops to <= 5% (a looser floor separating "maybe" from "no").
    Falls back to the impostor 99.9th/99th percentile if no clean cut
    exists in the sampled range.
    """
    candidates = np.linspace(0.0, 1.0, 1001)
    far = np.array([(impostor_scores >= t).mean() for t in candidates])
    frr = np.array([(genuine_scores < t).mean() for t in candidates])

    def first_threshold_at_or_below(far_target):
        idx = np.where(far <= far_target)[0]
        if len(idx) == 0:
            return None
        return candidates[idx[0]]

    high = first_threshold_at_or_below(0.01)
    low = first_threshold_at_or_below(0.05)

    if high is None:
        high = float(np.percentile(impostor_scores, 99.9))
    if low is None:
        low = float(np.percentile(impostor_scores, 99))

    # Report the operating point (FAR/FRR) actually achieved at each cut.
    def rates_at(t):
        far_t = (impostor_scores >= t).mean()
        frr_t = (genuine_scores < t).mean()
        return far_t, frr_t

    high_far, high_frr = rates_at(high)
    low_far, low_frr = rates_at(low)

    return {
        "high": (float(high), float(high_far), float(high_frr)),
        "low": (float(low), float(low_far), float(low_frr)),
    }


def main():
    embeddings, meta = load_gallery()
    genuine_scores, impostor_scores = compute_genuine_impostor_scores(embeddings, meta)

    print(f"Gallery: {embeddings.shape[0]} images, {meta['cow_id'].nunique()} cows")
    print(f"Genuine pairs (same cow): {len(genuine_scores)}")
    print(f"Impostor pairs (different cow): {len(impostor_scores)}")
    print()
    summarize("Genuine score distribution", genuine_scores)
    print()
    summarize("Impostor score distribution", impostor_scores)
    print()

    overlap = (genuine_scores.min() <= impostor_scores.max())
    print(f"Distributions overlap: {overlap}")
    if genuine_scores.mean() <= impostor_scores.mean():
        print(
            "WARNING: genuine mean <= impostor mean -- the embedding model is "
            "not separating same-cow from different-cow photos at all. This is "
            "expected if embeddings.npy was built from an UNTRAINED/placeholder "
            "checkpoint. Re-run this script after training on real data before "
            "trusting these thresholds."
        )
    print()

    rec = recommend_thresholds(genuine_scores, impostor_scores)
    high_t, high_far, high_frr = rec["high"]
    low_t, low_far, low_frr = rec["low"]

    print("=== Recommended thresholds ===")
    print(
        f"HIGH_CONFIDENCE_THRESHOLD = {high_t:.4f}  "
        f"(impostor false-accept rate={high_far:.4f}, genuine false-reject rate={high_frr:.4f})"
    )
    print(
        f"LOW_CONFIDENCE_THRESHOLD  = {low_t:.4f}  "
        f"(impostor false-accept rate={low_far:.4f}, genuine false-reject rate={low_frr:.4f})"
    )

    return high_t, low_t


if __name__ == "__main__":
    main()

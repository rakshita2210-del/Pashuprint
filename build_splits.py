import csv
import random
from pathlib import Path

RAW_DIR = Path("BeefCattle_Muzzle_database/BeefCattle_Muzzle_Individualized")
OUT_PATH = Path("data/splits.csv")
MIN_IMAGES = 8
SEED = 42
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def scan_manifest():
    rows = []
    for cow_dir in sorted(RAW_DIR.iterdir()):
        if not cow_dir.is_dir():
            continue
        cow_id = cow_dir.name
        for img_path in sorted(cow_dir.iterdir()):
            if img_path.suffix.lower() in IMG_EXTS:
                rows.append((str(img_path.as_posix()), cow_id))
    return rows


def assign_splits(image_paths, rng):
    paths = list(image_paths)
    rng.shuffle(paths)
    n = len(paths)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    n_test = n - n_train - n_val
    splits = ["train"] * n_train + ["val"] * n_val + ["test"] * n_test
    return list(zip(paths, splits))


def main():
    rng = random.Random(SEED)

    manifest = scan_manifest()

    by_cow = {}
    for path, cow_id in manifest:
        by_cow.setdefault(cow_id, []).append(path)

    kept_cows = {cid: paths for cid, paths in by_cow.items() if len(paths) >= MIN_IMAGES}
    dropped_cows = {cid: paths for cid, paths in by_cow.items() if len(paths) < MIN_IMAGES}

    split_counts = {"train": 0, "val": 0, "test": 0}
    out_rows = []
    for cow_id in sorted(kept_cows):
        image_count_for_this_cow = len(by_cow[cow_id])
        assigned = assign_splits(kept_cows[cow_id], rng)
        for path, split in assigned:
            out_rows.append((path, cow_id, image_count_for_this_cow, split))
            split_counts[split] += 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_path", "cow_id", "image_count_for_this_cow", "split"])
        writer.writerows(out_rows)

    total_images = sum(len(v) for v in by_cow.values())
    kept_images = sum(len(v) for v in kept_cows.values())

    print("=== Manifest scan ===")
    print(f"Total cow folders found : {len(by_cow)}")
    print(f"Total images found      : {total_images}")
    print()
    print("=== Filtering (min images per cow = %d) ===" % MIN_IMAGES)
    print(f"Cows kept    : {len(kept_cows)}")
    print(f"Cows dropped : {len(dropped_cows)}")
    if dropped_cows:
        dropped_list = ", ".join(f"{cid}({len(paths)})" for cid, paths in sorted(dropped_cows.items()))
        print(f"Dropped cows : {dropped_list}")
    print()
    print("=== Split output ===")
    print(f"Images written to {OUT_PATH} : {kept_images}")
    print(f"  train : {split_counts['train']}")
    print(f"  val   : {split_counts['val']}")
    print(f"  test  : {split_counts['test']}")


if __name__ == "__main__":
    main()

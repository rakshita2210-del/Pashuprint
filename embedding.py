"""
Embedding extraction for cow muzzle identification.

Loads the trained resnet50_muzzle.pt checkpoint (see train_muzzle_id.py),
strips off the final classifier, and exposes `embed_image()` to turn a
muzzle photo into an L2-normalized 512-dim fingerprint. Two such vectors
can be compared with cosine similarity / dot product to decide "same cow
or different cow" without needing the classifier at all -- this is what
lets the model generalize to cows outside the training label set.

Importable API (used directly by the Streamlit app later):
    from embedding import embed_image
    vec = embed_image("path/to/photo.jpg")   # -> np.ndarray, shape (512,), unit norm

Run as a script to embed the whole test split:
    python embedding.py
"""

from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
CKPT_PATH = Path("models/resnet50_muzzle.pt")

# Same DATA_ROOT convention as train_muzzle_id.py: image_path values in the
# CSV are relative (e.g. "data/raw/cattle_0100/...jpg"), resolved against this.
DATA_ROOT = Path(".")
CSV_PATH = Path("data/splits.csv")
OUT_EMB_PATH = Path("data/embeddings.npy")
OUT_META_PATH = Path("data/embeddings_meta.csv")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


# --------------------------------------------------------------------------
# MODEL (backbone + embedding layer only -- classifier is dropped)
# --------------------------------------------------------------------------
class _EmbeddingNet(nn.Module):
    def __init__(self, embedding_dim: int):
        super().__init__()
        self.backbone = timm.create_model("resnet50", pretrained=False, num_classes=0)
        self.embedding = nn.Linear(self.backbone.num_features, embedding_dim)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        features = self.backbone(x)                # (B, 2048)
        return self.relu(self.embedding(features))  # (B, embedding_dim)


# Lazy-loaded singletons so importing this module is cheap; the model is
# only pulled onto the device the first time embed_image() is actually called.
_model = None
_transform = None


def _load_model():
    global _model, _transform
    if _model is not None:
        return _model, _transform

    if not CKPT_PATH.exists():
        raise FileNotFoundError(
            f"Checkpoint not found at {CKPT_PATH}. Train the model first "
            f"(train_muzzle_id.py) and place resnet50_muzzle.pt there."
        )

    checkpoint = torch.load(CKPT_PATH, map_location=DEVICE)
    embedding_dim = checkpoint["embedding_dim"]
    img_size = checkpoint["img_size"]

    net = _EmbeddingNet(embedding_dim)

    # The checkpoint holds backbone + embedding + classifier weights; keep
    # everything except classifier.* since we only need the fingerprint.
    full_state = checkpoint["model_state_dict"]
    net_state = {k: v for k, v in full_state.items() if not k.startswith("classifier.")}
    net.load_state_dict(net_state)

    net.to(DEVICE)
    net.eval()

    transform = transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    _model, _transform = net, transform
    return _model, _transform


def embed_image(image_path) -> np.ndarray:
    """
    Compute an L2-normalized 512-dim embedding for a single muzzle photo.

    Args:
        image_path: str or Path to an image file.

    Returns:
        np.ndarray of shape (512,), dtype float32, unit L2 norm.
    """
    model, transform = _load_model()

    image = Image.open(image_path).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        embedding = model(tensor)

    embedding = embedding.squeeze(0).cpu().numpy().astype(np.float32)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding


# --------------------------------------------------------------------------
# SCRIPT: embed the whole test split, save embeddings.npy + meta csv
# --------------------------------------------------------------------------
def build_test_embeddings():
    import pandas as pd

    df = pd.read_csv(CSV_PATH)
    test_df = df[df["split"] == "test"].reset_index(drop=True)

    embeddings = []
    records = []
    for idx, row in test_df.iterrows():
        img_path = DATA_ROOT / row["image_path"]
        vec = embed_image(img_path)
        embeddings.append(vec)
        records.append(
            {
                "cow_id": row["cow_id"],
                "image_path": row["image_path"],
                "embedding_index": idx,
            }
        )
        if (idx + 1) % 100 == 0:
            print(f"  embedded {idx + 1}/{len(test_df)}")

    embeddings = np.stack(embeddings).astype(np.float32)

    OUT_EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUT_EMB_PATH, embeddings)

    meta_df = pd.DataFrame(records)
    meta_df.to_csv(OUT_META_PATH, index=False)

    print(f"Saved embeddings array {embeddings.shape} to {OUT_EMB_PATH}")
    print(f"Saved metadata ({len(meta_df)} rows) to {OUT_META_PATH}")
    print(f"Test split size in {CSV_PATH.name}: {len(test_df)}")

    assert embeddings.shape[0] == len(test_df), (
        "Embedding count does not match test split size!"
    )
    print("OK: embeddings.shape[0] matches number of test images.")


if __name__ == "__main__":
    build_test_embeddings()

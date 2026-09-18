"""
Cow muzzle identification -- transfer learning with a ResNet-50 backbone.

WHAT THIS SCRIPT DOES (for judges / explanation):

  Backbone:  timm's resnet50, pretrained on ImageNet. It already knows how
             to extract general visual features (edges, textures, shapes)
             from photos, so we reuse it instead of learning from scratch.

  Head:      global average pool (built into the backbone) -> Linear(2048,512)
             "embedding" layer -> ReLU -> Linear(512, num_cows) "classifier".
             The 512-dim "embedding" layer is the reusable part: after
             training, we can chop off the final classifier and use the
             512-dim vector it produces as a muzzle "fingerprint" to compare
             two photos (e.g. cosine similarity), even for cows the model
             never saw labels for. That's the point of naming it explicitly.

  Phase 1 (head-only warmup): the pretrained backbone is FROZEN (no gradient
             updates), and only the new embedding+classifier layers are
             trained. This lets the randomly-initialized head catch up to
             the pretrained features quickly and cheaply, without the risk
             of a big gradient from an untrained head wrecking the
             pretrained backbone weights.

  Phase 2 (fine-tuning): we unfreeze just the LAST resnet block (layer4),
             which holds the most task-specific/high-level features, and
             keep training -- but with a much smaller learning rate on that
             block so we gently adapt it to muzzle prints instead of
             overwriting what it already learned from ImageNet. The head
             keeps training too, at its normal (higher) learning rate.

  Throughout, the best checkpoint (by validation accuracy, across both
  phases) is saved to ./models/resnet50_muzzle.pt.

RUNTIME: tuned for a free Google Colab T4 GPU to finish in ~30-45 minutes
  end-to-end (see CONFIG below). Uses mixed precision (AMP) to speed up
  ResNet-50 on the T4's tensor cores.
"""

import copy
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
SEED = 42

CSV_PATH = "data/splits.csv"
# If you copy/mount the dataset somewhere else on Colab (e.g. Google Drive),
# set DATA_ROOT to that folder and image_path values from the CSV (which are
# relative, e.g. "data/raw/cattle_0100/...jpg") will be resolved against it.
DATA_ROOT = "."

CKPT_DIR = Path("models")
CKPT_PATH = CKPT_DIR / "resnet50_muzzle.pt"

IMG_SIZE = 224
BATCH_SIZE = 64          # T4 (16GB) handles resnet50 @224 comfortably at this size with AMP
NUM_WORKERS = 2          # Colab typically gives 2 usable CPU cores

EMBEDDING_DIM = 512

# Phase 1: frozen backbone, head-only warmup.
PHASE1_EPOCHS = 6
PHASE1_LR = 1e-3

# Phase 2: unfreeze layer4, fine-tune everything above it.
PHASE2_EPOCHS = 10
PHASE2_HEAD_LR = 1e-4
PHASE2_BACKBONE_LR = 1e-5

# ~16 total epochs x ~50 train batches + ~10 val batches on a T4 with AMP
# comes out to roughly 30-40 minutes. Trim PHASE2_EPOCHS first if you're
# short on time -- phase 2 gives smaller returns per epoch than phase 1.

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# --------------------------------------------------------------------------
# DATA
# --------------------------------------------------------------------------
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

train_transform = transforms.Compose(
    [
        transforms.Resize((int(IMG_SIZE * 1.15), int(IMG_SIZE * 1.15))),
        transforms.RandomCrop(IMG_SIZE),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.25, contrast=0.25),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ]
)

eval_transform = transforms.Compose(
    [
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ]
)


class MuzzleDataset(Dataset):
    def __init__(self, df: pd.DataFrame, class_to_idx: dict, data_root: str, transform):
        self.paths = df["image_path"].tolist()
        self.labels = [class_to_idx[c] for c in df["cow_id"].tolist()]
        self.data_root = Path(data_root)
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img_path = self.data_root / self.paths[idx]
        image = Image.open(img_path).convert("RGB")
        image = self.transform(image)
        label = self.labels[idx]
        return image, label


def build_dataloaders():
    df = pd.read_csv(CSV_PATH)

    # Label mapping is built from the full manifest so it's identical and
    # stable across train/val/test (every cow appears in all three splits).
    classes = sorted(df["cow_id"].unique())
    class_to_idx = {c: i for i, c in enumerate(classes)}

    train_df = df[df["split"] == "train"].reset_index(drop=True)
    val_df = df[df["split"] == "val"].reset_index(drop=True)
    test_df = df[df["split"] == "test"].reset_index(drop=True)

    train_ds = MuzzleDataset(train_df, class_to_idx, DATA_ROOT, train_transform)
    val_ds = MuzzleDataset(val_df, class_to_idx, DATA_ROOT, eval_transform)
    test_ds = MuzzleDataset(test_df, class_to_idx, DATA_ROOT, eval_transform)

    train_loader = DataLoader(
        train_ds, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=True, drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=True,
    )
    test_loader = DataLoader(
        test_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=True,
    )

    return train_loader, val_loader, test_loader, classes


# --------------------------------------------------------------------------
# MODEL
# --------------------------------------------------------------------------
class MuzzleIDNet(nn.Module):
    """
    ResNet-50 backbone (pretrained, pooled features) -> embedding -> classifier.

    `embedding` is the layer to hook later for feature extraction: run an
    image through `self.backbone` + `self.embedding` (skip `self.classifier`)
    to get a 512-dim muzzle fingerprint for similarity / retrieval use cases.
    """

    def __init__(self, num_classes: int, embedding_dim: int = EMBEDDING_DIM):
        super().__init__()
        # num_classes=0 strips timm's default classifier and returns the
        # globally-average-pooled 2048-dim feature vector instead of logits.
        self.backbone = timm.create_model("resnet50", pretrained=True, num_classes=0)
        backbone_out_dim = self.backbone.num_features  # 2048 for resnet50

        self.embedding = nn.Linear(backbone_out_dim, embedding_dim)
        self.relu = nn.ReLU(inplace=True)
        self.classifier = nn.Linear(embedding_dim, num_classes)

    def forward(self, x):
        features = self.backbone(x)          # (B, 2048) pooled features
        embedding = self.relu(self.embedding(features))  # (B, 512) fingerprint
        logits = self.classifier(embedding)   # (B, num_classes)
        return logits

    def extract_embedding(self, x):
        """Convenience method for later use: image -> 512-dim fingerprint."""
        with torch.no_grad():
            features = self.backbone(x)
            embedding = self.relu(self.embedding(features))
        return embedding


def freeze_backbone(model: MuzzleIDNet) -> None:
    for p in model.backbone.parameters():
        p.requires_grad = False


def unfreeze_last_block(model: MuzzleIDNet) -> None:
    """Unfreeze only layer4 (the final resnet stage) for phase-2 fine-tuning."""
    for name, p in model.backbone.named_parameters():
        if name.startswith("layer4"):
            p.requires_grad = True


# --------------------------------------------------------------------------
# TRAIN / EVAL LOOPS
# --------------------------------------------------------------------------
def run_epoch(model, loader, criterion, optimizer, scaler, train: bool):
    model.train() if train else model.eval()

    total_loss, total_correct, total_samples = 0.0, 0, 0

    for images, labels in loader:
        images = images.to(DEVICE, non_blocking=True)
        labels = labels.to(DEVICE, non_blocking=True)

        if train:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(train):
            with torch.cuda.amp.autocast(enabled=(DEVICE.type == "cuda")):
                logits = model(images)
                loss = criterion(logits, labels)

            if train:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

        batch_size = images.size(0)
        total_loss += loss.item() * batch_size
        total_correct += (logits.argmax(dim=1) == labels).sum().item()
        total_samples += batch_size

    avg_loss = total_loss / total_samples
    accuracy = total_correct / total_samples
    return avg_loss, accuracy


def train_phase(model, train_loader, val_loader, optimizer, num_epochs,
                 phase_name, best_val_acc, best_state):
    criterion = nn.CrossEntropyLoss()
    scaler = torch.cuda.amp.GradScaler(enabled=(DEVICE.type == "cuda"))

    for epoch in range(1, num_epochs + 1):
        start = time.time()

        train_loss, train_acc = run_epoch(
            model, train_loader, criterion, optimizer, scaler, train=True
        )
        val_loss, val_acc = run_epoch(
            model, val_loader, criterion, optimizer, scaler, train=False
        )

        elapsed = time.time() - start
        print(
            f"[{phase_name}] epoch {epoch}/{num_epochs} "
            f"({elapsed:.0f}s) | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = copy.deepcopy(model.state_dict())
            print(f"  -> new best val_acc={best_val_acc:.4f}, checkpoint updated")

    return best_val_acc, best_state


def main():
    set_seed(SEED)
    CKPT_DIR.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader, classes = build_dataloaders()
    num_classes = len(classes)
    print(f"Loaded {num_classes} cow classes | "
          f"train={len(train_loader.dataset)} val={len(val_loader.dataset)} "
          f"test={len(test_loader.dataset)}")
    print(f"Device: {DEVICE}")

    model = MuzzleIDNet(num_classes=num_classes).to(DEVICE)

    best_val_acc = -1.0
    best_state = None

    # ---------------- Phase 1: frozen backbone, head-only warmup ----------
    freeze_backbone(model)
    head_params = list(model.embedding.parameters()) + list(model.classifier.parameters())
    optimizer = torch.optim.Adam(head_params, lr=PHASE1_LR)

    best_val_acc, best_state = train_phase(
        model, train_loader, val_loader, optimizer,
        PHASE1_EPOCHS, "phase1-head", best_val_acc, best_state,
    )

    # ---------------- Phase 2: unfreeze layer4, fine-tune ------------------
    unfreeze_last_block(model)
    optimizer = torch.optim.Adam(
        [
            {"params": model.backbone.layer4.parameters(), "lr": PHASE2_BACKBONE_LR},
            {"params": head_params, "lr": PHASE2_HEAD_LR},
        ]
    )

    best_val_acc, best_state = train_phase(
        model, train_loader, val_loader, optimizer,
        PHASE2_EPOCHS, "phase2-finetune", best_val_acc, best_state,
    )

    # ---------------- Save best checkpoint ----------------------------------
    torch.save(
        {
            "model_state_dict": best_state,
            "classes": classes,               # index -> cow_id mapping (sorted list)
            "num_classes": num_classes,
            "embedding_dim": EMBEDDING_DIM,
            "img_size": IMG_SIZE,
            "best_val_acc": best_val_acc,
        },
        CKPT_PATH,
    )
    print(f"Saved best checkpoint (val_acc={best_val_acc:.4f}) to {CKPT_PATH}")

    # ---------------- Final test-set check with the best weights -----------
    model.load_state_dict(best_state)
    criterion = nn.CrossEntropyLoss()
    scaler = torch.cuda.amp.GradScaler(enabled=(DEVICE.type == "cuda"))
    test_loss, test_acc = run_epoch(
        model, test_loader, criterion, optimizer, scaler, train=False
    )
    print(f"Test set: loss={test_loss:.4f} acc={test_acc:.4f}")

if __name__ == "__main__":
    main()

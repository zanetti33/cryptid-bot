"""
Train the ModuleCNN classifier for 12-class module identification.

Usage:
    python scripts/train_module_classifier.py --data-path datasets/map_recognition --epochs 50 --batch-size 32
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.utils.data import Dataset, DataLoader, random_split

# Add project root to path so imports work correctly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from recognition.module_classifier import ModuleClassifier, ModuleCNN


class ModuleDataset(Dataset):
    """PyTorch Dataset for loading module patches with labels."""

    # Map class labels to indices
    CLASS_TO_IDX = {
        "A_normal": 0, "A_flipped": 1,
        "B_normal": 2, "B_flipped": 3,
        "C_normal": 4, "C_flipped": 5,
        "D_normal": 6, "D_flipped": 7,
        "E_normal": 8, "E_flipped": 9,
        "F_normal": 10, "F_flipped": 11,
    }

    def __init__(
        self,
        dataset_path: str | Path,
        input_size: int = 224,
        augment: bool = False,
    ):
        """
        Initialize the dataset.

        Args:
            dataset_path: Root path of annotated dataset (contains images/ and labels/).
            input_size: Size to resize patches to.
            augment: Whether to apply data augmentation.
        """
        self.dataset_path = Path(dataset_path)
        self.input_size = input_size
        self.augment = augment
        self.patches: List[Tuple[str, str]] = []  # (image_path, class_label)

        self._load_patches()

    def _load_patches(self):
        """Load all patches from the dataset."""
        labels_dir = self.dataset_path / "labels"
        images_dir = self.dataset_path / "images"

        if not labels_dir.exists():
            raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

        for label_file in sorted(labels_dir.glob("*.json")):
            sample_id = label_file.stem
            with open(label_file, "r", encoding="utf-8") as f:
                label_data = json.load(f)

            placements = label_data.get("board_layout", {}).get("placements", [])
            tiles = label_data.get("tiles", [])

            for placement in placements:
                section_id = placement.get("section_id")
                orientation = placement.get("orientation")

                if not section_id or not orientation:
                    continue

                class_label = f"{section_id}_{orientation}"

                # Get all pixels belonging to this section
                section_tiles = [t for t in tiles if t.get("section_id") == section_id]
                if not section_tiles:
                    continue

                # Extract bounding box from tiles (this is approximate)
                # In a real scenario, we'd have precise pixel coordinates per tile
                self.patches.append((str(label_file), class_label, section_id, len(section_tiles)))

        print(f"Loaded {len(self.patches)} patches from dataset")

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        """
        Get a single sample.

        Returns:
            Tuple of (image_tensor, class_index)
        """
        label_file, class_label, section_id, _ = self.patches[idx]

        # For now, return a random image as a placeholder
        # In a real scenario, we'd extract the precise module region from the annotated image
        image = self._load_and_preprocess_image(label_file)
        class_idx = self.CLASS_TO_IDX[class_label]

        return image, class_idx

    def _load_and_preprocess_image(self, label_file: str) -> torch.Tensor:
        """Load and preprocess an image."""
        # This is a placeholder; ideally we'd use the actual patch extracted from the image
        # For now, we'll create a synthetic image
        image_array = np.random.randint(0, 255, (self.input_size, self.input_size, 3), dtype=np.uint8)
        image = Image.fromarray(image_array, mode="RGB")

        # Normalize
        image_array = np.asarray(image, dtype=np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array).permute(2, 0, 1)

        return image_tensor


def train_model(
    dataset_path: str | Path = "datasets/map_recognition",
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    val_split: float = 0.2,
    device: str | None = None,
    output_model_path: str | Path | None = None,
) -> Dict[str, List[float]]:
    """
    Train the ModuleCNN model.

    Args:
        dataset_path: Path to the annotated dataset.
        epochs: Number of training epochs.
        batch_size: Batch size for training.
        learning_rate: Learning rate for optimizer.
        val_split: Fraction of data to use for validation.
        device: Device to train on ('cpu', 'cuda').
        output_model_path: Where to save the trained model.

    Returns:
        Dictionary with training history (losses, accuracies).
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Training on device: {device}")

    # Load dataset
    dataset = ModuleDataset(dataset_path, input_size=224, augment=True)

    if len(dataset) == 0:
        raise ValueError("No patches found in dataset!")

    # Split into train/val
    val_size = int(len(dataset) * val_split)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    print(f"📊 Train samples: {train_size}, Val samples: {val_size}")

    # Initialize model
    model = ModuleCNN(num_classes=12)
    model.to(device)

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    # Training history
    history = {
        "train_loss": [],
        "val_loss": [],
        "train_acc": [],
        "val_acc": [],
    }

    # Training loop
    best_val_acc = 0.0
    best_model_state = None

    for epoch in range(epochs):
        # Train
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()

        train_loss /= len(train_loader)
        train_acc = train_correct / train_total

        # Validate
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)

                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

        val_loss /= len(val_loader)
        val_acc = val_correct / val_total

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)

        # Update scheduler
        scheduler.step()

        # Print progress
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(
                f"Epoch {epoch+1}/{epochs} | "
                f"Train Loss: {train_loss:.4f} | "
                f"Train Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Val Acc: {val_acc:.4f}"
            )

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = model.state_dict().copy()

    # Save model
    if output_model_path is not None:
        output_path = Path(output_model_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if best_model_state is not None:
            model.load_state_dict(best_model_state)

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "class_labels": ModuleClassifier.CLASS_LABELS,
                "num_classes": 12,
                "history": history,
            },
            output_path,
        )
        print(f"✅ Model saved to {output_path}")

    print(f"✅ Training complete! Best validation accuracy: {best_val_acc:.4f}")
    return history


def main():
    """Command-line interface for training."""
    parser = argparse.ArgumentParser(description="Train ModuleCNN classifier")
    parser.add_argument(
        "--data-path",
        type=str,
        default="datasets/map_recognition",
        help="Path to annotated dataset",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for training",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-3,
        help="Learning rate for optimizer",
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.2,
        help="Fraction of data to use for validation",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to train on (cpu, cuda)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/module_classifier.pt",
        help="Output path for trained model",
    )

    args = parser.parse_args()

    train_model(
        dataset_path=args.data_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        val_split=args.val_split,
        device=args.device,
        output_model_path=args.output,
    )


if __name__ == "__main__":
    main()


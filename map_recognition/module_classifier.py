"""
Module section classifier using a CNN model.

This module implements a neural network classifier that identifies the 12 possible
module variants (6 sections × 2 orientations) from image patches extracted from
the board screenshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.nn.functional import softmax

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True, slots=True)
class SectionModuleClassification:
    """Result of a single module classification."""
    section_id: str
    orientation: str
    confidence: float
    logits: np.ndarray  # 12-element array of raw scores

    @property
    def class_label(self) -> str:
        """Human-readable class label like 'A_normal', 'B_flipped', etc."""
        return f"{self.section_id}_{self.orientation}"


class ModuleCNN(nn.Module):
    """Convolutional neural network for 12-class module classification."""

    def __init__(self, num_classes: int = 12):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1, stride=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1, stride=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1, stride=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),

            nn.Conv2d(128, 256, kernel_size=3, padding=1, stride=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = x.flatten(1)
        x = self.classifier(x)
        return x


class ModuleClassifier:
    """
    Classifies image patches into 12 module classes (6 sections × 2 orientations).

    Attributes:
        model: The PyTorch CNN model.
        device: The device to run the model on (CPU or CUDA).
        class_labels: List of class labels in order (e.g., ['A_normal', 'A_flipped', ...]).
    """

    # Class labels in order (must match the trained model's output order)
    CLASS_LABELS = [
        "A_normal", "A_flipped",
        "B_normal", "B_flipped",
        "C_normal", "C_flipped",
        "D_normal", "D_flipped",
        "E_normal", "E_flipped",
        "F_normal", "F_flipped",
    ]
    NUM_CLASSES = 12

    def __init__(self, model_path: str | Path | None = None, device: str | None = None):
        """
        Initialize the classifier.

        Args:
            model_path: Path to the saved model weights. If None, a random model is used.
            device: Device to run the model on ('cpu', 'cuda', etc.). If None, auto-detects.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = ModuleCNN(num_classes=self.NUM_CLASSES)
        self.model.to(self.device)
        self.model.eval()

        if model_path is not None and Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, model_path: str | Path) -> None:
        """Load model weights from disk."""
        checkpoint = torch.load(model_path, map_location=self.device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            self.model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self.model.load_state_dict(checkpoint)

    def save_model(self, output_path: str | Path) -> None:
        """Save model weights to disk."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "class_labels": self.CLASS_LABELS,
                "num_classes": self.NUM_CLASSES,
            },
            output_path,
        )

    @staticmethod
    def _label_to_section_orientation(label: str) -> Tuple[str, str]:
        """Convert class label (e.g., 'A_normal') to (section_id, orientation)."""
        parts = label.split("_")
        if len(parts) != 2:
            raise ValueError(f"Invalid label format: {label}")
        return parts[0], parts[1]

    def classify_image(self, image_path: str | Path, input_size: int = 224) -> SectionModuleClassification:
        """
        Classify a single image patch.

        Args:
            image_path: Path to the image patch.
            input_size: Size to resize the image to (224x224 by default, standard for CNN).

        Returns:
            SectionModuleClassification with predicted section, orientation, and confidence.
        """
        image = Image.open(image_path).convert("RGB")
        image = image.resize((input_size, input_size), Image.LANCZOS)
        image_array = np.asarray(image, dtype=np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array).permute(2, 0, 1).unsqueeze(0)
        image_tensor = image_tensor.to(self.device)

        with torch.no_grad():
            logits = self.model(image_tensor)
            probabilities = softmax(logits, dim=1)

        pred_class_idx = logits.argmax(dim=1).item()
        confidence = probabilities[0, pred_class_idx].item()
        logits_np = logits[0].cpu().numpy()

        label = self.CLASS_LABELS[pred_class_idx]
        section_id, orientation = self._label_to_section_orientation(label)

        return SectionModuleClassification(
            section_id=section_id,
            orientation=orientation,
            confidence=confidence,
            logits=logits_np,
        )

    def classify_batch(
        self, image_paths: List[str | Path], input_size: int = 224
    ) -> List[SectionModuleClassification]:
        """
        Classify multiple image patches in a batch.

        Args:
            image_paths: List of paths to image patches.
            input_size: Size to resize images to.

        Returns:
            List of SectionModuleClassification results.
        """
        images_tensor_list = []
        for image_path in image_paths:
            image = Image.open(image_path).convert("RGB")
            image = image.resize((input_size, input_size), Image.LANCZOS)
            image_array = np.asarray(image, dtype=np.float32) / 255.0
            image_tensor = torch.from_numpy(image_array).permute(2, 0, 1)
            images_tensor_list.append(image_tensor)

        batch = torch.stack(images_tensor_list).to(self.device)

        with torch.no_grad():
            logits = self.model(batch)
            probabilities = softmax(logits, dim=1)

        results = []
        for idx in range(len(image_paths)):
            pred_class_idx = logits[idx].argmax(dim=0).item()
            confidence = probabilities[idx, pred_class_idx].item()
            logits_np = logits[idx].cpu().numpy()

            label = self.CLASS_LABELS[pred_class_idx]
            section_id, orientation = self._label_to_section_orientation(label)

            results.append(
                SectionModuleClassification(
                    section_id=section_id,
                    orientation=orientation,
                    confidence=confidence,
                    logits=logits_np,
                )
            )

        return results

    def classify_from_array(
        self, image_array: np.ndarray, input_size: int = 224
    ) -> SectionModuleClassification:
        """
        Classify from a numpy array (already loaded image).

        Args:
            image_array: Image as numpy array (shape: HxWx3, values 0-255 or 0-1).
            input_size: Size to resize the image to.

        Returns:
            SectionModuleClassification result.
        """
        # Ensure values are in [0, 1] range
        if image_array.max() > 1.0:
            image_array = image_array / 255.0

        # Convert to PIL Image for consistent resize behavior
        image_uint8 = (image_array * 255.0).astype(np.uint8)
        image = Image.fromarray(image_uint8, mode="RGB")
        image = image.resize((input_size, input_size), Image.LANCZOS)
        image_array = np.asarray(image, dtype=np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array).permute(2, 0, 1).unsqueeze(0)
        image_tensor = image_tensor.to(self.device)

        with torch.no_grad():
            logits = self.model(image_tensor)
            probabilities = softmax(logits, dim=1)

        pred_class_idx = logits.argmax(dim=1).item()
        confidence = probabilities[0, pred_class_idx].item()
        logits_np = logits[0].cpu().numpy()

        label = self.CLASS_LABELS[pred_class_idx]
        section_id, orientation = self._label_to_section_orientation(label)

        return SectionModuleClassification(
            section_id=section_id,
            orientation=orientation,
            confidence=confidence,
            logits=logits_np,
        )


"""
Unit tests for the ModuleCNN classifier.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from map_recognition.module_classifier import ModuleClassifier, ModuleCNN, SectionModuleClassification


class TestModuleCNN:
    """Tests for the ModuleCNN neural network."""

    def test_model_initialization(self):
        """Test that the model initializes with correct architecture."""
        model = ModuleCNN(num_classes=12)
        assert model is not None

        # Test forward pass with dummy input
        dummy_input = torch.randn(1, 3, 224, 224)
        output = model(dummy_input)
        assert output.shape == (1, 12)

    def test_model_moves_to_device(self):
        """Test that the model can be moved to different devices."""
        model = ModuleCNN(num_classes=12)

        # CPU
        model.to("cpu")
        assert next(model.parameters()).device.type == "cpu"

        # CUDA if available
        if torch.cuda.is_available():
            model.to("cuda")
            assert next(model.parameters()).device.type == "cuda"


class TestModuleClassifier:
    """Tests for the ModuleClassifier wrapper."""

    def test_classifier_initialization(self):
        """Test that classifier initializes correctly."""
        classifier = ModuleClassifier(model_path=None)
        assert classifier is not None
        assert len(classifier.CLASS_LABELS) == 12
        assert "A_normal" in classifier.CLASS_LABELS
        assert "F_flipped" in classifier.CLASS_LABELS

    def test_class_labels_are_correct(self):
        """Test that class labels are in the expected order."""
        expected_labels = [
            "A_normal", "A_flipped",
            "B_normal", "B_flipped",
            "C_normal", "C_flipped",
            "D_normal", "D_flipped",
            "E_normal", "E_flipped",
            "F_normal", "F_flipped",
        ]
        assert ModuleClassifier.CLASS_LABELS == expected_labels

    def test_label_to_section_orientation_conversion(self):
        """Test conversion between class labels and (section_id, orientation)."""
        section_id, orientation = ModuleClassifier._label_to_section_orientation("A_normal")
        assert section_id == "A"
        assert orientation == "normal"

        section_id, orientation = ModuleClassifier._label_to_section_orientation("F_flipped")
        assert section_id == "F"
        assert orientation == "flipped"

    def test_classify_from_array(self):
        """Test classification from numpy array."""
        classifier = ModuleClassifier(model_path=None)

        # Create a dummy image
        image_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)

        # Classify
        prediction = classifier.classify_from_array(image_array)

        assert isinstance(prediction, SectionModuleClassification)
        assert prediction.section_id in ["A", "B", "C", "D", "E", "F"]
        assert prediction.orientation in ["normal", "flipped"]
        assert 0.0 <= prediction.confidence <= 1.0
        assert len(prediction.logits) == 12

    def test_classify_batch(self):
        """Test batch classification."""
        classifier = ModuleClassifier(model_path=None)

        # Create temporary images
        with tempfile.TemporaryDirectory() as tmpdir:
            image_paths = []
            for i in range(3):
                image_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
                from PIL import Image
                image = Image.fromarray(image_array)
                path = Path(tmpdir) / f"test_{i}.png"
                image.save(path)
                image_paths.append(path)

            # Classify batch
            predictions = classifier.classify_batch(image_paths)

            assert len(predictions) == 3
            for pred in predictions:
                assert isinstance(pred, SectionModuleClassification)
                assert 0.0 <= pred.confidence <= 1.0

    def test_save_and_load_model(self):
        """Test saving and loading model weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"

            # Create and save a classifier
            classifier1 = ModuleClassifier(model_path=None)
            classifier1.save_model(model_path)

            assert model_path.exists()

            # Load the model
            classifier2 = ModuleClassifier(model_path=model_path)

            # Both should produce similar outputs for the same input
            image_array = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
            pred1 = classifier1.classify_from_array(image_array)
            pred2 = classifier2.classify_from_array(image_array)

            # They should have the same predicted class (assuming same input)
            assert pred1.section_id == pred2.section_id
            assert pred1.orientation == pred2.orientation


class TestSectionModuleClassification:
    """Tests for the SectionModuleClassification dataclass."""

    def test_classification_dataclass(self):
        """Test the SectionModuleClassification dataclass."""
        logits = np.array([0.1, 0.9, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05])

        classification = SectionModuleClassification(
            section_id="A",
            orientation="normal",
            confidence=0.9,
            logits=logits,
        )

        assert classification.section_id == "A"
        assert classification.orientation == "normal"
        assert classification.confidence == 0.9
        assert classification.class_label == "A_normal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image


@dataclass(slots=True)
class ExtractedTile:
    q: int
    r: int
    center: Tuple[int, int]
    rgb_mean: Tuple[int, int, int]


@dataclass(slots=True)
class ExtractedBoard:
    width: int
    height: int
    tiles: List[ExtractedTile]


def _estimate_board_bbox(rgb: np.ndarray) -> Tuple[int, int, int, int]:
    diff = rgb.max(axis=2) - rgb.min(axis=2)
    mask = diff > 20
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        h, w = rgb.shape[:2]
        return (0, 0, w - 1, h - 1)
    x0 = max(0, int(xs.min()) - 10)
    y0 = max(0, int(ys.min()) - 10)
    x1 = min(rgb.shape[1] - 1, int(xs.max()) + 10)
    y1 = min(rgb.shape[0] - 1, int(ys.max()) + 10)
    return (x0, y0, x1, y1)


def _sample_mean(rgb: np.ndarray, x: int, y: int, radius: int = 4) -> Tuple[int, int, int]:
    y0 = max(0, y - radius)
    y1 = min(rgb.shape[0], y + radius + 1)
    x0 = max(0, x - radius)
    x1 = min(rgb.shape[1], x + radius + 1)
    patch = rgb[y0:y1, x0:x1]
    mean = patch.mean(axis=(0, 1))
    return int(mean[0]), int(mean[1]), int(mean[2])


def normalize_lighting(rgb: np.ndarray) -> np.ndarray:
    rgb_float = rgb.astype(np.float32)

    # Gray-world balancing to reduce channel bias from ambient light.
    channel_means = rgb_float.reshape(-1, 3).mean(axis=0)
    target_mean = float(channel_means.mean())
    scales = np.ones(3, dtype=np.float32)
    valid = channel_means > 1e-6
    scales[valid] = target_mean / channel_means[valid]
    balanced = np.clip(rgb_float * scales, 0, 255)

    # Gentle contrast stretch per channel for low/high exposure shots.
    low = np.percentile(balanced, 1, axis=(0, 1))
    high = np.percentile(balanced, 99, axis=(0, 1))
    span = np.maximum(high - low, 1.0)
    normalized = np.clip((balanced - low) * 255.0 / span, 0, 255)
    return normalized.astype(np.uint8)


def extract_tiles(
    image_path: str | Path,
    cols: int = 12,
    rows: int = 9,
    normalize_light: bool = True,
) -> ExtractedBoard:
    image = Image.open(image_path).convert("RGB")
    rgb = np.asarray(image)
    sampling_rgb = normalize_lighting(rgb) if normalize_light else rgb
    x0, y0, x1, y1 = _estimate_board_bbox(rgb)

    width = max(1, x1 - x0)
    height = max(1, y1 - y0)

    # Approximate odd-r hex center distribution.
    dx = width / (cols + 0.5)
    dy = height / (rows + 0.25)

    tiles: List[ExtractedTile] = []
    for r in range(rows):
        for q in range(cols):
            x = x0 + int((q + 0.75 + (0.5 if r % 2 else 0.0)) * dx)
            y = y0 + int((r + 0.6) * dy)
            x = max(0, min(sampling_rgb.shape[1] - 1, x))
            y = max(0, min(sampling_rgb.shape[0] - 1, y))
            rgb_mean = _sample_mean(sampling_rgb, x, y)
            tiles.append(ExtractedTile(q=q, r=r, center=(x, y), rgb_mean=rgb_mean))

    return ExtractedBoard(width=rgb.shape[1], height=rgb.shape[0], tiles=tiles)


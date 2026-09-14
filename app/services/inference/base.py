"""The seam between the app and whatever actually classifies pixels.

Everything downstream (label mapping, triage, persistence) depends only on
``list[RawPrediction]``. Swapping the mock for a hosted vision API or a
self-hosted CNN means writing one new class, not touching the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawPrediction:
    label: str  # model-native label string, e.g. "eczema" or "nv"
    confidence: float  # 0..1


class InferenceAdapter(Protocol):
    name: str
    model_version: str

    def predict(self, image_bytes: bytes, *, context: dict) -> list[RawPrediction]:
        """Return predictions sorted by confidence descending.

        ``context`` may carry hints (body_site, questionnaire) that a real model
        could condition on; the mock ignores them.
        """
        ...

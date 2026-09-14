"""Deterministic stand-in classifier.

Same image bytes always yield the same predictions (hash-seeded), so demos and
tests are reproducible. It emits real-looking label strings drawn from the seed
condition vocabulary, including the occasional malignancy label so the triage
referral path is exercised.
"""

from __future__ import annotations

import hashlib
import random

from app.config import get_settings
from app.services.inference.base import RawPrediction

# Model-native labels -> must be resolvable via SkinCondition.slug or .aliases
_LABEL_POOL = [
    "acne_vulgaris",
    "atopic_dermatitis",
    "psoriasis",
    "rosacea",
    "seborrheic_dermatitis",
    "contact_dermatitis",
    "tinea_corporis",
    "urticaria",
    "melasma",
    "vitiligo",
    "benign_nevus",
    "actinic_keratosis",
    "wart",
    "cold_sore",
    "melanoma_suspected",  # referral trigger
    "basal_cell_carcinoma_suspected",  # referral trigger
]


class MockInferenceAdapter:
    name = "mock"

    def __init__(self) -> None:
        self.model_version = get_settings().model_version

    def predict(self, image_bytes: bytes, *, context: dict) -> list[RawPrediction]:
        seed = int.from_bytes(hashlib.sha256(image_bytes).digest()[:8], "big")
        rng = random.Random(seed)
        k = min(get_settings().top_k_predictions, len(_LABEL_POOL))
        labels = rng.sample(_LABEL_POOL, k)

        # Random but plausibly-shaped confidence vector, normalised, sorted desc.
        weights = sorted((rng.random() ** 2 for _ in labels), reverse=True)
        total = sum(weights) or 1.0
        return [
            RawPrediction(label=label, confidence=round(w / total, 4))
            for label, w in zip(labels, weights)
        ]

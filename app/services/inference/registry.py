from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.inference.base import InferenceAdapter


@lru_cache
def get_adapter(name: str | None = None) -> InferenceAdapter:
    name = name or get_settings().inference_adapter
    if name == "mock":
        from app.services.inference.mock import MockInferenceAdapter

        return MockInferenceAdapter()
    # Add real adapters here:
    #   if name == "hosted_vision": return HostedVisionAdapter()
    #   if name == "custom":        return CustomCNNAdapter()
    raise ValueError(f"unknown inference adapter: {name!r}")

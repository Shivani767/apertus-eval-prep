"""Model/system adapters for the evaluation platform."""
from .base import ModelAdapter, CompletionRequest, AdapterResponse
from .mock import MockAdapter, MockSkillProfile
from .local import LocalAdapter
from .local_transformers import LocalTransformersAdapter

__all__ = [
    "ModelAdapter", "CompletionRequest", "AdapterResponse", "MockAdapter", "MockSkillProfile",
    "LocalAdapter", "LocalTransformersAdapter",
]

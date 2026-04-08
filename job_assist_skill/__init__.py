"""Agent-friendly job search and CV tailoring skill."""

from . import keywords
from .assistant import CareerAssistant, PreferenceMemory

__all__ = [
    "CareerAssistant",
    "PreferenceMemory",
    "keywords",
]

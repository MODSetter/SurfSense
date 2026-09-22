"""What each model in a catalogue is for, so tabs never mix types."""

from modules.llm.taxonomy.classify import classify
from modules.llm.taxonomy.types import ModelType

__all__ = ["ModelType", "classify"]

"""MIRAGE — secondary single-arm SurfSense MCQ measurement.

Source: https://github.com/Teddy-XiongGZ/MIRAGE, paper
https://aclanthology.org/2024.findings-acl.372/. 7,663 questions
across MMLU-Med, MedQA-US, MedMCQA, PubMedQA*, BioASQ-Y/N.

This is a SurfSense-only measurement (not a head-to-head); native
PDF-in-LLM doesn't apply because there is no per-question discrete
document — the corpus is millions of biomedical snippets.
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import MirageBenchmark

_registry.register(MirageBenchmark())

"""MedXpertQA-MM — multimodal medical exam head-to-head (medical suite headline).

Source: https://huggingface.co/datasets/TsinghuaC3I/MedXpertQA
Paper:  https://arxiv.org/abs/2501.18362 (ICML 2025)

* MM subset: ~2,000 expert-level exam questions with diverse medical
  images (radiology, dermatology, pathology, ECGs, gross specimens,
  fundus photos) and structured patient information embedded in the
  question stem.
* 5 answer choices per MM question (A–E).
* USMLE / COMLEX / 17 specialty board sources; rigorously filtered
  and reviewed by physicians.

Real diagnostic images carry signal that text-only patient charts
cannot (e.g. CT scans, dermoscopy), so this benchmark exercises the
full vision RAG pipeline end-to-end against a vision-capable model
fed the same PDF natively.
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import MedXpertQAMMBenchmark

_registry.register(MedXpertQAMMBenchmark())

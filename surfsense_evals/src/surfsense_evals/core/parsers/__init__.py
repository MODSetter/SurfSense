"""Direct parser invocations for the parser_compare benchmark.

The SurfSense backend exposes a single ``ETL_SERVICE`` env var that
picks one parser globally; per-ingestion overrides are not on the
public API. To drive the four (Azure DI x basic/premium, LlamaCloud x
basic/premium) extractions we need for ``multimodal_doc/parser_compare``
we therefore call the Azure DI and LlamaCloud SDKs directly from the
eval harness, mirroring the production code path in
``surfsense_backend/app/etl_pipeline/parsers/``.

Two design rules:

* No backend imports — the eval harness cannot pull in the FastAPI
  app's config layer (it would require the full backend ``.env`` plus a
  reachable Postgres). We re-read keys from our own environment instead.
* Same wire shape as the backend's parsers (Azure ``prebuilt-read`` /
  ``prebuilt-layout`` selected by ``processing_mode``; LlamaCloud
  ``parse_page_with_llm`` / ``parse_page_with_agent`` selected by
  ``processing_mode``) so any quality conclusions transfer back to
  production behaviour.
"""

from __future__ import annotations

from .azure_di import AzureDIError, parse_with_azure_di
from .llamacloud import LlamaCloudError, parse_with_llamacloud
from .pdf_pages import count_pdf_pages

__all__ = [
    "AzureDIError",
    "LlamaCloudError",
    "count_pdf_pages",
    "parse_with_azure_di",
    "parse_with_llamacloud",
]

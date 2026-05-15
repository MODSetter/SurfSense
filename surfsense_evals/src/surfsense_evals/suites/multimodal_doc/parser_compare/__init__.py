"""parser_compare — six-way head-to-head on long multimodal PDFs.

Same 5 mmlongbench PDFs that ``mmlongbench`` already ingested
(``search_space_id=55``), one question per PDF for the smoke run.

The point of this benchmark is to disentangle TWO orthogonal
dimensions of "how good is our multimodal pipeline?":

1. **Parser quality** — Azure DI prebuilt-read vs prebuilt-layout vs
   LlamaParse parse_page_with_llm vs parse_page_with_agent. We run
   each parser directly (bypassing ``/documents/fileupload`` because
   the backend's parser routing is global, not per-call) and stuff the
   resulting markdown into a long-context prompt.

2. **Context-management strategy** — full-context stuffing (no chunk
   selection, the model sees everything) vs SurfSense's agentic
   retrieval over chunks of the same documents.

Six arms, all answered by ``anthropic/claude-sonnet-4.5``:

* ``native_pdf``           — PDF attached natively via OpenRouter
                              (gold-standard reference).
* ``azure_basic_lc``       — Azure DI ``prebuilt-read`` markdown stuffed
                              into the prompt.
* ``azure_premium_lc``     — Azure DI ``prebuilt-layout`` markdown stuffed.
* ``llamacloud_basic_lc``  — LlamaParse ``parse_page_with_llm`` markdown stuffed.
* ``llamacloud_premium_lc`` — LlamaParse ``parse_page_with_agent`` markdown stuffed.
* ``surfsense_agentic``    — SurfSense ``/api/v1/new_chat`` with
                              ``mentioned_document_ids`` scoped to the
                              one source PDF, retrieving chunks from
                              the existing search_space=55 ingestion
                              (vision_llm=on, processing_mode=premium,
                              ETL_SERVICE=LLAMACLOUD with Azure DI
                              fallback ⇒ effectively azure_premium).

The report includes preprocessing cost ($1 / 1k pages basic, $10 / 1k
pages premium) on top of the OpenRouter LLM cost so each arm's true
total-cost-per-question is directly comparable.
"""

from __future__ import annotations

from ....core import registry as _registry
from .runner import ParserCompareBenchmark

_registry.register(ParserCompareBenchmark())

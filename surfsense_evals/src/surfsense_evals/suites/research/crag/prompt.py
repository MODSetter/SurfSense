"""CRAG prompt templates for the three competing arms.

The CRAG paper grades each prediction as one of:

* **correct**   — answer matches gold (with paraphrasing tolerance)
* **missing**   — model refuses or says "I don't know"
* **incorrect** — model commits to a wrong answer (hallucination)

The truthfulness score `(correct - incorrect) / total` rewards
calibrated abstention, so the prompts below explicitly *invite* the
model to refuse when it isn't confident — otherwise the bare-LLM arm
gets penalised twice (no docs *and* a no-refusal prompt) and the
comparison stops being fair to the LLM-only baseline.

Three templates, byte-identical instructions:

* ``build_bare_prompt(q)``         — question-only.
* ``build_long_context_prompt(q, contexts)`` — question + concatenated
  page extracts, all stuffed into the user message. Mirrors the
  paper's "straightforward RAG" baseline.
* ``build_surfsense_prompt(q)``    — question + a hint that retrieval
  over the question's 5 ingested pages is available; the SurfSense
  agent itself owns the retrieval step.

The ``Answer:`` line at the end is parsed by ``extract_freeform_answer``
in the runner, so the format is mandatory.
"""

from __future__ import annotations

_BASE_INSTRUCTIONS = (
    "You are a careful question-answering assistant. The question is a "
    "real-world factual question that may be about finance, music, "
    "movies, sports, or any other domain.\n\n"
    "Important rules:\n"
    "1. If the question contains a false premise (an assumption that "
    "is factually wrong), say so explicitly in your final answer "
    "rather than answering as if the premise were true.\n"
    "2. If you are not confident in an answer, prefer saying \"I don't "
    "know\" over guessing. A wrong commit is penalised more than a "
    "refusal.\n"
    "3. Keep the final answer short — a name, a number, a date, a "
    "phrase. Do not repeat the question.\n\n"
    "Format your final line EXACTLY as:\n"
    "Answer: <short answer>\n"
    "If you don't know, write `Answer: I don't know`."
)


_BARE_TEMPLATE = """\
{instructions}

Question: {question}
Question time: {query_time}
"""


_SURFSENSE_TEMPLATE = """\
{instructions}

You have access to a search index of up to 5 web pages that were
retrieved for this question. Use the retrieval tool to look up any
facts you are not confident about. The pages may be partially or fully
relevant; some may contradict each other (prefer the more authoritative
or more recent source).

Question: {question}
Question time: {query_time}
"""


_LONG_CONTEXT_TEMPLATE = """\
{instructions}

You are given the full text of {n_contexts} web pages that were
retrieved for this question. Read all of them, then answer. The
pages may be partially or fully relevant; some may contradict each
other (prefer the more authoritative or more recent source).

{contexts}

Question: {question}
Question time: {query_time}
"""


def build_bare_prompt(question: str, *, query_time: str = "") -> str:
    """Prompt for the no-retrieval baseline arm."""

    return _BARE_TEMPLATE.format(
        instructions=_BASE_INSTRUCTIONS,
        question=question.strip(),
        query_time=query_time.strip() or "unknown",
    )


def build_surfsense_prompt(question: str, *, query_time: str = "") -> str:
    """Prompt for the SurfSense arm (agent does retrieval itself)."""

    return _SURFSENSE_TEMPLATE.format(
        instructions=_BASE_INSTRUCTIONS,
        question=question.strip(),
        query_time=query_time.strip() or "unknown",
    )


def build_long_context_prompt(
    question: str,
    *,
    contexts: list[tuple[str, str]],
    query_time: str = "",
    per_page_char_cap: int = 12_000,
) -> str:
    """Prompt for the "stuff all pages into the prompt" baseline.

    ``contexts`` is a list of ``(page_title_or_url, page_text)`` pairs.
    Each page is truncated at ``per_page_char_cap`` (default 12k chars
    ≈ 3k tokens) so a 5-page CRAG question fits well under any
    modern long-context window with room for the question + reasoning.
    """

    blocks: list[str] = []
    for idx, (title, text) in enumerate(contexts, start=1):
        body = (text or "").strip()
        if len(body) > per_page_char_cap:
            body = body[:per_page_char_cap].rstrip() + "\n[...truncated...]"
        title_clean = (title or f"page_{idx}").strip().replace("\n", " ")
        blocks.append(
            f"--- PAGE {idx}: {title_clean} ---\n{body}\n"
        )
    contexts_block = "\n".join(blocks) if blocks else "(no pages retrieved)"
    return _LONG_CONTEXT_TEMPLATE.format(
        instructions=_BASE_INSTRUCTIONS,
        n_contexts=len(contexts),
        contexts=contexts_block,
        question=question.strip(),
        query_time=query_time.strip() or "unknown",
    )


__all__ = [
    "build_bare_prompt",
    "build_long_context_prompt",
    "build_surfsense_prompt",
]

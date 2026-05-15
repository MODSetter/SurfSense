"""Native-PDF arm: drop the PDF straight into OpenRouter chat-completions.

Generic across suites — a benchmark just supplies the prompt and the
single PDF path. Multi-PDF questions concatenate in the runner before
calling this arm so each ``answer`` invocation feeds the model exactly
one ``data:application/pdf;base64,...`` block (matches the human
"drag-and-drop one PDF into Claude" intent).
"""

from __future__ import annotations

import logging

from ..parse.answer_letter import extract_answer_letter
from ..providers.openrouter_pdf import OpenRouterPdfProvider, PdfEngine
from .base import Arm, ArmRequest, ArmResult

logger = logging.getLogger(__name__)


class NativePdfArm(Arm):
    """``Arm`` implementation backed by ``OpenRouterPdfProvider``."""

    name: str = "native_pdf"

    def __init__(
        self,
        *,
        provider: OpenRouterPdfProvider,
        max_output_tokens: int | None = 1024,
    ) -> None:
        self._provider = provider
        self._max_output = max_output_tokens

    @classmethod
    def from_env(
        cls,
        *,
        api_key: str,
        model: str,
        engine: PdfEngine = PdfEngine.NATIVE,
        base_url: str = "https://openrouter.ai/api/v1",
        max_output_tokens: int | None = 1024,
    ) -> NativePdfArm:
        provider = OpenRouterPdfProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            engine=engine,
        )
        return cls(provider=provider, max_output_tokens=max_output_tokens)

    async def answer(self, request: ArmRequest) -> ArmResult:
        if not request.pdf_paths:
            return ArmResult(
                arm=self.name,
                question_id=request.question_id,
                raw_text="",
                error="native_pdf arm requires at least one pdf_path",
            )
        if len(request.pdf_paths) > 1:
            # The plan calls out one-PDF-per-question so the head-to-head
            # is fair; runners are responsible for upstream concatenation.
            logger.debug(
                "qid=%s native_pdf got %d pdfs; using first only",
                request.question_id,
                len(request.pdf_paths),
            )
        pdf = request.pdf_paths[0]
        try:
            response = await self._provider.complete(
                prompt=request.prompt,
                pdf_path=pdf,
                max_tokens=self._max_output,
            )
        except Exception as exc:  # noqa: BLE001
            return ArmResult(
                arm=self.name,
                question_id=request.question_id,
                raw_text="",
                error=f"{type(exc).__name__}: {exc}",
            )

        letter = extract_answer_letter(response.text)
        return ArmResult(
            arm=self.name,
            question_id=request.question_id,
            raw_text=response.text,
            answer_letter=letter.letter,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_micros=response.cost_micros,
            latency_ms=response.latency_ms,
            extra={
                "model": self._provider.model,
                "engine": self._provider.engine.value,
                "answer_letter_strategy": letter.strategy,
                "finish_reason": response.finish_reason,
                "pdf_filename": pdf.name,
            },
        )


__all__ = ["NativePdfArm"]

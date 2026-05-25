"""Emit the per-turn token-usage SSE frame from the accumulator.

``per_message_summary()`` returns ``None`` when the turn made no chargeable
LLM calls (e.g. interrupt-on-input). In that case we skip the frame; the
frontend has no usage to render.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.new_streaming_service import VercelStreamingService
from app.utils.perf import get_perf_logger

if TYPE_CHECKING:
    from app.services.token_tracking_service import TokenAccumulator

_perf_log = get_perf_logger()
logger = logging.getLogger(__name__)


def iter_token_usage_frame(
    streaming_service: VercelStreamingService,
    *,
    accumulator: TokenAccumulator,
    log_label: str,
):
    """Yield zero or one ``data: token-usage`` SSE frame.

    Side effect: logs a one-line ``[token_usage] {log_label}: ...`` summary so
    cost analysis can grep call/total/cost across all flows.
    """
    usage_summary = accumulator.per_message_summary()
    _perf_log.info(
        "[token_usage] %s: calls=%d total=%d cost_micros=%d summary=%s",
        log_label,
        len(accumulator.calls),
        accumulator.grand_total,
        accumulator.total_cost_micros,
        usage_summary,
    )
    if usage_summary:
        yield streaming_service.format_data(
            "token-usage",
            {
                "usage": usage_summary,
                "prompt_tokens": accumulator.total_prompt_tokens,
                "completion_tokens": accumulator.total_completion_tokens,
                "total_tokens": accumulator.grand_total,
                "cost_micros": accumulator.total_cost_micros,
                "call_details": accumulator.serialized_calls(),
            },
        )

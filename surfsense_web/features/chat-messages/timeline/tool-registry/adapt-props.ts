import type { ToolCallItem } from "../types";
import type { TimelineToolProps } from "./types";

/**
 * Lossless mapping ``ToolCallItem → TimelineToolProps``. Pure;
 * extracts only the fields tool components actually consume.
 *
 * ``id``, ``kind``, ``spanId``, ``thinkingStepId`` are intentionally
 * dropped — they're timeline-internal concerns (React key, dispatch,
 * indentation, back-correlation) that tool components have no reason to
 * see. ``items`` is forwarded as ``progress`` so a tool body can show its
 * live activity (e.g. streamed scraper progress) inside its own card.
 */
export function adaptItemToProps(item: ToolCallItem): TimelineToolProps {
	return {
		toolCallId: item.toolCallId,
		toolName: item.toolName,
		args: item.args,
		argsText: item.argsText,
		result: item.result,
		langchainToolCallId: item.langchainToolCallId,
		status: item.status,
		progress: item.items,
	};
}

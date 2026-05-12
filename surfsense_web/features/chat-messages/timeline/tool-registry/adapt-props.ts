import type { ToolCallItem } from "../types";
import type { TimelineToolProps } from "./types";

/**
 * Lossless mapping ``ToolCallItem → TimelineToolProps``. Pure;
 * extracts only the fields tool components actually consume.
 *
 * ``id``, ``kind``, ``items``, ``spanId``, ``thinkingStepId`` are
 * intentionally dropped — they're timeline-internal concerns (React
 * key, dispatch, indentation, back-correlation) that tool components
 * have no reason to see.
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
	};
}

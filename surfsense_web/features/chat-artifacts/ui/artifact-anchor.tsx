import type { ToolCallMessagePartComponent, ToolCallMessagePartProps } from "@assistant-ui/react";
import { ARTIFACT_ANCHOR_ATTR } from "../lib/scroll-to-artifact";

/**
 * Wrap a body tool component so its rendered card carries a DOM anchor keyed by
 * tool call id. The artifacts sidebar uses it to scroll a deliverable back into
 * view. The wrapper is layout-neutral — the card keeps its own margins.
 */
export function withArtifactAnchor(
	Tool: ToolCallMessagePartComponent
): ToolCallMessagePartComponent {
	function AnchoredTool(props: ToolCallMessagePartProps) {
		return (
			<div {...{ [ARTIFACT_ANCHOR_ATTR]: props.toolCallId }}>
				<Tool {...props} />
			</div>
		);
	}
	return AnchoredTool;
}

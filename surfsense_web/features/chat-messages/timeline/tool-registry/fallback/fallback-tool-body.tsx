"use client";

import {
	DoomLoopApproval,
	GenericHitlApproval,
	type InterruptResult,
	isDoomLoopInterrupt,
	isInterruptResult,
} from "@/features/chat-messages/hitl";
import type { TimelineToolComponent } from "../types";
import { DefaultFallbackCard } from "./default-fallback-card";

/**
 * Mounted by the timeline for any tool name not in the registry. The
 * fallback owns the inner discrimination between HITL approval cards
 * and the default visual card:
 *
 *   isInterruptResult(result) ─┬─ isDoomLoopInterrupt → DoomLoopApproval
 *                              └─ otherwise           → GenericHitlApproval
 *   else                                              → DefaultFallbackCard
 *
 * This is the ONLY place ``isInterruptResult`` is checked for unknown
 * tools. Per-tool components in ``components/tool-ui/*`` perform their
 * own internal discrimination over richer result shapes; the fallback
 * only knows the two top-level branches.
 */
export const FallbackToolBody: TimelineToolComponent = (props) => {
	if (isInterruptResult(props.result)) {
		const approvalProps = {
			toolCallId: props.toolCallId,
			toolName: props.toolName,
			args: props.args,
			result: props.result as InterruptResult,
		};
		if (isDoomLoopInterrupt(props.result)) {
			return <DoomLoopApproval {...approvalProps} />;
		}
		return <GenericHitlApproval {...approvalProps} />;
	}
	return <DefaultFallbackCard {...props} />;
};

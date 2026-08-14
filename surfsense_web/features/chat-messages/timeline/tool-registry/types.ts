import type { ReactNode } from "react";
import type { ItemStatus } from "../types";

/**
 * The exact prop subset the HITL approval surface supplies when mounting a
 * tool component. A strict subset of assistant-ui's
 * ``ToolCallMessagePartProps`` — only the fields we actually have when
 * rendering a pending approval action.
 *
 * Notably absent vs. assistant-ui:
 * - ``addResult`` / ``resume`` (runtime-only, not available to us)
 * - The complex ``status: ToolCallMessagePartState["status"]`` object
 *   (replaced by our simple ``ItemStatus`` enum)
 * - ``messageId`` and other parent-message context (not needed by any
 *   of the 15 HITL-aware tool-ui components today)
 */
export interface TimelineToolProps {
	toolCallId: string;
	toolName: string;
	args: Record<string, unknown>;
	argsText?: string;
	result?: unknown;
	langchainToolCallId?: string;
	status: ItemStatus;
}

/**
 * Contract for tool components mounted by the HITL approval card.
 *
 * Components are expected to perform internal discrimination on
 * ``result`` to pick a view (interrupt → approval card; success →
 * result card; etc.) — see §2.2 of the architecture doc.
 */
export type TimelineToolComponent = (props: TimelineToolProps) => ReactNode;

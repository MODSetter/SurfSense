/**
 * Indent tool-call cards that belong to an open delegating ``task`` episode.
 *
 * The backend only stamps ``metadata.spanId`` on tool SSE / persisted parts
 * while a ``task`` is active (see ``AgentEventRelayState.tool_activity_metadata``),
 * so its presence is sufficient. The opening ``task`` row itself carries the
 * same span id but stays flush — it is the header of the delegation.
 */

export function shouldIndentToolCallForDelegationSpan(
	toolName: string,
	metadata: Record<string, unknown> | undefined
): boolean {
	if (toolName === "task") return false;
	const v = metadata?.spanId;
	return typeof v === "string" && v.trim().length > 0;
}

export const DELEGATION_SPAN_INDENT_CLASS = "pl-3 sm:ml-4";

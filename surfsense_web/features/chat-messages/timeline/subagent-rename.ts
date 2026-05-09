import type { TimelineItem, ToolCallItem } from "./types";

function asNonEmptyString(v: unknown): string | undefined {
	return typeof v === "string" && v.trim().length > 0 ? v.trim() : undefined;
}

/**
 * Title-case a subagent identifier:
 *   "notion"        → "Notion"
 *   "doc_research"  → "Doc Research"
 *   "ux-review"     → "Ux Review"
 */
export function titleCaseSubagent(raw: string): string {
	return raw
		.split(/[\s_-]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

/**
 * Display title for a tool-call item. For the ``task`` delegation
 * primitive, substitute ``args.subagent_type`` (e.g. "Notion" instead
 * of the generic "Task" label). Returns ``undefined`` if no rename
 * applies — caller falls back to ``getToolDisplayName(toolName)``.
 */
export function resolveSubagentTitle(item: ToolCallItem): string | undefined {
	if (item.toolName !== "task") return undefined;
	const subagent = asNonEmptyString(item.args?.subagent_type);
	return subagent ? titleCaseSubagent(subagent) : undefined;
}

/**
 * Unified title resolver for any timeline item. Reasoning items use
 * their own ``title``; tool-call items try the subagent rename first,
 * then fall back to the resolver passed in (typically
 * ``getToolDisplayName``).
 *
 * Pure: no React, no I/O. Trivially testable.
 */
export function resolveItemTitle(
	item: TimelineItem,
	getToolDisplayName: (toolName: string) => string
): string {
	if (item.kind === "reasoning") return item.title;
	return resolveSubagentTitle(item) ?? getToolDisplayName(item.toolName);
}

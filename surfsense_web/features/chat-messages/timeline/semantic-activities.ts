import { getToolCategory, getToolVisibility } from "./presentation";
import type { ItemStatus, TimelineItem, ToolCallItem } from "./types";

function artifactLabel(item: ToolCallItem): string {
	return item.safeDetail?.filename ?? item.context?.artifactType ?? "artifact";
}

type DeliverablePhase = "skill" | "draft" | "build" | "verify" | "inspect" | "persist" | "author";

function deliverablePhase(item: ToolCallItem): DeliverablePhase | undefined {
	if (item.context?.subagentType !== "deliverables") return undefined;
	if (item.context.intent === "discover_skill") return "skill";
	if (item.context.intent === "verify") return "verify";
	if (item.context.intent === "persist") return "persist";
	if (item.context.intent === "inspect") return "inspect";
	if (item.context.intent !== "author") return undefined;
	if (item.toolName === "write_file" || item.toolName === "edit_file") return "draft";
	if (item.toolName === "execute" || item.toolName === "execute_code") return "build";
	return "author";
}

function semanticKey(item: ToolCallItem): string | undefined {
	const phase = deliverablePhase(item);
	if (phase === "skill") return `deliverable:skill:${item.context?.skillName ?? "artifact"}`;
	if (phase) return `deliverable:${phase}:${artifactLabel(item)}`;
	if (getToolVisibility(item.toolName) === "aggregate") {
		return `aggregate:${getToolCategory(item.toolName)}:${item.toolName}`;
	}
	return undefined;
}

function withSemanticTitle(item: ToolCallItem): ToolCallItem {
	const phase = deliverablePhase(item);
	if (!phase) {
		if (
			getToolVisibility(item.toolName) === "aggregate" &&
			getToolCategory(item.toolName) === "research"
		) {
			return {
				...item,
				activeTitle: "Reviewing sources",
				completedTitle: "Reviewed sources",
			};
		}
		return item;
	}

	const artifact = artifactLabel(item);
	const skill = item.context?.skillName?.toUpperCase() ?? "artifact";
	const titles = {
		skill: [`Finding the ${skill} creation skill`, `Found the ${skill} creation skill`],
		draft: [`Drafting the ${artifact}`, `Drafted the ${artifact}`],
		build: [`Building the ${artifact}`, `Built the ${artifact}`],
		verify: [`Checking the ${artifact}`, `Checked the ${artifact}`],
		inspect: [`Reviewing the ${artifact}`, `Reviewed the ${artifact}`],
		persist: ["Preparing the file", "Presented file"],
		author: [`Creating the ${artifact}`, `Created the ${artifact}`],
	} satisfies Record<DeliverablePhase, [string, string]>;
	const [activeTitle, completedTitle] = titles[phase];
	return { ...item, activeTitle, completedTitle };
}

function mergedStatus(left: ItemStatus, right: ItemStatus): ItemStatus {
	const statuses = new Set([left, right]);
	if (statuses.has("awaiting_approval")) return "awaiting_approval";
	if (statuses.has("running")) return "running";
	if (statuses.has("pending")) return "pending";
	if (statuses.has("error")) return "error";
	if (statuses.has("cancelled")) return "cancelled";
	if (statuses.has("interrupted")) return "interrupted";
	return "completed";
}

/**
 * Converts the raw execution journal into a user-facing activity journal.
 * Delegation wrappers and hidden mechanics disappear; repeated calls that
 * represent one semantic phase update a stable row instead of appending noise.
 */
export function buildSemanticActivities(items: readonly TimelineItem[]): TimelineItem[] {
	const result: TimelineItem[] = [];
	const indexByKey = new Map<string, number>();

	for (const rawItem of items) {
		if (rawItem.kind !== "tool-call") {
			result.push(rawItem);
			continue;
		}
		if (rawItem.toolName === "task" || getToolVisibility(rawItem.toolName) === "hide") continue;

		const item = withSemanticTitle({ ...rawItem, items: undefined, spanId: undefined });
		const key = semanticKey(item);
		if (!key) {
			result.push(item);
			continue;
		}

		const existingIndex = indexByKey.get(key);
		if (existingIndex === undefined) {
			indexByKey.set(key, result.length);
			result.push(item);
			continue;
		}

		const existing = result[existingIndex];
		if (existing.kind !== "tool-call") continue;
		const status = mergedStatus(existing.status, item.status);
		result[existingIndex] = {
			...existing,
			...item,
			id: existing.id,
			status,
			sequence: existing.sequence,
			startedAt: existing.startedAt ?? item.startedAt,
			completedAt:
				status === "running" || status === "pending" || status === "awaiting_approval"
					? undefined
					: item.completedAt,
		};
	}

	return result;
}

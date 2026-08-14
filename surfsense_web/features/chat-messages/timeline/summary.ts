import { getToolCategory, getToolPresentation, getToolVisibility } from "./presentation";
import type { TimelineItem, ToolCallItem } from "./types";

const CATEGORY_PRIORITY = {
	artifact: 0,
	connector: 1,
	research: 2,
	file: 3,
	action: 4,
} as const;

function isTool(item: TimelineItem): item is ToolCallItem {
	return item.kind === "tool-call";
}

function activityCategory(item: ToolCallItem) {
	return item.context?.subagentType === "deliverables"
		? "artifact"
		: getToolCategory(item.toolName);
}

function outcomePriority(title: string, category: ReturnType<typeof activityCategory>): number {
	if (category === "artifact") {
		if (title.startsWith("Checked")) return 0;
		if (title.startsWith("Presented")) return 1;
		if (title.startsWith("Built")) return 2;
		if (title.startsWith("Drafted")) return 3;
	}
	return CATEGORY_PRIORITY[category] + 10;
}

export function buildCompletionSummary(items: readonly TimelineItem[]): string {
	const completed = items.filter(
		(item): item is ToolCallItem =>
			isTool(item) && item.status === "completed" && getToolVisibility(item.toolName) !== "hide"
	);

	if (completed.length === 0) {
		const reasoning = items.find(
			(item) => item.kind === "reasoning" && item.status === "completed"
		);
		return reasoning ? "Reasoned through the request" : "Completed the work";
	}

	const unique = new Map<string, { title: string; count: number; priority: number }>();
	for (const item of completed) {
		const presentation = getToolPresentation(item.toolName);
		const category = activityCategory(item);
		const title = item.completedTitle ?? presentation.completed;
		const key = `${category}:${title}`;
		const current = unique.get(key);
		if (current) current.count += 1;
		else {
			unique.set(key, {
				title,
				count: 1,
				priority: outcomePriority(title, category),
			});
		}
	}

	const clauses = [...unique.values()]
		.sort((a, b) => a.priority - b.priority)
		.slice(0, 2)
		.map(({ title, count }) => (count > 1 ? `${title} (${count})` : title));

	if (clauses.length === 0) return `Completed ${completed.length} actions`;
	if (clauses.length === 1) return clauses[0];
	const second = clauses[1];
	return `${clauses[0]} and ${second.charAt(0).toLowerCase()}${second.slice(1)}`;
}

export function buildActiveSummary(items: readonly TimelineItem[]): string {
	const running = items.filter(
		(item): item is ToolCallItem =>
			isTool(item) &&
			(item.status === "running" || item.status === "pending") &&
			getToolVisibility(item.toolName) !== "hide"
	);
	if (running.length === 0) return "Spellweaving";
	if (running.length === 1) {
		return running[0].activeTitle ?? getToolPresentation(running[0].toolName).active;
	}

	const categories = new Set(running.map(activityCategory));
	if (categories.size === 1) {
		const category = categories.values().next().value;
		if (category === "research") return `Reviewing ${running.length} sources`;
		if (category === "file") return `Working with ${running.length} files`;
		if (category === "artifact") return `Creating ${running.length} artifacts`;
	}
	return `Running ${running.length} tasks`;
}

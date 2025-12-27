/**
 * Plan State Atom
 *
 * Tracks the latest state of each plan by title.
 * When write_todos is called multiple times with the same title,
 * only the FIRST component renders (stays fixed in position),
 * subsequent calls just update the shared state.
 */

import { atom } from "jotai";

export interface PlanTodo {
	id: string;
	content: string;
	status: "pending" | "in_progress" | "completed" | "cancelled";
}

export interface PlanState {
	id: string;
	title: string;
	todos: PlanTodo[];
	lastUpdated: number;
	/** The toolCallId of the first component that rendered this plan */
	ownerToolCallId: string;
}

/**
 * SYNCHRONOUS ownership registry - prevents race conditions
 * Only ONE plan allowed per conversation - first plan wins
 */
let firstPlanOwner: { toolCallId: string; title: string } | null = null;

/**
 * Register as owner of a plan SYNCHRONOUSLY
 * ONE PLAN PER CONVERSATION: Only the first write_todos call renders.
 * All subsequent calls update the state but don't render their own card.
 */
export function registerPlanOwner(title: string, toolCallId: string): boolean {
	if (!firstPlanOwner) {
		// First plan in this conversation - claim ownership
		firstPlanOwner = { toolCallId, title };
		return true;
	}

	// Check if we're the owner
	return firstPlanOwner.toolCallId === toolCallId;
}

/**
 * Get the canonical title for a plan
 * Returns the first plan's title if one exists, otherwise the provided title
 */
export function getCanonicalPlanTitle(title: string): string {
	return firstPlanOwner?.title || title;
}

/**
 * Check if a plan already exists in this conversation
 */
export function hasPlan(): boolean {
	return firstPlanOwner !== null;
}

/**
 * Get the first plan's info
 */
export function getFirstPlanInfo(): { toolCallId: string; title: string } | null {
	return firstPlanOwner;
}

/**
 * Check if a toolCallId is the owner of the plan SYNCHRONOUSLY
 */
export function isPlanOwner(toolCallId: string): boolean {
	return !firstPlanOwner || firstPlanOwner.toolCallId === toolCallId;
}

/**
 * Clear ownership registry (call when starting a new chat)
 */
export function clearPlanOwnerRegistry(): void {
	firstPlanOwner = null;
}

/**
 * Map of plan title -> latest plan state
 * Using title as key since it stays constant across updates
 */
export const planStatesAtom = atom<Map<string, PlanState>>(new Map());

/**
 * Input type for updating plan state
 */
export interface UpdatePlanInput {
	id: string;
	title: string;
	todos: PlanTodo[];
	toolCallId: string;
}

/**
 * Helper atom to update a plan state
 */
export const updatePlanStateAtom = atom(null, (get, set, plan: UpdatePlanInput) => {
	const states = new Map(get(planStatesAtom));

	// Register ownership synchronously if not already done
	registerPlanOwner(plan.title, plan.toolCallId);

	// Get the actual owner from the first plan
	const ownerToolCallId = firstPlanOwner?.toolCallId || plan.toolCallId;

	// Always use the canonical (first) title for the plan key
	const canonicalTitle = getCanonicalPlanTitle(plan.title);

	states.set(canonicalTitle, {
		id: plan.id,
		title: canonicalTitle,
		todos: plan.todos,
		lastUpdated: Date.now(),
		ownerToolCallId,
	});
	set(planStatesAtom, states);
});

/**
 * Helper atom to get the latest plan state by title
 */
export const getPlanStateAtom = atom((get) => {
	const states = get(planStatesAtom);
	return (title: string) => states.get(title);
});

/**
 * Helper atom to clear all plan states (useful when starting a new chat)
 */
export const clearPlanStatesAtom = atom(null, (get, set) => {
	clearPlanOwnerRegistry();
	set(planStatesAtom, new Map());
});

/**
 * Hydrate plan state from persisted message content
 * Call this when loading messages from the database to restore plan state
 */
export interface HydratePlanInput {
	toolCallId: string;
	result: {
		id?: string;
		title?: string;
		todos?: Array<{
			id?: string;
			content: string;
			status: "pending" | "in_progress" | "completed" | "cancelled";
		}>;
	};
}

export const hydratePlanStateAtom = atom(null, (get, set, plan: HydratePlanInput) => {
	if (!plan.result?.todos || plan.result.todos.length === 0) return;

	const states = new Map(get(planStatesAtom));
	const title = plan.result.title || "Plan";

	// Register this as the owner if no plan exists yet
	registerPlanOwner(title, plan.toolCallId);

	// Get the canonical title
	const canonicalTitle = getCanonicalPlanTitle(title);
	const ownerToolCallId = firstPlanOwner?.toolCallId || plan.toolCallId;

	// Only set if this is newer or doesn't exist
	const existing = states.get(canonicalTitle);
	if (!existing) {
		states.set(canonicalTitle, {
			id: plan.result.id || `plan-${Date.now()}`,
			title: canonicalTitle,
			todos: plan.result.todos.map((t, i) => ({
				id: t.id || `todo-${i}`,
				content: t.content,
				status: t.status,
			})),
			lastUpdated: Date.now(),
			ownerToolCallId,
		});
		set(planStatesAtom, states);
	}
});

/**
 * Extract write_todos tool call data from message content
 * Returns an array of { toolCallId, result } for each write_todos call found
 */
export function extractWriteTodosFromContent(content: unknown): HydratePlanInput[] {
	if (!Array.isArray(content)) return [];

	const results: HydratePlanInput[] = [];

	for (const part of content) {
		if (
			typeof part === "object" &&
			part !== null &&
			"type" in part &&
			(part as { type: string }).type === "tool-call" &&
			"toolName" in part &&
			(part as { toolName: string }).toolName === "write_todos" &&
			"toolCallId" in part &&
			"result" in part
		) {
			const toolCall = part as {
				toolCallId: string;
				result: HydratePlanInput["result"];
			};
			if (toolCall.result) {
				results.push({
					toolCallId: toolCall.toolCallId,
					result: toolCall.result,
				});
			}
		}
	}

	return results;
}

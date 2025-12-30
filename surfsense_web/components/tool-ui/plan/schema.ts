import { z } from "zod";

/**
 * Todo item status
 */
export const TodoStatusSchema = z.enum(["pending", "in_progress", "completed", "cancelled"]);
export type TodoStatus = z.infer<typeof TodoStatusSchema>;

/**
 * Normalize various status string formats to the canonical TodoStatus
 * Handles common variations from different sources:
 * - Linear: Done, In Progress, Todo, Backlog, Cancelled
 * - Jira: To Do, In Progress, Done, In Review, Reopened, Testing + statusCategory
 * - ClickUp: Open, In Progress, Complete, Closed, Review
 * - GitHub: open, closed
 * - Airtable: Any custom field values
 */
export function normalizeStatus(status: unknown): TodoStatus {
	if (typeof status !== "string") return "pending";

	const normalized = status
		.toLowerCase()
		.trim()
		.replace(/[\s_-]+/g, "_");

	// Completed variations
	// Sources: Linear (Done), Jira (Done), ClickUp (Complete, Closed), GitHub (closed)
	if (
		normalized === "completed" ||
		normalized === "complete" ||
		normalized === "done" ||
		normalized === "finished" ||
		normalized === "closed" ||
		normalized === "resolved" ||
		normalized === "fixed" ||
		normalized === "shipped" ||
		normalized === "released" ||
		normalized === "merged"
	) {
		return "completed";
	}

	// In progress variations
	// Sources: Linear (In Progress), Jira (In Progress, In Review, Testing), ClickUp (In Progress, Review)
	if (
		normalized === "in_progress" ||
		normalized === "inprogress" ||
		normalized === "started" ||
		normalized === "active" ||
		normalized === "working" ||
		normalized === "in_review" ||
		normalized === "inreview" ||
		normalized === "review" ||
		normalized === "reviewing" ||
		normalized === "testing" ||
		normalized === "in_testing" ||
		normalized === "qa" ||
		normalized === "in_qa" ||
		normalized === "doing" ||
		normalized === "wip" ||
		normalized === "work_in_progress"
	) {
		return "in_progress";
	}

	// Cancelled variations
	// Sources: Linear (Cancelled), Jira (Won't Fix, Duplicate)
	if (
		normalized === "cancelled" ||
		normalized === "canceled" ||
		normalized === "dropped" ||
		normalized === "won't_fix" ||
		normalized === "wontfix" ||
		normalized === "wont_fix" ||
		normalized === "duplicate" ||
		normalized === "invalid" ||
		normalized === "rejected" ||
		normalized === "archived" ||
		normalized === "removed" ||
		normalized === "obsolete"
	) {
		return "cancelled";
	}

	// Pending variations (default)
	// Sources: Linear (Todo, Backlog), Jira (To Do, Reopened), ClickUp (Open), GitHub (open)
	// Includes: "pending", "todo", "to_do", "backlog", "open", "new", "triage", "reopened", etc.
	return "pending";
}

/**
 * Single todo item in a plan
 * Matches deepagents TodoListMiddleware output: { content, status }
 * id is auto-generated if not provided
 */
export const PlanTodoSchema = z.object({
	id: z.string().optional(),
	content: z.string(),
	status: TodoStatusSchema,
});

export type PlanTodo = z.infer<typeof PlanTodoSchema>;

/**
 * Serializable plan schema for tool results
 * Matches deepagents TodoListMiddleware output format
 * id/title are auto-generated if not provided
 */
export const SerializablePlanSchema = z.object({
	id: z.string().optional(),
	title: z.string().optional(),
	todos: z.array(PlanTodoSchema).min(1),
	maxVisibleTodos: z.number().optional(),
	showProgress: z.boolean().optional(),
});

export type SerializablePlan = z.infer<typeof SerializablePlanSchema>;

/**
 * Normalized plan with required fields (after auto-generation)
 */
export interface NormalizedPlan {
	id: string;
	title: string;
	todos: Array<{ id: string; content: string; status: TodoStatus }>;
	maxVisibleTodos?: number;
	showProgress?: boolean;
}

/**
 * Parse and normalize a plan from tool result
 * Auto-generates id/title if not provided (for deepagents compatibility)
 */
export function parseSerializablePlan(data: unknown): NormalizedPlan {
	const result = SerializablePlanSchema.safeParse(data);

	if (!result.success) {
		console.warn("Invalid plan data:", result.error.issues);

		// Try to extract basic info for fallback
		const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;

		return {
			id: typeof obj.id === "string" ? obj.id : `plan-${Date.now()}`,
			title: typeof obj.title === "string" ? obj.title : "Plan",
			todos: Array.isArray(obj.todos)
				? obj.todos.map((t: unknown, i: number) => {
						const todo = t as Record<string, unknown>;
						return {
							id: typeof todo?.id === "string" ? todo.id : `todo-${i}`,
							content: typeof todo?.content === "string" ? todo.content : "Task",
							status: normalizeStatus(todo?.status),
						};
					})
				: [{ id: "1", content: "No tasks", status: "pending" as const }],
		};
	}

	// Normalize: add id/title if missing
	return {
		id: result.data.id || `plan-${Date.now()}`,
		title: result.data.title || "Plan",
		todos: result.data.todos.map((t, i) => ({
			id: t.id || `todo-${i}`,
			content: t.content,
			status: t.status,
		})),
		maxVisibleTodos: result.data.maxVisibleTodos,
		showProgress: result.data.showProgress,
	};
}

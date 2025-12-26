import { z } from "zod";

/**
 * Todo item status
 */
export const TodoStatusSchema = z.enum(["pending", "in_progress", "completed", "cancelled"]);
export type TodoStatus = z.infer<typeof TodoStatusSchema>;

/**
 * Single todo item in a plan
 */
export const PlanTodoSchema = z.object({
	id: z.string(),
	label: z.string(),
	status: TodoStatusSchema,
	description: z.string().optional(),
});

export type PlanTodo = z.infer<typeof PlanTodoSchema>;

/**
 * Serializable plan schema for tool results
 */
export const SerializablePlanSchema = z.object({
	id: z.string(),
	title: z.string(),
	description: z.string().optional(),
	todos: z.array(PlanTodoSchema).min(1),
	maxVisibleTodos: z.number().optional(),
	showProgress: z.boolean().optional(),
});

export type SerializablePlan = z.infer<typeof SerializablePlanSchema>;

/**
 * Parse and validate a serializable plan from tool result
 */
export function parseSerializablePlan(data: unknown): SerializablePlan {
	const result = SerializablePlanSchema.safeParse(data);

	if (!result.success) {
		console.warn("Invalid plan data:", result.error.issues);

		// Try to extract basic info for fallback
		const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;

		return {
			id: typeof obj.id === "string" ? obj.id : "unknown",
			title: typeof obj.title === "string" ? obj.title : "Plan",
			description: typeof obj.description === "string" ? obj.description : undefined,
			todos: Array.isArray(obj.todos)
				? obj.todos.map((t, i) => ({
						id: typeof (t as any)?.id === "string" ? (t as any).id : `todo-${i}`,
						label: typeof (t as any)?.label === "string" ? (t as any).label : "Task",
						status: TodoStatusSchema.safeParse((t as any)?.status).success
							? (t as any).status
							: "pending",
						description:
							typeof (t as any)?.description === "string" ? (t as any).description : undefined,
					}))
				: [{ id: "1", label: "No tasks", status: "pending" as const }],
		};
	}

	return result.data;
}

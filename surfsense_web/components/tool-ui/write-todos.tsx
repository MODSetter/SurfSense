"use client";

import { makeAssistantToolUI, useAssistantState } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useMemo } from "react";
import { z } from "zod";
import {
	getCanonicalPlanTitle,
	planStatesAtom,
	registerPlanOwner,
	updatePlanStateAtom,
} from "@/atoms/chat/plan-state.atom";
import { Spinner } from "@/components/ui/spinner";
import { Plan, PlanErrorBoundary, parseSerializablePlan, TodoStatusSchema } from "./plan";

// ============================================================================
// Zod Schemas - Matching deepagents TodoListMiddleware output
// ============================================================================

/**
 * Schema for a single todo item (matches deepagents output)
 */
const TodoItemSchema = z.object({
	content: z.string(),
	status: TodoStatusSchema,
});

/**
 * Schema for write_todos tool args/result (matches deepagents output)
 * deepagents provides: { todos: [{ content, status }] }
 */
const WriteTodosSchema = z.object({
	todos: z.array(TodoItemSchema).nullish(),
});

// ============================================================================
// Types
// ============================================================================

type WriteTodosData = z.infer<typeof WriteTodosSchema>;

/**
 * Loading state component
 */
function WriteTodosLoading() {
	return (
		<div className="my-4 w-full max-w-xl rounded-2xl border bg-card/60 px-5 py-4 shadow-sm">
			<div className="flex items-center gap-3">
				<Spinner size="md" className="text-primary" />
				<span className="text-sm text-muted-foreground">Creating plan...</span>
			</div>
		</div>
	);
}

/**
 * WriteTodos Tool UI Component
 *
 * Displays the agent's planning/todo list with a beautiful UI.
 * Uses deepagents TodoListMiddleware output directly: { todos: [{ content, status }] }
 *
 * FIXED POSITION: When multiple write_todos calls happen in a conversation,
 * only the FIRST component renders. Subsequent updates just update the
 * shared state, and the first component reads from it.
 */
export const WriteTodosToolUI = makeAssistantToolUI<WriteTodosData, WriteTodosData>({
	toolName: "write_todos",
	render: function WriteTodosUI({ args, result, status, toolCallId }) {
		const updatePlanState = useSetAtom(updatePlanStateAtom);
		const planStates = useAtomValue(planStatesAtom);

		// Check if the THREAD is running
		const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);

		// Use result if available, otherwise args (for streaming)
		const data = result || args;
		const hasTodos = data?.todos && data.todos.length > 0;

		// Fixed title for all plans in conversation
		const planTitle = "Plan";

		// SYNCHRONOUS ownership check
		const isOwner = useMemo(() => {
			return registerPlanOwner(planTitle, toolCallId);
		}, [planTitle, toolCallId]);

		// Get canonical title
		const canonicalTitle = useMemo(() => getCanonicalPlanTitle(planTitle), [planTitle]);

		// Register/update the plan state
		useEffect(() => {
			if (hasTodos) {
				const normalizedPlan = parseSerializablePlan({ todos: data.todos });
				updatePlanState({
					id: normalizedPlan.id,
					title: canonicalTitle,
					todos: normalizedPlan.todos,
					toolCallId,
				});
			}
		}, [data, hasTodos, canonicalTitle, updatePlanState, toolCallId]);

		// Get the current plan state
		const currentPlanState = planStates.get(canonicalTitle);

		// If we're NOT the owner, render nothing
		if (!isOwner) {
			return null;
		}

		// Loading state
		if (status.type === "running" || status.type === "requires-action") {
			if (hasTodos) {
				const plan = parseSerializablePlan({ todos: data.todos });
				return (
					<div className="my-4">
						<PlanErrorBoundary>
							<Plan {...plan} showProgress={true} isStreaming={isThreadRunning} />
						</PlanErrorBoundary>
					</div>
				);
			}
			return <WriteTodosLoading />;
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (currentPlanState || hasTodos) {
				const plan = currentPlanState || parseSerializablePlan({ todos: data?.todos || [] });
				return (
					<div className="my-4">
						<PlanErrorBoundary>
							<Plan {...plan} showProgress={true} isStreaming={isThreadRunning} />
						</PlanErrorBoundary>
					</div>
				);
			}
			return null;
		}

		// Success - render the plan
		const planToRender =
			currentPlanState || (hasTodos ? parseSerializablePlan({ todos: data.todos }) : null);
		if (!planToRender) {
			return <WriteTodosLoading />;
		}

		return (
			<div className="my-4">
				<PlanErrorBoundary>
					<Plan {...planToRender} showProgress={true} isStreaming={isThreadRunning} />
				</PlanErrorBoundary>
			</div>
		);
	},
});

export { WriteTodosSchema, type WriteTodosData };

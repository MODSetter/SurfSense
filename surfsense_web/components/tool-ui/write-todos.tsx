"use client";

import { makeAssistantToolUI, useAssistantState } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { z } from "zod";
import {
	getCanonicalPlanTitle,
	planStatesAtom,
	registerPlanOwner,
	updatePlanStateAtom,
} from "@/atoms/chat/plan-state.atom";
import { Plan, PlanErrorBoundary, parseSerializablePlan, TodoStatusSchema } from "./plan";

// ============================================================================
// Zod Schemas
// ============================================================================

/**
 * Schema for a single todo item in the args
 * Note: Using nullish() with transform to convert null → undefined for Plan compatibility
 */
const WriteTodosArgsTodoSchema = z.object({
	id: z.string(),
	content: z.string(),
	status: TodoStatusSchema,
	description: z
		.string()
		.nullish()
		.transform((v) => v ?? undefined),
});

/**
 * Schema for write_todos tool arguments
 * Note: Using nullish() with transform to convert null → undefined for Plan compatibility
 */
const WriteTodosArgsSchema = z.object({
	title: z
		.string()
		.nullish()
		.transform((v) => v ?? undefined),
	description: z
		.string()
		.nullish()
		.transform((v) => v ?? undefined),
	todos: z.array(WriteTodosArgsTodoSchema).nullish(),
});

/**
 * Schema for a single todo item in the result
 * Note: Using nullish() with transform to convert null → undefined for Plan compatibility
 */
const WriteTodosResultTodoSchema = z.object({
	id: z.string(),
	label: z.string(),
	status: TodoStatusSchema,
	description: z
		.string()
		.nullish()
		.transform((v) => v ?? undefined),
});

/**
 * Schema for write_todos tool result
 * Note: Using nullish() with transform to convert null → undefined for Plan compatibility
 */
const WriteTodosResultSchema = z.object({
	id: z.string(),
	title: z.string(),
	description: z
		.string()
		.nullish()
		.transform((v) => v ?? undefined),
	todos: z.array(WriteTodosResultTodoSchema),
});

// ============================================================================
// Types
// ============================================================================

type WriteTodosArgs = z.infer<typeof WriteTodosArgsSchema>;
type WriteTodosResult = z.infer<typeof WriteTodosResultSchema>;

/**
 * Loading state component
 */
function WriteTodosLoading() {
	return (
		<div className="my-4 w-full max-w-xl rounded-2xl border bg-card/60 px-5 py-4 shadow-sm">
			<div className="flex items-center gap-3">
				<Loader2 className="size-5 animate-spin text-primary" />
				<span className="text-sm text-muted-foreground">Creating plan...</span>
			</div>
		</div>
	);
}

/**
 * Transform tool args to result format
 * This handles the case where the LLM is streaming the tool call
 */
function transformArgsToResult(args: WriteTodosArgs): WriteTodosResult | null {
	if (!args.todos || !Array.isArray(args.todos) || args.todos.length === 0) {
		return null;
	}

	return {
		id: `plan-${Date.now()}`,
		title: args.title || "Planning Approach",
		description: args.description,
		todos: args.todos.map((todo, index) => ({
			id: todo.id || `todo-${index}`,
			label: todo.content || "Task",
			status: todo.status || "pending",
			description: todo.description,
		})),
	};
}

/**
 * WriteTodos Tool UI Component
 *
 * Displays the agent's planning/todo list with a beautiful UI.
 * Shows progress, status indicators, and expandable details.
 *
 * FIXED POSITION: When the same plan (by title) is updated multiple times,
 * only the FIRST component renders. Subsequent updates just update the
 * shared state, and the first component reads from it. This prevents
 * layout shift when plans are updated.
 */
export const WriteTodosToolUI = makeAssistantToolUI<WriteTodosArgs, WriteTodosResult>({
	toolName: "write_todos",
	render: function WriteTodosUI({ args, result, status, toolCallId }) {
		const updatePlanState = useSetAtom(updatePlanStateAtom);
		const planStates = useAtomValue(planStatesAtom);

		// Check if the THREAD is running (not just this tool)
		// This hook subscribes to state changes, so it re-renders when thread stops
		const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);

		// Get the plan data (from result or args)
		const planData = result || transformArgsToResult(args);
		const rawTitle = planData?.title || args.title || "Planning Approach";

		// SYNCHRONOUS ownership check - happens immediately, no race conditions
		// ONE PLAN PER CONVERSATION: Only first write_todos call becomes owner
		const isOwner = useMemo(() => {
			return registerPlanOwner(rawTitle, toolCallId);
		}, [rawTitle, toolCallId]);

		// Get canonical title - always use the FIRST plan's title
		// This ensures all updates go to the same plan state
		const planTitle = useMemo(() => getCanonicalPlanTitle(rawTitle), [rawTitle]);

		// Register/update the plan state - ALWAYS use canonical title
		useEffect(() => {
			if (planData) {
				updatePlanState({
					id: planData.id,
					title: planTitle, // Use canonical title, not raw title
					description: planData.description,
					todos: planData.todos,
					toolCallId,
				});
			}
		}, [planData, planTitle, updatePlanState, toolCallId]);

		// Update when result changes (for streaming updates)
		useEffect(() => {
			if (result) {
				updatePlanState({
					id: result.id,
					title: planTitle, // Use canonical title, not raw title
					description: result.description,
					todos: result.todos,
					toolCallId,
				});
			}
		}, [result, planTitle, updatePlanState, toolCallId]);

		// Get the current plan state (may be updated by other components)
		const currentPlanState = planStates.get(planTitle);

		// If we're NOT the owner, render nothing (the owner will render)
		if (!isOwner) {
			return null;
		}

		// Loading state - tool is still running (no data yet)
		if (status.type === "running" || status.type === "requires-action") {
			// Try to show partial results from args while streaming
			const partialResult = transformArgsToResult(args);
			if (partialResult) {
				const plan = parseSerializablePlan(partialResult);
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
			// For cancelled or errors, try to show what we have from args or shared state
			// Use isThreadRunning to determine if we should still animate
			const fallbackResult = currentPlanState || transformArgsToResult(args);
			if (fallbackResult) {
				const plan = parseSerializablePlan(fallbackResult);
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

		// Success - render the plan using the LATEST shared state
		// Use isThreadRunning to determine if we should animate in_progress items
		// (LLM may still be working on tasks even though this tool call completed)
		const planToRender = currentPlanState || result;
		if (!planToRender) {
			return <WriteTodosLoading />;
		}

		const plan = parseSerializablePlan(planToRender);
		return (
			<div className="my-4">
				<PlanErrorBoundary>
					<Plan {...plan} showProgress={true} isStreaming={isThreadRunning} />
				</PlanErrorBoundary>
			</div>
		);
	},
});

export { WriteTodosArgsSchema, WriteTodosResultSchema, type WriteTodosArgs, type WriteTodosResult };

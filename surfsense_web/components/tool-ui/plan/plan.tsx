"use client";

import { CheckCircle2, Circle, CircleDashed, ListTodo, PartyPopper, XCircle } from "lucide-react";
import type { FC } from "react";
import { useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { Action, ActionsConfig } from "../shared/schema";
import type { TodoStatus } from "./schema";

// ============================================================================
// Status Icon Component
// ============================================================================

interface StatusIconProps {
	status: TodoStatus;
	className?: string;
	/** When false, in_progress items show as static (no spinner) */
	isStreaming?: boolean;
}

const StatusIcon: FC<StatusIconProps> = ({ status, className, isStreaming = true }) => {
	const baseClass = cn("size-4 shrink-0", className);

	switch (status) {
		case "completed":
			return <CheckCircle2 className={cn(baseClass, "text-emerald-500")} />;
		case "in_progress":
			// Only animate the spinner if we're actively streaming
			// When streaming is stopped, show as a static dashed circle
			return (
				<CircleDashed
					className={cn(baseClass, "text-primary", isStreaming && "animate-spin")}
					style={isStreaming ? { animationDuration: "3s" } : undefined}
				/>
			);
		case "cancelled":
			return <XCircle className={cn(baseClass, "text-destructive")} />;
		case "pending":
		default:
			return <Circle className={cn(baseClass, "text-muted-foreground")} />;
	}
};

// ============================================================================
// Todo Item Component
// ============================================================================

interface TodoItemProps {
	todo: { id: string; content: string; status: TodoStatus };
	/** When false, in_progress items show as static (no spinner/pulse) */
	isStreaming?: boolean;
}

const TodoItem: FC<TodoItemProps> = ({ todo, isStreaming = true }) => {
	const isStrikethrough = todo.status === "completed" || todo.status === "cancelled";
	// Only show shimmer animation if streaming and in progress
	const isShimmer = todo.status === "in_progress" && isStreaming;

	// Render the content with optional shimmer effect
	const renderContent = () => {
		if (isShimmer) {
			return <TextShimmerLoader text={todo.content} size="md" />;
		}
		return (
			<span className={cn("text-sm text-muted-foreground", isStrikethrough && "line-through")}>
				{todo.content}
			</span>
		);
	};

	return (
		<div className="flex items-center gap-2 py-2">
			<StatusIcon status={todo.status} isStreaming={isStreaming} />
			{renderContent()}
		</div>
	);
};

// ============================================================================
// Plan Component
// ============================================================================

export interface PlanProps {
	id: string;
	title: string;
	todos: Array<{ id: string; content: string; status: TodoStatus }>;
	maxVisibleTodos?: number;
	showProgress?: boolean;
	/** When false, in_progress items show as static (no spinner/pulse animations) */
	isStreaming?: boolean;
	responseActions?: Action[] | ActionsConfig;
	className?: string;
	onResponseAction?: (actionId: string) => void;
	onBeforeResponseAction?: (actionId: string) => boolean;
}

export const Plan: FC<PlanProps> = ({
	id,
	title,
	todos,
	maxVisibleTodos = 4,
	showProgress = true,
	isStreaming = true,
	responseActions,
	className,
	onResponseAction,
	onBeforeResponseAction,
}) => {
	const [isExpanded, setIsExpanded] = useState(false);

	// Calculate progress
	const progress = useMemo(() => {
		const completed = todos.filter((t) => t.status === "completed").length;
		const total = todos.filter((t) => t.status !== "cancelled").length;
		return { completed, total, percentage: total > 0 ? (completed / total) * 100 : 0 };
	}, [todos]);

	const isAllComplete = progress.completed === progress.total && progress.total > 0;

	// Split todos for collapsible display
	const visibleTodos = todos.slice(0, maxVisibleTodos);
	const hiddenTodos = todos.slice(maxVisibleTodos);
	const hasHiddenTodos = hiddenTodos.length > 0;

	// Handle action click
	const handleAction = (actionId: string) => {
		if (onBeforeResponseAction && !onBeforeResponseAction(actionId)) {
			return;
		}
		onResponseAction?.(actionId);
	};

	// Normalize actions to array
	const actionArray: Action[] = useMemo(() => {
		if (!responseActions) return [];
		if (Array.isArray(responseActions)) return responseActions;
		return [
			responseActions.confirm && { ...responseActions.confirm, id: "confirm" },
			responseActions.cancel && { ...responseActions.cancel, id: "cancel" },
		].filter(Boolean) as Action[];
	}, [responseActions]);

	const TodoList: FC<{ items: typeof todos }> = ({ items }) => {
		return (
			<div className="space-y-0">
				{items.map((todo) => (
					<TodoItem key={todo.id} todo={todo} isStreaming={isStreaming} />
				))}
			</div>
		);
	};

	return (
		<Card id={id} className={cn("w-full max-w-xl", className)}>
			<CardHeader className="pb-3">
				<div className="flex items-start justify-between gap-2">
					<div className="flex-1 min-w-0 flex items-center gap-2">
						<ListTodo className="size-5 text-muted-foreground shrink-0" />
						<CardTitle className="text-base font-semibold text-muted-foreground">{title}</CardTitle>
					</div>
					{isAllComplete && (
						<div className="flex items-center gap-1 text-emerald-500">
							<PartyPopper className="size-5" />
						</div>
					)}
				</div>

				{showProgress && (
					<div className="mt-3 space-y-1.5">
						<div className="flex items-center justify-between text-xs text-muted-foreground">
							<span>
								{progress.completed} of {progress.total} complete
							</span>
							<span>{Math.round(progress.percentage)}%</span>
						</div>
						<Progress
							value={progress.percentage}
							className="h-1.5 bg-muted [&>div]:bg-muted-foreground"
						/>
					</div>
				)}
			</CardHeader>

			<CardContent className="pt-0">
				<TodoList items={visibleTodos} />

				{hasHiddenTodos && (
					<Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
						<CollapsibleTrigger asChild>
							<Button
								variant="ghost"
								size="sm"
								className="w-full mt-2 text-xs text-muted-foreground hover:text-foreground"
							>
								{isExpanded
									? "Show less"
									: `Show ${hiddenTodos.length} more ${hiddenTodos.length === 1 ? "task" : "tasks"}`}
							</Button>
						</CollapsibleTrigger>
						<CollapsibleContent>
							<TodoList items={hiddenTodos} />
						</CollapsibleContent>
					</Collapsible>
				)}

				{actionArray.length > 0 && (
					<div className="flex flex-wrap gap-2 pt-4 mt-2 border-t">
						{actionArray.map((action) => (
							<Button
								key={action.id}
								variant={action.variant || "default"}
								size="sm"
								disabled={action.disabled}
								onClick={() => handleAction(action.id)}
							>
								{action.label}
							</Button>
						))}
					</div>
				)}
			</CardContent>
		</Card>
	);
};

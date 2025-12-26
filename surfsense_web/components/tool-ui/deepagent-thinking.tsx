"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Brain, CheckCircle2, Loader2, Search, Sparkles } from "lucide-react";
import type { FC, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";
import {
	ChainOfThought,
	ChainOfThoughtContent,
	ChainOfThoughtItem,
	ChainOfThoughtStep,
	ChainOfThoughtTrigger,
} from "@/components/prompt-kit/chain-of-thought";
import { cn } from "@/lib/utils";

// ============================================================================
// Constants
// ============================================================================

/** Step status values */
const STEP_STATUS = {
	PENDING: "pending",
	IN_PROGRESS: "in_progress",
	COMPLETED: "completed",
} as const;

/** Agent thinking status values */
const THINKING_STATUS = {
	THINKING: "thinking",
	SEARCHING: "searching",
	SYNTHESIZING: "synthesizing",
	COMPLETED: "completed",
} as const;

/** Keywords for icon detection */
const STEP_KEYWORDS = {
	SEARCH: ["search", "knowledge"] as const,
	ANALYSIS: ["analy", "understand"] as const,
} as const;

/** Icon size class */
const ICON_SIZE_CLASS = "size-4" as const;

/** Status text mapping */
const STATUS_TEXT_MAP: Record<string, string> = {
	[THINKING_STATUS.SEARCHING]: "Searching knowledge base...",
	[THINKING_STATUS.SYNTHESIZING]: "Synthesizing response...",
	[THINKING_STATUS.THINKING]: "Thinking...",
} as const;

// ============================================================================
// Type Definitions
// ============================================================================

type StepStatus = (typeof STEP_STATUS)[keyof typeof STEP_STATUS];
type ThinkingStatus = (typeof THINKING_STATUS)[keyof typeof THINKING_STATUS];

// ============================================================================
// Zod Schemas
// ============================================================================

const ThinkingStepSchema = z.object({
	id: z.string(),
	title: z.string(),
	items: z.array(z.string()).default([]),
	status: z
		.enum([STEP_STATUS.PENDING, STEP_STATUS.IN_PROGRESS, STEP_STATUS.COMPLETED])
		.default(STEP_STATUS.PENDING),
});

const DeepAgentThinkingArgsSchema = z.object({
	query: z.string().nullish(),
	context: z.string().nullish(),
});

const DeepAgentThinkingResultSchema = z.object({
	steps: z.array(ThinkingStepSchema).nullish(),
	status: z
		.enum([
			THINKING_STATUS.THINKING,
			THINKING_STATUS.SEARCHING,
			THINKING_STATUS.SYNTHESIZING,
			THINKING_STATUS.COMPLETED,
		])
		.nullish(),
	summary: z.string().nullish(),
});

/** Types derived from Zod schemas */
type ThinkingStep = z.infer<typeof ThinkingStepSchema>;
type DeepAgentThinkingArgs = z.infer<typeof DeepAgentThinkingArgsSchema>;
type DeepAgentThinkingResult = z.infer<typeof DeepAgentThinkingResultSchema>;

// ============================================================================
// Parser Functions
// ============================================================================

/** Default fallback step when parsing fails */
const DEFAULT_FALLBACK_STEP: ThinkingStep = {
	id: "unknown",
	title: "Processing...",
	items: [],
	status: STEP_STATUS.PENDING,
} as const;

/**
 * Parse and validate a single thinking step
 */
export function parseThinkingStep(data: unknown): ThinkingStep {
	const result = ThinkingStepSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid thinking step data:", result.error.issues);
		return DEFAULT_FALLBACK_STEP;
	}
	return result.data;
}

/**
 * Parse and validate thinking result
 */
export function parseThinkingResult(data: unknown): DeepAgentThinkingResult {
	const result = DeepAgentThinkingResultSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid thinking result data:", result.error.issues);
		return {};
	}
	return result.data;
}

// ============================================================================
// Icon Utilities
// ============================================================================

/**
 * Check if title contains any of the keywords
 */
function titleContainsKeywords(title: string, keywords: readonly string[]): boolean {
	const titleLower = title.toLowerCase();
	return keywords.some((keyword) => titleLower.includes(keyword));
}

/**
 * Get icon based on step status and title
 */
function getStepIcon(status: StepStatus, title: string): ReactNode {
	if (status === STEP_STATUS.IN_PROGRESS) {
		return <Loader2 className={cn(ICON_SIZE_CLASS, "animate-spin text-primary")} />;
	}

	if (status === STEP_STATUS.COMPLETED) {
		return <CheckCircle2 className={cn(ICON_SIZE_CLASS, "text-emerald-500")} />;
	}

	// Default icons based on step type keywords
	if (titleContainsKeywords(title, STEP_KEYWORDS.SEARCH)) {
		return <Search className={cn(ICON_SIZE_CLASS, "text-muted-foreground")} />;
	}

	if (titleContainsKeywords(title, STEP_KEYWORDS.ANALYSIS)) {
		return <Brain className={cn(ICON_SIZE_CLASS, "text-muted-foreground")} />;
	}

	return <Sparkles className={cn(ICON_SIZE_CLASS, "text-muted-foreground")} />;
}

// ============================================================================
// Sub-Components
// ============================================================================

interface ThinkingStepDisplayProps {
	step: ThinkingStep;
	isOpen: boolean;
	onToggle: () => void;
}

/**
 * Component to display a single thinking step with controlled open state
 */
const ThinkingStepDisplay: FC<ThinkingStepDisplayProps> = ({ step, isOpen, onToggle }) => {
	const icon = useMemo(() => getStepIcon(step.status, step.title), [step.status, step.title]);

	const isInProgress = step.status === STEP_STATUS.IN_PROGRESS;
	const isCompleted = step.status === STEP_STATUS.COMPLETED;

	return (
		<ChainOfThoughtStep open={isOpen} onOpenChange={onToggle}>
			<ChainOfThoughtTrigger
				leftIcon={icon}
				swapIconOnHover={!isInProgress}
				className={cn(
					isInProgress && "text-foreground font-medium",
					isCompleted && "text-muted-foreground"
				)}
			>
				{step.title}
			</ChainOfThoughtTrigger>
			<ChainOfThoughtContent>
				{step.items.map((item, index) => (
					<ChainOfThoughtItem key={`${step.id}-item-${index}`}>{item}</ChainOfThoughtItem>
				))}
			</ChainOfThoughtContent>
		</ChainOfThoughtStep>
	);
};

interface ThinkingLoadingStateProps {
	status?: ThinkingStatus | string;
}

/**
 * Loading state with animated thinking indicator
 */
const ThinkingLoadingState: FC<ThinkingLoadingStateProps> = ({ status }) => {
	const statusText = useMemo(() => {
		if (status && status in STATUS_TEXT_MAP) {
			return STATUS_TEXT_MAP[status];
		}
		return STATUS_TEXT_MAP[THINKING_STATUS.THINKING];
	}, [status]);

	return (
		<div className="my-3 flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 px-4 py-3">
			<div className="relative">
				<Brain className="size-5 text-primary" />
				<span className="absolute -right-0.5 -top-0.5 flex size-2">
					<span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
					<span className="relative inline-flex size-2 rounded-full bg-primary" />
				</span>
			</div>
			<span className="text-sm text-muted-foreground">{statusText}</span>
		</div>
	);
};

interface SmartChainOfThoughtProps {
	steps: ThinkingStep[];
}

/** Type for tracking step override states */
type StepOverrides = Record<string, boolean>;

/** Type for tracking step status history */
type StepStatusHistory = Record<string, StepStatus>;

/**
 * Smart chain of thought renderer with state management
 */
const SmartChainOfThought: FC<SmartChainOfThoughtProps> = ({ steps }) => {
	// Track which steps the user has manually toggled
	const [manualOverrides, setManualOverrides] = useState<StepOverrides>({});
	// Track previous step statuses to detect changes
	const prevStatusesRef = useRef<StepStatusHistory>({});

	// Clear manual overrides when a step's status changes
	useEffect(() => {
		const currentStatuses: StepStatusHistory = {};
		steps.forEach((step) => {
			currentStatuses[step.id] = step.status;
			// If status changed, clear any manual override for this step
			const prevStatus = prevStatusesRef.current[step.id];
			if (prevStatus && prevStatus !== step.status) {
				setManualOverrides((prev) => {
					const next = { ...prev };
					delete next[step.id];
					return next;
				});
			}
		});
		prevStatusesRef.current = currentStatuses;
	}, [steps]);

	const getStepOpenState = useCallback(
		(step: ThinkingStep): boolean => {
			// If user has manually toggled, respect that
			if (manualOverrides[step.id] !== undefined) {
				return manualOverrides[step.id];
			}
			// Auto behavior: open if in progress
			if (step.status === STEP_STATUS.IN_PROGRESS) {
				return true;
			}
			// Default: collapsed (all steps collapse when processing is done)
			return false;
		},
		[manualOverrides]
	);

	const handleToggle = useCallback((stepId: string, currentOpen: boolean) => {
		setManualOverrides((prev) => ({
			...prev,
			[stepId]: !currentOpen,
		}));
	}, []);

	return (
		<ChainOfThought>
			{steps.map((step) => {
				const isOpen = getStepOpenState(step);
				return (
					<ThinkingStepDisplay
						key={step.id}
						step={step}
						isOpen={isOpen}
						onToggle={() => handleToggle(step.id, isOpen)}
					/>
				);
			})}
		</ChainOfThought>
	);
};

/**
 * DeepAgent Thinking Tool UI Component
 *
 * This component displays the agent's chain-of-thought reasoning
 * when the deepagent is processing a query. It shows thinking steps
 * in a collapsible, hierarchical format.
 */
export const DeepAgentThinkingToolUI = makeAssistantToolUI<
	DeepAgentThinkingArgs,
	DeepAgentThinkingResult
>({
	toolName: "deepagent_thinking",
	render: function DeepAgentThinkingUI({ result, status }) {
		// Loading state - tool is still running
		if (status.type === "running" || status.type === "requires-action") {
			return <ThinkingLoadingState status={result?.status ?? undefined} />;
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return null; // Don't show anything if cancelled
			}
			if (status.reason === "error") {
				return null; // Don't show error for thinking - it's not critical
			}
		}

		// No result or no steps - don't render anything
		if (!result?.steps || result.steps.length === 0) {
			return null;
		}

		// Render the chain of thought
		return (
			<div className="my-3 w-full">
				<SmartChainOfThought steps={result.steps} />
			</div>
		);
	},
});

// ============================================================================
// Public Components
// ============================================================================

export interface InlineThinkingDisplayProps {
	/** The thinking steps to display */
	steps: ThinkingStep[];
	/** Whether content is currently streaming */
	isStreaming?: boolean;
	/** Additional CSS class names */
	className?: string;
}

/**
 * Inline Thinking Display Component
 *
 * A simpler version that can be used inline with the message content
 * for displaying reasoning without the full tool UI infrastructure.
 */
export const InlineThinkingDisplay: FC<InlineThinkingDisplayProps> = ({
	steps,
	isStreaming = false,
	className,
}) => {
	if (steps.length === 0 && !isStreaming) {
		return null;
	}

	return (
		<div className={cn("my-3 w-full", className)}>
			{isStreaming && steps.length === 0 ? (
				<ThinkingLoadingState />
			) : (
				<SmartChainOfThought steps={steps} />
			)}
		</div>
	);
};

// ============================================================================
// Exports
// ============================================================================

export type {
	ThinkingStep,
	DeepAgentThinkingArgs,
	DeepAgentThinkingResult,
	StepStatus,
	ThinkingStatus,
};

export { STEP_STATUS, THINKING_STATUS };

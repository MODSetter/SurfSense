import { useAssistantState, useThreadViewport } from "@assistant-ui/react";
import { ChevronRightIcon } from "lucide-react";
import type { FC } from "react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ChainOfThoughtItem } from "@/components/prompt-kit/chain-of-thought";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { cn } from "@/lib/utils";

// Context to pass thinking steps to AssistantMessage
export const ThinkingStepsContext = createContext<Map<string, ThinkingStep[]>>(new Map());

/**
 * Chain of thought display component - single collapsible dropdown design
 */
export const ThinkingStepsDisplay: FC<{ steps: ThinkingStep[]; isThreadRunning?: boolean }> = ({
	steps,
	isThreadRunning = true,
}) => {
	const [isOpen, setIsOpen] = useState(true);

	// Derive effective status for each step
	const getEffectiveStatus = useCallback(
		(step: ThinkingStep): "pending" | "in_progress" | "completed" => {
			if (step.status === "in_progress" && !isThreadRunning) {
				return "completed";
			}
			return step.status;
		},
		[isThreadRunning]
	);

	// Calculate summary info
	const completedSteps = steps.filter((s) => getEffectiveStatus(s) === "completed").length;
	const inProgressStep = steps.find((s) => getEffectiveStatus(s) === "in_progress");
	const allCompleted = completedSteps === steps.length && steps.length > 0 && !isThreadRunning;
	const isProcessing = isThreadRunning && !allCompleted;

	// Auto-collapse when all tasks are completed
	useEffect(() => {
		if (allCompleted) {
			setIsOpen(false);
		}
	}, [allCompleted]);

	if (steps.length === 0) return null;

	// Generate header text
	const getHeaderText = () => {
		if (allCompleted) {
			return `Reviewed ${completedSteps} ${completedSteps === 1 ? "step" : "steps"}`;
		}
		if (inProgressStep) {
			return inProgressStep.title;
		}
		if (isProcessing) {
			return `Processing ${completedSteps}/${steps.length} steps`;
		}
		return `Reviewed ${completedSteps} ${completedSteps === 1 ? "step" : "steps"}`;
	};

	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<div className="rounded-lg">
				{/* Main collapsible header */}
				<button
					type="button"
					onClick={() => setIsOpen(!isOpen)}
					className={cn(
						"flex w-full items-center gap-1.5 text-left text-sm transition-colors",
						"text-muted-foreground hover:text-foreground"
					)}
				>
					{/* Header text with shimmer if processing (streaming) */}
					{isProcessing ? (
						<TextShimmerLoader text={getHeaderText()} size="sm" />
					) : (
						<span>{getHeaderText()}</span>
					)}

					{/* Chevron */}
					<ChevronRightIcon
						className={cn("size-4 transition-transform duration-200", isOpen && "rotate-90")}
					/>
				</button>

				{/* Collapsible content with CSS grid animation */}
				<div
					className={cn(
						"grid transition-[grid-template-rows] duration-300 ease-out",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-3 pl-1">
							{steps.map((step, index) => {
								const effectiveStatus = getEffectiveStatus(step);
								const isLast = index === steps.length - 1;

								return (
									<div key={step.id} className="relative flex gap-3">
										{/* Dot and line column */}
										<div className="relative flex flex-col items-center w-2">
											{/* Vertical connection line - extends to next dot */}
											{!isLast && (
												<div className="absolute left-1/2 top-[15px] -bottom-[7px] w-px -translate-x-1/2 bg-muted-foreground/30" />
											)}
											{/* Step dot - on top of line */}
											<div className="relative z-10 mt-[7px] flex shrink-0 items-center justify-center">
												{effectiveStatus === "in_progress" ? (
													<span className="relative flex size-2">
														<span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
														<span className="relative inline-flex size-2 rounded-full bg-primary" />
													</span>
												) : (
													<span className="size-2 rounded-full bg-muted-foreground/30" />
												)}
											</div>
										</div>

										{/* Step content */}
										<div className="flex-1 min-w-0 pb-4">
											{/* Step title */}
											<div
												className={cn(
													"text-sm leading-5",
													effectiveStatus === "in_progress" && "text-foreground font-medium",
													effectiveStatus === "completed" && "text-muted-foreground",
													effectiveStatus === "pending" && "text-muted-foreground/60"
												)}
											>
												{effectiveStatus === "in_progress" ? (
													<TextShimmerLoader text={step.title} size="sm" />
												) : (
													step.title
												)}
											</div>

											{/* Step items (sub-content) */}
											{step.items && step.items.length > 0 && (
												<div className="mt-1 space-y-0.5">
													{step.items.map((item, idx) => (
														<ChainOfThoughtItem key={`${step.id}-item-${idx}`} className="text-xs">
															{item}
														</ChainOfThoughtItem>
													))}
												</div>
											)}
										</div>
									</div>
								);
							})}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

/**
 * Component that handles auto-scroll when thinking steps update.
 * Uses useThreadViewport to scroll to bottom when thinking steps change,
 * ensuring the user always sees the latest content during streaming.
 */
export const ThinkingStepsScrollHandler: FC = () => {
	const thinkingStepsMap = useContext(ThinkingStepsContext);
	const viewport = useThreadViewport();
	const isRunning = useAssistantState(({ thread }) => thread.isRunning);
	// Track the serialized state to detect any changes
	const prevStateRef = useRef<string>("");

	useEffect(() => {
		// Only act during streaming
		if (!isRunning) {
			prevStateRef.current = "";
			return;
		}

		// Serialize the thinking steps state to detect any changes
		// This catches new steps, status changes, and item additions
		let stateString = "";
		thinkingStepsMap.forEach((steps, msgId) => {
			steps.forEach((step) => {
				stateString += `${msgId}:${step.id}:${step.status}:${step.items?.length || 0};`;
			});
		});

		// If state changed at all during streaming, scroll
		if (stateString !== prevStateRef.current && stateString !== "") {
			prevStateRef.current = stateString;

			// Multiple attempts to ensure scroll happens after DOM updates
			const scrollAttempt = () => {
				try {
					viewport.scrollToBottom();
				} catch {
					// Ignore errors - viewport might not be ready
				}
			};

			// Delayed attempts to handle async DOM updates
			requestAnimationFrame(scrollAttempt);
			setTimeout(scrollAttempt, 100);
		}
	}, [thinkingStepsMap, viewport, isRunning]);

	return null; // This component doesn't render anything
};

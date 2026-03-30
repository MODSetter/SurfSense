import { makeAssistantDataUI, useAuiState } from "@assistant-ui/react";
import { ChevronRightIcon } from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import { ChainOfThoughtItem } from "@/components/prompt-kit/chain-of-thought";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { cn } from "@/lib/utils";

export interface ThinkingStep {
	id: string;
	title: string;
	items: string[];
	status: "pending" | "in_progress" | "completed";
}

/**
 * Chain of thought display component - single collapsible dropdown design
 */
export const ThinkingStepsDisplay: FC<{ steps: ThinkingStep[]; isThreadRunning?: boolean }> = ({
	steps,
	isThreadRunning = true,
}) => {
	const getEffectiveStatus = useCallback(
		(step: ThinkingStep): "pending" | "in_progress" | "completed" => {
			if (step.status === "in_progress" && !isThreadRunning) {
				return "completed";
			}
			return step.status;
		},
		[isThreadRunning]
	);

	const inProgressStep = steps.find((s) => getEffectiveStatus(s) === "in_progress");
	const allCompleted =
		steps.length > 0 &&
		!isThreadRunning &&
		steps.every((s) => getEffectiveStatus(s) === "completed");
	const isProcessing = isThreadRunning && !allCompleted;
	const [isOpen, setIsOpen] = useState(() => isProcessing);

	useEffect(() => {
		if (isProcessing) {
			setIsOpen(true);
			return;
		}

		if (allCompleted) {
			setIsOpen(false);
		}
	}, [allCompleted, isProcessing]);

	if (steps.length === 0) return null;

	const getHeaderText = () => {
		if (allCompleted) {
			return "Reviewed";
		}
		if (inProgressStep) {
			return inProgressStep.title;
		}
		if (isProcessing) {
			return "Processing";
		}
		return "Reviewed";
	};

	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<div className="rounded-lg">
				<button
					type="button"
					onClick={() => setIsOpen(prev => !prev)}
					className={cn(
						"flex w-full items-center gap-1.5 text-left text-sm transition-colors",
						"text-muted-foreground hover:text-foreground"
					)}
				>
					{isProcessing ? (
						<TextShimmerLoader text={getHeaderText()} size="sm" />
					) : (
						<span>{getHeaderText()}</span>
					)}

					<ChevronRightIcon
						className={cn("size-4 transition-transform duration-200", isOpen && "rotate-90")}
					/>
				</button>

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
										<div className="relative flex flex-col items-center w-2">
											{!isLast && (
												<div className="absolute left-1/2 top-[15px] -bottom-[7px] w-px -translate-x-1/2 bg-muted-foreground/30" />
											)}
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

										<div className="flex-1 min-w-0 pb-4">
											<div
												className={cn(
													"text-sm leading-5",
													effectiveStatus === "in_progress" && "text-foreground font-medium",
													effectiveStatus === "completed" && "text-muted-foreground",
													effectiveStatus === "pending" && "text-muted-foreground/60"
												)}
											>
												{step.title}
											</div>

											{step.items && step.items.length > 0 && (
												<div className="mt-1 space-y-0.5">
													{step.items.map((item) => (
														<ChainOfThoughtItem key={`${step.id}-${item}`} className="text-xs">
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
 * assistant-ui data UI component that renders thinking steps from message content.
 * Registered globally via makeAssistantDataUI — renders inside MessagePrimitive.Parts
 * at the position of the data part in the content array.
 */
function ThinkingStepsDataRenderer({ data }: { name: string; data: unknown }) {
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;

	const steps = (data as { steps: ThinkingStep[] } | null)?.steps ?? [];
	if (steps.length === 0) return null;

	return (
		<div className="mb-3 -mx-2 leading-normal">
			<ThinkingStepsDisplay steps={steps} isThreadRunning={isMessageStreaming} />
		</div>
	);
}

export const ThinkingStepsDataUI = makeAssistantDataUI({
	name: "thinking-steps",
	render: ThinkingStepsDataRenderer,
});

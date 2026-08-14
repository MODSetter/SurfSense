"use client";

import { CheckCircle2, ChevronRightIcon, History } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type FC, useEffect, useId, useMemo, useRef, useState } from "react";
import { ElapsedTime } from "@/components/prompt-kit/elapsed-time";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { PixelGridLoader } from "@/components/prompt-kit/pixel-grid-loader";
import { Button } from "@/components/ui/button";
import { HitlApprovalCard, usePendingInterrupt } from "@/features/chat-messages/hitl";
import { trackThinkingTraceInteraction } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";
import { FadeSwapText } from "./fade-swap-text";
import { groupItems } from "./grouping";
import { buildActiveSummary, buildCompletionSummary } from "./summary";
import { TimelineGroupRow } from "./timeline-group-row";
import type { ItemStatus, TimelineItem, VisibleReasoningBlock } from "./types";

/**
 * Force a stale "running" to read as "completed" once the thread
 * stops, so the chrome doesn't keep pulsing forever after a stream
 * is aborted or disconnected.
 */
function effectiveStatus(status: ItemStatus, isThreadRunning: boolean): ItemStatus {
	if ((status === "running" || status === "pending") && !isThreadRunning) return "interrupted";
	return status;
}

function latestCompletedAt(
	items: readonly TimelineItem[],
	reasoning: readonly VisibleReasoningBlock[]
): string | undefined {
	const timestamps = [
		...items.map((item) => item.completedAt),
		...reasoning.map((item) => item.completedAt),
	]
		.filter((value): value is string => typeof value === "string")
		.map((value) => new Date(value).getTime())
		.filter(Number.isFinite);
	return timestamps.length > 0 ? new Date(Math.max(...timestamps)).toISOString() : undefined;
}

const ReasoningDisclosure: FC<{
	blocks: readonly VisibleReasoningBlock[];
	active: boolean;
}> = ({ blocks, active }) => {
	const [isOpen, setIsOpen] = useState(false);
	if (blocks.length === 0) return null;
	return (
		<div className="pb-4">
			<Button
				variant="ghost"
				type="button"
				onClick={() =>
					setIsOpen((value) => {
						const next = !value;
						if (next) trackThinkingTraceInteraction("reasoning_expanded");
						return next;
					})
				}
				aria-expanded={isOpen}
				className="h-auto w-full justify-start gap-2 p-0 text-left text-sm text-muted-foreground hover:bg-transparent hover:text-foreground"
			>
				<History className="size-4 shrink-0" aria-hidden="true" />
				<FadeSwapText swapKey={active ? "active" : "completed"}>
					{active ? (
						<TextShimmerLoader text="Reasoning through the request" size="md" />
					) : (
						"Reasoned through the request"
					)}
				</FadeSwapText>
				<ChevronRightIcon
					className={cn(
						"ml-auto size-4 transition-transform motion-reduce:transition-none",
						isOpen && "rotate-90"
					)}
					aria-hidden="true"
				/>
			</Button>
			<div
				className={cn(
					"grid transition-[grid-template-rows] duration-200 motion-reduce:transition-none",
					isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
				)}
			>
				<div className="overflow-hidden">
					<section
						aria-label="Provider reasoning"
						className="mt-2 max-h-64 overflow-y-auto border-l border-muted-foreground/30 pl-4 text-sm leading-relaxed whitespace-pre-wrap wrap-break-word text-muted-foreground"
					>
						{blocks.map((block) => (
							<div key={block.id} className="not-last:mb-3">
								{block.text}
							</div>
						))}
					</section>
				</div>
			</div>
		</div>
	);
};

const AnimatedActivityLabel: FC<{ label: string; active: boolean }> = ({ label, active }) => {
	return (
		<FadeSwapText
			swapKey={`${active}:${label}`}
			className="h-5 max-w-[min(28rem,60vw)] overflow-hidden"
			contentClassName="truncate whitespace-nowrap"
		>
			{active ? <TextShimmerLoader text={label} size="md" className="truncate" /> : label}
		</FadeSwapText>
	);
};

/**
 * The "process" surface in the body | timeline split. Pure consumer
 * of ``TimelineItem[]`` — owns the collapsible chrome and tree
 * indent only. Pending HITL interrupts mount ``HitlApprovalCard`` at
 * the bottom; the card owns its own decision/pager state.
 */
export const Timeline: FC<{
	items: readonly TimelineItem[];
	reasoning?: readonly VisibleReasoningBlock[];
	isThreadRunning?: boolean;
	hasAnswer?: boolean;
	startedAt: string;
}> = ({ items, reasoning = [], isThreadRunning = true, hasAnswer = false, startedAt }) => {
	const traceId = useId();
	const reducedMotion = useReducedMotion();
	const pendingValue = usePendingInterrupt();
	const pendingInterrupts = pendingValue?.pendingInterrupts ?? [];
	const onSubmit = pendingValue?.onSubmit;
	const hasPending = pendingInterrupts.length > 0;

	// Apply the override here so downstream (grouping, headers, dots)
	// sees the corrected status without threading a callback. Keeps
	// ``buildTimeline`` pure.
	const effectiveItems = useMemo<TimelineItem[]>(
		() =>
			items.map((it) => ({
				...it,
				status: effectiveStatus(it.status, isThreadRunning),
			})),
		[items, isThreadRunning]
	);

	// "Settled" includes cancelled/errored, not just completed —
	// rejecting an interrupt leaves items in ``cancelled`` and the
	// timeline still needs to auto-collapse.
	const allSettled = useMemo(
		() =>
			(effectiveItems.length > 0 || reasoning.length > 0) &&
			!isThreadRunning &&
			!hasPending &&
			effectiveItems.every(
				(it) =>
					it.status === "completed" ||
					it.status === "cancelled" ||
					it.status === "interrupted" ||
					it.status === "error"
			),
		[effectiveItems, reasoning.length, isThreadRunning, hasPending]
	);
	const isProcessing = (isThreadRunning || hasPending) && !allSettled;
	const hasExpandableContent = effectiveItems.length > 0 || reasoning.length > 0 || hasPending;
	const [isOpen, setIsOpen] = useState(() => isProcessing && hasExpandableContent && !hasAnswer);
	const userToggled = useRef(false);
	const didAutoCollapse = useRef(false);
	useEffect(() => {
		if (hasPending) {
			setIsOpen(true);
			return;
		}
		if (hasAnswer && !didAutoCollapse.current && !userToggled.current) {
			didAutoCollapse.current = true;
			setIsOpen(false);
			return;
		}
		if (isProcessing && hasExpandableContent && !hasAnswer && !userToggled.current) {
			setIsOpen(true);
		}
	}, [hasAnswer, hasExpandableContent, hasPending, isProcessing]);

	const groups = useMemo(() => groupItems(effectiveItems), [effectiveItems]);

	if (!isThreadRunning && !hasExpandableContent) return null;
	if (hasAnswer && !hasExpandableContent) return null;

	const hasError = effectiveItems.some((item) => item.status === "error");
	const hasCancelled = effectiveItems.some(
		(item) => item.status === "cancelled" || item.status === "interrupted"
	);
	const headerText = (() => {
		if (hasPending) return "Waiting for your approval";
		if (hasAnswer && effectiveItems.length === 0 && reasoning.length > 0) {
			return "Reasoned through the request";
		}
		if (!isThreadRunning && hasError) return "Couldn’t complete the work";
		if (!isThreadRunning && hasCancelled) return "Stopped working";
		if (allSettled) return buildCompletionSummary(effectiveItems);
		if (isProcessing) return buildActiveSummary(effectiveItems);
		return buildCompletionSummary(effectiveItems);
	})();
	const reasoningOnlyAnswer = hasAnswer && effectiveItems.length === 0 && reasoning.length > 0;
	const gridActive = isProcessing && !hasPending && !reasoningOnlyAnswer;
	const completedAt =
		allSettled || reasoningOnlyAnswer ? latestCompletedAt(effectiveItems, reasoning) : undefined;
	const reasoningActive = reasoning.some((block) => block.status === "running") && isThreadRunning;

	return (
		<div className="mb-3 w-full leading-normal">
			<div className="rounded-lg">
				<output aria-live="polite" aria-busy={gridActive} className="block">
					<Button
						variant="ghost"
						type="button"
						disabled={!hasExpandableContent}
						onClick={() => {
							userToggled.current = true;
							setIsOpen((value) => {
								const next = !value;
								trackThinkingTraceInteraction(next ? "expanded" : "collapsed", {
									activityCount: effectiveItems.length,
									hasApproval: hasPending,
								});
								return next;
							});
						}}
						aria-expanded={hasExpandableContent ? isOpen : undefined}
						aria-controls={hasExpandableContent ? traceId : undefined}
						className={cn(
							"group/trace h-8 w-fit max-w-full justify-start gap-2.5 px-0 py-0 has-[>svg]:px-0 text-left text-sm font-normal hover:bg-transparent disabled:pointer-events-none disabled:opacity-100",
							"text-muted-foreground hover:text-foreground"
						)}
					>
						<PixelGridLoader active={gridActive} />
						<AnimatedActivityLabel label={headerText} active={gridActive} />
						<ElapsedTime startedAt={startedAt} completedAt={completedAt} running={gridActive} />
						{hasExpandableContent ? (
							<motion.span
								className="size-4 shrink-0 opacity-0 transition-opacity duration-200 group-hover/trace:opacity-100 group-focus-visible/trace:opacity-100 motion-reduce:transition-none"
								animate={{ rotate: isOpen ? 90 : 0 }}
								transition={{
									duration: reducedMotion ? 0 : 0.22,
									ease: [0.22, 1, 0.36, 1],
								}}
								aria-hidden="true"
							>
								<ChevronRightIcon className="size-4" />
							</motion.span>
						) : null}
					</Button>
				</output>

				<div
					id={traceId}
					className={cn(
						"grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-3 pl-1">
							<ReasoningDisclosure blocks={reasoning} active={reasoningActive} />
							{groups.map((group, idx) => {
								const showLine = idx < groups.length - 1 || hasPending || allSettled;
								return (
									<TimelineGroupRow
										key={group.parent.id}
										group={group}
										parentStatus={group.parent.status}
										showParentLine={showLine}
									/>
								);
							})}
							{hasPending && onSubmit && (
								<div className="pl-5 space-y-3">
									{pendingInterrupts.map((pi) => (
										<HitlApprovalCard
											key={pi.interruptId}
											pendingInterrupt={pi}
											onSubmit={(decisions) => onSubmit(pi.interruptId, decisions)}
										/>
									))}
								</div>
							)}
							{allSettled && !hasError && !hasCancelled ? (
								<div className="flex items-center gap-2 pb-1 text-sm text-muted-foreground">
									<CheckCircle2 className="size-4" aria-hidden="true" />
									<span>Done</span>
								</div>
							) : null}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

"use client";

import { CheckCircle2, ChevronRightIcon, History } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { type FC, useEffect, useId, useMemo, useRef, useState } from "react";
import { ElapsedTime } from "@/components/prompt-kit/elapsed-time";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { PixelGridLoader } from "@/components/prompt-kit/pixel-grid-loader";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { HitlApprovalCard, usePendingInterrupt } from "@/features/chat-messages/hitl";
import { getActivityIcon, getConnectorLogo } from "@/features/chat-messages/timeline/presentation";
import type { VisibleReasoningBlock } from "@/features/chat-messages/timeline/types";
import { useMediaQuery } from "@/hooks/use-media-query";
import type { ActivityData, ActivityStatus, ActivityTimingData } from "@/lib/chat/streaming-state";
import { trackThinkingTraceInteraction } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";
import { FadeSwapText } from "./fade-swap-text";
import { ItemHeader } from "./items/item-header";
import { buildActiveSummary, buildCompletionSummary } from "./summary";

/**
 * Force a stale "running" to read as "completed" once the thread
 * stops, so the chrome doesn't keep pulsing forever after a stream
 * is aborted or disconnected.
 */
function effectiveStatus(status: ActivityStatus, isThreadRunning: boolean): ActivityStatus {
	if (status === "running" && !isThreadRunning) return "interrupted";
	return status;
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

const TimelineDetails: FC<{
	activities: readonly ActivityData[];
	reasoning: readonly VisibleReasoningBlock[];
	reasoningActive: boolean;
	allSettled: boolean;
	hasError: boolean;
	hasCancelled: boolean;
}> = ({ activities, reasoning, reasoningActive, allSettled, hasError, hasCancelled }) => (
	<div className="pl-1">
		<ReasoningDisclosure blocks={reasoning} active={reasoningActive} />
		{activities.map((activity, index) => {
			const Icon = getActivityIcon(activity.iconKey, activity.category);
			const showLine = index < activities.length - 1 || allSettled;
			return (
				<div key={activity.id} className="relative min-w-0 pb-4">
					{showLine ? (
						<div className="absolute top-5 bottom-0 left-[7.5px] w-px bg-muted-foreground/25" />
					) : null}
					<ItemHeader
						title={activity.title}
						status={activity.status}
						icon={Icon}
						logo={getConnectorLogo(activity.integration)}
					/>
					{activity.details && activity.details.length > 0 ? (
						<ul className="mt-1 ml-6 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
							{activity.details.map((detail) => (
								<li key={`${activity.id}:${detail}`}>{detail}</li>
							))}
						</ul>
					) : null}
				</div>
			);
		})}
		{allSettled && !hasError && !hasCancelled ? (
			<div className="flex items-center gap-2 pb-1 text-sm text-muted-foreground">
				<CheckCircle2 className="size-4" aria-hidden="true" />
				<span>Done</span>
			</div>
		) : null}
	</div>
);

/**
 * The "process" surface in the body | timeline split. Pure consumer
 * of canonical backend activities. Mobile trace details open in a drawer;
 * pending HITL cards remain in chat because approvals are not thinking steps.
 */
export const Timeline: FC<{
	activities: readonly ActivityData[];
	reasoning?: readonly VisibleReasoningBlock[];
	timing: ActivityTimingData | null;
	isThreadRunning?: boolean;
	hasAnswer?: boolean;
}> = ({ activities, reasoning = [], timing, isThreadRunning = true, hasAnswer = false }) => {
	const traceId = useId();
	const mobileDrawerId = `${traceId}-drawer`;
	const reducedMotion = useReducedMotion();
	const isMobile = useMediaQuery("(max-width: 767px)");
	const pendingValue = usePendingInterrupt();
	const pendingInterrupts = pendingValue?.pendingInterrupts ?? [];
	const onSubmit = pendingValue?.onSubmit;
	const hasPending = pendingInterrupts.length > 0;
	const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

	const effectiveActivities = useMemo<ActivityData[]>(
		() =>
			activities.map((activity) => ({
				...activity,
				status: effectiveStatus(activity.status, isThreadRunning),
			})),
		[activities, isThreadRunning]
	);

	// "Settled" includes cancelled/errored, not just completed —
	// rejecting an interrupt leaves items in ``cancelled`` and the
	// timeline still needs to auto-collapse.
	const allSettled = useMemo(
		() =>
			(effectiveActivities.length > 0 || reasoning.length > 0) &&
			!isThreadRunning &&
			!hasPending &&
			effectiveActivities.every(
				(activity) =>
					activity.status === "completed" ||
					activity.status === "cancelled" ||
					activity.status === "interrupted" ||
					activity.status === "error"
			),
		[effectiveActivities, reasoning.length, isThreadRunning, hasPending]
	);
	const isProcessing = (isThreadRunning || hasPending) && !allSettled;
	const hasTraceContent = effectiveActivities.length > 0 || reasoning.length > 0;
	const hasContent = hasTraceContent || hasPending;
	const [isOpen, setIsOpen] = useState(() => isProcessing && hasTraceContent && !hasAnswer);
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
		if (isProcessing && hasTraceContent && !hasAnswer && !userToggled.current) {
			setIsOpen(true);
		}
	}, [hasAnswer, hasPending, hasTraceContent, isProcessing]);

	if (!isThreadRunning && !hasContent) return null;
	if (hasAnswer && !hasContent) return null;

	const hasError = effectiveActivities.some((activity) => activity.status === "error");
	const hasCancelled = effectiveActivities.some(
		(activity) => activity.status === "cancelled" || activity.status === "interrupted"
	);
	const headerText = (() => {
		if (hasPending) return "Waiting for your approval";
		if (hasAnswer && effectiveActivities.length === 0 && reasoning.length > 0) {
			return "Reasoned through the request";
		}
		if (!isThreadRunning && hasError) return "Couldn’t complete the work";
		if (!isThreadRunning && hasCancelled) return "Stopped working";
		if (allSettled) return buildCompletionSummary(effectiveActivities);
		if (isProcessing) return buildActiveSummary(effectiveActivities);
		return buildCompletionSummary(effectiveActivities);
	})();
	const reasoningOnlyAnswer = hasAnswer && effectiveActivities.length === 0 && reasoning.length > 0;
	const gridActive = isProcessing && !hasPending && !reasoningOnlyAnswer;
	const reasoningActive = reasoning.some((block) => block.status === "running") && isThreadRunning;

	return (
		<div className="mb-3 w-full leading-normal">
			<div className="rounded-lg">
				<output aria-live="polite" aria-busy={gridActive} className="block">
					<Button
						variant="ghost"
						type="button"
						disabled={!hasTraceContent}
						onClick={() => {
							if (isMobile) {
								setMobileDrawerOpen(true);
								trackThinkingTraceInteraction("expanded", {
									activityCount: effectiveActivities.length,
									hasApproval: hasPending,
								});
								return;
							}
							userToggled.current = true;
							setIsOpen((value) => {
								const next = !value;
								trackThinkingTraceInteraction(next ? "expanded" : "collapsed", {
									activityCount: effectiveActivities.length,
									hasApproval: hasPending,
								});
								return next;
							});
						}}
						aria-expanded={hasTraceContent ? (isMobile ? mobileDrawerOpen : isOpen) : undefined}
						aria-controls={hasTraceContent ? (isMobile ? mobileDrawerId : traceId) : undefined}
						className={cn(
							"group/trace h-8 max-md:min-h-11 w-fit max-w-full justify-start gap-2.5 px-0 py-0 has-[>svg]:px-0 text-left text-sm font-normal hover:bg-transparent disabled:pointer-events-none disabled:opacity-100",
							"text-muted-foreground hover:text-foreground"
						)}
					>
						<PixelGridLoader active={gridActive} />
						<span className="flex min-w-0 items-baseline gap-2.5">
							<AnimatedActivityLabel label={headerText} active={gridActive} />
							{timing ? (
								<ElapsedTime
									key={`${timing.status}:${timing.activeDurationMs}`}
									activeDurationMs={timing.activeDurationMs}
									running={timing.status === "running"}
								/>
							) : null}
						</span>
						{hasTraceContent ? (
							<motion.span
								className="size-4 shrink-0 opacity-0 transition-opacity duration-200 group-hover/trace:opacity-100 group-focus-visible/trace:opacity-100 max-md:opacity-100 motion-reduce:transition-none"
								animate={{ rotate: isMobile ? 0 : isOpen ? 90 : 0 }}
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
						"hidden md:grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-3">
							<TimelineDetails
								activities={effectiveActivities}
								reasoning={reasoning}
								reasoningActive={reasoningActive}
								allSettled={allSettled}
								hasError={hasError}
								hasCancelled={hasCancelled}
							/>
						</div>
					</div>
				</div>
				{isMobile && hasTraceContent ? (
					<Drawer
						open={mobileDrawerOpen}
						onOpenChange={(open) => {
							setMobileDrawerOpen(open);
							if (!open) {
								trackThinkingTraceInteraction("collapsed", {
									activityCount: effectiveActivities.length,
									hasApproval: hasPending,
								});
							}
						}}
						shouldScaleBackground={false}
					>
						<DrawerContent id={mobileDrawerId} className="h-[85vh] max-h-[85vh] overflow-hidden">
							<DrawerHandle />
							<DrawerTitle className="px-4 pt-3 pb-2 text-center text-base">Summary</DrawerTitle>
							<div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-6">
								<TimelineDetails
									activities={effectiveActivities}
									reasoning={reasoning}
									reasoningActive={reasoningActive}
									allSettled={allSettled}
									hasError={hasError}
									hasCancelled={hasCancelled}
								/>
							</div>
						</DrawerContent>
					</Drawer>
				) : null}
				{hasPending && onSubmit ? (
					<div className="mt-3 flex flex-col gap-3">
						{pendingInterrupts.map((pi) => (
							<HitlApprovalCard
								key={pi.interruptId}
								pendingInterrupt={pi}
								onSubmit={(decisions) => onSubmit(pi.interruptId, decisions)}
							/>
						))}
					</div>
				) : null}
			</div>
		</div>
	);
};

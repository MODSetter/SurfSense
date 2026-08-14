"use client";

import {
	type EnrichedPartState,
	MessagePrimitive,
	type PartState,
	type ToolCallMessagePartComponent,
	useAuiState,
} from "@assistant-ui/react";
import { ChevronRightIcon, History } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import {
	type ComponentType,
	type FC,
	type ReactNode,
	useCallback,
	useEffect,
	useId,
	useMemo,
	useRef,
	useState,
} from "react";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { NestedScroll } from "@/components/assistant-ui/nested-scroll";
import { ElapsedTime } from "@/components/prompt-kit/elapsed-time";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { PixelGridLoader } from "@/components/prompt-kit/pixel-grid-loader";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import {
	HitlApprovalCard,
	PendingInterruptProvider,
	type PendingInterruptState,
	usePendingInterrupt,
} from "@/features/chat-messages/hitl";
import { useMediaQuery } from "@/hooks/use-media-query";
import type {
	ActivityData,
	ActivityStatus,
	ActivityTimingData,
	ActivityTimingProjection,
} from "@/lib/chat/streaming-state";
import { trackActivityTraceInteraction } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";
import { FadeSwapText } from "./fade-swap-text";
import {
	buildActivityLookup,
	firstToolIndexByActivityId,
	getLastTraceIndex,
	getToolActivityId,
	getTraceGroupPath,
	type TracePartLike,
} from "./grouping";
import { getActivityIcon, getConnectorLogo } from "./presentation";

const noopSubmit = () => {};

function effectiveActivityStatus(status: ActivityStatus, threadRunning: boolean): ActivityStatus {
	return status === "running" && !threadRunning ? "interrupted" : status;
}

function partIsRunning(part: PartState | undefined): boolean {
	return part?.status.type === "running";
}

function interruptIndex(
	interrupt: PendingInterruptState,
	parts: readonly TracePartLike[]
): number | null {
	const toolCallIds = new Set([interrupt.interruptId, ...interrupt.bundleToolCallIds]);
	for (let index = 0; index < parts.length; index += 1) {
		if (parts[index].type === "tool-call" && toolCallIds.has(String(parts[index].toolCallId))) {
			return index;
		}
	}
	return null;
}

function PendingCards({ indices }: { indices: readonly number[] }) {
	const value = usePendingInterrupt();
	const parts = useAuiState(({ message }) => message.parts) as readonly TracePartLike[];
	if (!value) return null;
	const indexSet = new Set(indices);
	const cards = value.pendingInterrupts.filter((interrupt) => {
		const index = interruptIndex(interrupt, parts);
		return index !== null && indexSet.has(index);
	});
	if (cards.length === 0) return null;
	return (
		<div className="mt-3 flex flex-col gap-3">
			{cards.map((interrupt) => (
				<HitlApprovalCard
					key={interrupt.interruptId}
					pendingInterrupt={interrupt}
					onSubmit={(decisions) => value.onSubmit(interrupt.interruptId, decisions)}
				/>
			))}
		</div>
	);
}

function UnmatchedPendingCards() {
	const value = usePendingInterrupt();
	const parts = useAuiState(({ message }) => message.parts) as readonly TracePartLike[];
	if (!value) return null;
	const unmatched = value.pendingInterrupts.filter(
		(interrupt) => interruptIndex(interrupt, parts) === null
	);
	if (unmatched.length === 0) return null;
	return (
		<div className="mt-3 flex flex-col gap-3">
			{unmatched.map((interrupt) => (
				<HitlApprovalCard
					key={interrupt.interruptId}
					pendingInterrupt={interrupt}
					onSubmit={(decisions) => value.onSubmit(interrupt.interruptId, decisions)}
				/>
			))}
		</div>
	);
}

export const TraceItemRow: FC<{
	icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }> | null;
	logo?: { src: string; alt: string };
	title: ReactNode;
	status?: ActivityStatus | "reasoning";
	children?: ReactNode;
}> = ({ icon: Icon, logo, title, status, children }) => (
	<div
		className={cn(
			"relative grid min-w-0 grid-cols-[1rem_minmax(0,1fr)] gap-x-2 pb-4 last:pb-0",
			"after:pointer-events-none after:absolute after:top-6 after:bottom-1 after:left-[7.5px]",
			"after:w-px after:bg-muted-foreground/20 last:after:hidden"
		)}
	>
		<div className="relative z-10 mt-0.5 flex size-4 items-center justify-center">
			{logo ? (
				// biome-ignore lint/performance/noImgElement: connector paths may be extension-provided.
				<img src={logo.src} alt="" className="size-4 object-contain" />
			) : Icon ? (
				<Icon className="size-4" aria-hidden={true} />
			) : null}
		</div>
		<div
			className={cn(
				"min-w-0 text-sm leading-5",
				status === "running" && "font-medium text-foreground",
				(status === "completed" || status === "reasoning") && "text-muted-foreground",
				status === "awaiting_approval" && "text-muted-foreground",
				status === "error" && "text-destructive",
				(status === "cancelled" || status === "interrupted") && "text-muted-foreground"
			)}
		>
			{title}
			{children}
		</div>
	</div>
);

const ReasoningEpisode: FC<{ text: string; running: boolean }> = ({ text, running }) => (
	<TraceItemRow
		icon={History}
		status="reasoning"
		title={running ? <TextShimmerLoader text="Reasoning" size="md" /> : "Reasoning"}
	>
		<NestedScroll
			role="region"
			aria-label="Provider reasoning"
			className="mt-2 max-h-52 overflow-y-auto overscroll-contain rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm leading-6 whitespace-pre-wrap wrap-break-word text-muted-foreground scrollbar-thin"
		>
			{text}
		</NestedScroll>
	</TraceItemRow>
);

const ActivityRow: FC<{ activity: ActivityData; threadRunning: boolean }> = ({
	activity,
	threadRunning,
}) => {
	const status = effectiveActivityStatus(activity.status, threadRunning);
	const Icon = getActivityIcon(activity.iconKey, activity.category);
	return (
		<TraceItemRow
			icon={Icon}
			logo={getConnectorLogo(activity.integration)}
			title={
				status === "running" ? (
					<TextShimmerLoader text={activity.title} size="md" className="truncate" />
				) : (
					activity.title
				)
			}
			status={status}
		>
			{activity.details?.length ? (
				<ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
					{activity.details.map((detail) => (
						<li key={`${activity.id}:${detail}`}>{detail}</li>
					))}
				</ul>
			) : null}
		</TraceItemRow>
	);
};

const TraceLeaf: FC<{
	part: EnrichedPartState;
	index: number;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	showReasoning: boolean;
	threadRunning: boolean;
}> = ({ part, index, activities, firstActivityIndices, showReasoning, threadRunning }) => {
	if (part.type === "reasoning") {
		if (!showReasoning || part.text.length === 0) return null;
		return <ReasoningEpisode text={part.text} running={partIsRunning(part)} />;
	}
	if (part.type !== "tool-call") return null;
	const activityId = getToolActivityId(part);
	const activity = activityId ? activities.get(activityId) : undefined;
	return activity && firstActivityIndices.get(activity.id) === index ? (
		<ActivityRow activity={activity} threadRunning={threadRunning} />
	) : null;
};

const TraceDetails: FC<{
	indices: readonly number[];
	renderPart: (part: EnrichedPartState, index: number) => ReactNode;
	parts: readonly PartState[];
}> = ({ indices, renderPart, parts }) => (
	<div className="pl-1">
		{indices.map((index) => renderPart(parts[index] as EnrichedPartState, index))}
	</div>
);

const TraceSegment: FC<{
	indices: readonly number[];
	activities: ReadonlyMap<string, ActivityData>;
	timing: ActivityTimingData | null;
	timingProjection: ActivityTimingProjection | null;
	renderPart: (part: EnrichedPartState, index: number) => ReactNode;
	parts: readonly PartState[];
	threadRunning: boolean;
	isLastTraceSegment: boolean;
}> = ({
	indices,
	activities,
	timing,
	timingProjection,
	renderPart,
	parts,
	threadRunning,
	isLastTraceSegment,
}) => {
	const id = useId();
	const isMobile = useMediaQuery("(max-width: 767px)");
	const reducedMotion = useReducedMotion();
	const [open, setOpen] = useState(false);
	const [drawerOpen, setDrawerOpen] = useState(false);
	const userToggled = useRef(false);
	const segmentActivities = indices.flatMap((index) => {
		const activityId = getToolActivityId(parts[index] as TracePartLike);
		const activity = activityId ? activities.get(activityId) : undefined;
		return activity ? [activity] : [];
	});
	const active =
		(threadRunning &&
			(indices.some((index) => partIsRunning(parts[index])) ||
				segmentActivities.some((activity) => activity.status === "running"))) ||
		segmentActivities.some((activity) => activity.status === "awaiting_approval");
	const label =
		segmentActivities.at(-1)?.title ?? (active ? "Spellweaving" : "Reasoned through the request");
	const showTiming =
		timing !== null && (active || (timing.status === "completed" && isLastTraceSegment));
	const details = <TraceDetails indices={indices} renderPart={renderPart} parts={parts} />;
	useEffect(() => {
		if (isMobile || userToggled.current) return;
		setOpen(active);
	}, [active, isMobile]);
	const toggle = () => {
		if (isMobile) {
			setDrawerOpen(true);
			trackActivityTraceInteraction("segment_expanded", {
				activityCount: segmentActivities.length,
				reasoningCount: indices.filter((index) => parts[index]?.type === "reasoning").length,
				surface: "mobile_drawer",
			});
			return;
		}
		userToggled.current = true;
		setOpen((current) => {
			const next = !current;
			trackActivityTraceInteraction(next ? "segment_expanded" : "segment_collapsed", {
				activityCount: segmentActivities.length,
				reasoningCount: indices.filter((index) => parts[index]?.type === "reasoning").length,
				surface: "desktop_inline",
			});
			return next;
		});
	};
	return (
		<section className="mb-3 w-full leading-normal">
			<Button
				variant="ghost"
				type="button"
				onClick={toggle}
				aria-expanded={isMobile ? drawerOpen : open}
				aria-controls={id}
				className="group/trace h-8 w-fit max-w-full justify-start gap-2.5 px-0 py-0 text-left text-sm font-normal text-muted-foreground hover:bg-transparent hover:text-foreground has-[>svg]:px-0 max-md:min-h-11"
			>
				<PixelGridLoader active={active} />
				<FadeSwapText
					swapKey={`${active}:${label}`}
					className="h-5 max-w-[min(28rem,60vw)] overflow-hidden"
					contentClassName="truncate whitespace-nowrap"
				>
					{active ? <TextShimmerLoader text={label} size="md" className="truncate" /> : label}
				</FadeSwapText>
				{showTiming ? (
					<ElapsedTime timing={timing} projection={timingProjection ?? undefined} />
				) : null}
				<motion.span
					className="size-4 shrink-0 opacity-0 transition-opacity group-hover/trace:opacity-100 group-focus-visible/trace:opacity-100 max-md:opacity-100"
					animate={{ rotate: !isMobile && open ? 90 : 0 }}
					transition={{ duration: reducedMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
					aria-hidden="true"
				>
					<ChevronRightIcon className="size-4" />
				</motion.span>
			</Button>
			<div
				id={id}
				className={cn(
					"hidden transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none md:grid",
					open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
				)}
			>
				<div className="overflow-hidden">
					<div className="mt-3">{details}</div>
				</div>
			</div>
			{isMobile ? (
				<Drawer
					open={drawerOpen}
					onOpenChange={(next) => {
						setDrawerOpen(next);
						if (!next) {
							trackActivityTraceInteraction("segment_collapsed", {
								activityCount: segmentActivities.length,
								surface: "mobile_drawer",
							});
						}
					}}
					shouldScaleBackground={false}
				>
					<DrawerContent className="h-[85vh] max-h-[85vh] overflow-hidden">
						<DrawerHandle />
						<DrawerTitle className="px-4 pt-3 pb-2 text-center text-base">Summary</DrawerTitle>
						<div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-6">{details}</div>
					</DrawerContent>
				</Drawer>
			) : null}
		</section>
	);
};

const InterleavedPartsInner: FC<{
	bodyTools: Readonly<Record<string, ToolCallMessagePartComponent>>;
	showReasoning: boolean;
}> = ({ bodyTools, showReasoning }) => {
	const parts = useAuiState(({ message }) => message.parts);
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message.isLast);
	const threadRunning = isThreadRunning && isLastMessage;
	const rawParts = parts as readonly TracePartLike[];
	const journal = useMemo(() => buildActivityLookup(rawParts), [rawParts]);
	const firstActivityIndices = useMemo(() => firstToolIndexByActivityId(rawParts), [rawParts]);
	const bodyToolNames = useMemo(() => new Set(Object.keys(bodyTools)), [bodyTools]);
	const lastTraceIndex = useMemo(
		() => getLastTraceIndex(rawParts, bodyToolNames, showReasoning),
		[rawParts, bodyToolNames, showReasoning]
	);
	const groupBy = useCallback(
		(part: PartState) =>
			part.type === "reasoning" && !showReasoning ? [] : getTraceGroupPath(part, bodyToolNames),
		[bodyToolNames, showReasoning]
	);

	const renderLeaf = useCallback(
		(part: EnrichedPartState, index: number): ReactNode => (
			<TraceLeaf
				part={part}
				index={index}
				activities={journal.byId}
				firstActivityIndices={firstActivityIndices}
				showReasoning={showReasoning}
				threadRunning={threadRunning}
			/>
		),
		[firstActivityIndices, journal.byId, showReasoning, threadRunning]
	);

	return (
		<>
			{/* data-activities needs no makeAssistantDataUI registrar: GroupedParts exposes
			    the normalized data leaf while buildActivityLookup consumes it directly. */}
			<MessagePrimitive.GroupedParts groupBy={groupBy} indicator="never">
				{({ part }) => {
					switch (part.type) {
						case "group-trace":
							return (
								<>
									<TraceSegment
										indices={part.indices}
										activities={journal.byId}
										timing={journal.timing}
										timingProjection={journal.timingProjection}
										renderPart={renderLeaf}
										parts={parts}
										threadRunning={threadRunning}
										isLastTraceSegment={part.indices.includes(lastTraceIndex)}
									/>
									<PendingCards indices={part.indices} />
								</>
							);
						case "text":
							return <MarkdownText />;
						case "tool-call": {
							const Body = bodyTools[part.toolName];
							const index = parts.findIndex(
								(candidate) =>
									candidate.type === "tool-call" && candidate.toolCallId === part.toolCallId
							);
							return (
								<>
									{Body ? <Body {...part} /> : null}
									<PendingCards indices={index >= 0 ? [index] : []} />
								</>
							);
						}
						case "data":
						case "reasoning":
						case "indicator":
							return null;
						default:
							return null;
					}
				}}
			</MessagePrimitive.GroupedParts>
			<UnmatchedPendingCards />
		</>
	);
};

export const InterleavedMessageParts: FC<{
	bodyTools: Readonly<Record<string, ToolCallMessagePartComponent>>;
	showReasoning?: boolean;
}> = ({ bodyTools, showReasoning = true }) => {
	const messageId = useAuiState(({ message }) => message.id);
	const pending = usePendingInterrupt();
	const pendingForMessage = useMemo(
		() => (pending?.pendingInterrupts ?? []).filter((item) => item.assistantMsgId === messageId),
		[pending?.pendingInterrupts, messageId]
	);
	return (
		<PendingInterruptProvider
			pendingInterrupts={pendingForMessage}
			onSubmit={pending?.onSubmit ?? noopSubmit}
		>
			<InterleavedPartsInner bodyTools={bodyTools} showReasoning={showReasoning} />
		</PendingInterruptProvider>
	);
};

"use client";

import {
	MessagePrimitive,
	PartByIndexProvider,
	type PartState,
	type ToolCallMessagePartComponent,
	useAuiState,
} from "@assistant-ui/react";
import { ChevronRightIcon, History } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import {
	type ComponentType,
	type FC,
	Fragment,
	type ReactNode,
	useEffect,
	useId,
	useMemo,
	useState,
} from "react";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { NestedScroll } from "@/components/assistant-ui/nested-scroll";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { TimelineActivityIndicator } from "@/components/ui/timeline-activity-indicator";
import {
	HitlApprovalCard,
	isStructuredQuestionInterrupt,
	PendingInterruptProvider,
	type PendingInterruptState,
	usePendingInterrupt,
} from "@/features/chat-messages/hitl";
import { useMediaQuery } from "@/hooks/use-media-query";
import type { ActivityData, ActivityStatus } from "@/lib/chat/activity-journal";
import { trackActivityTraceInteraction } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";
import { FadeSwapText } from "./fade-swap-text";
import {
	buildActivityLookup,
	buildTurnRenderItems,
	firstToolIndexByActivityId,
	getToolActivityId,
	getTraceLeafKind,
	hasExpandableTraceDetails,
	type TracePartLike,
	type TurnRenderItem,
} from "./grouping";
import { getActivityIcon, getActivityPresentation, getConnectorLogo } from "./presentation";
import { AssistantTurnTiming, useAssistantTurnTiming } from "./turn-timing";
import type { TurnTimingDisplay } from "./turn-timing-state";
import { useReasoningAutoScroll } from "./use-reasoning-auto-scroll";

const noopSubmit = () => {};
const TEXT_PART_COMPONENTS = { Text: MarkdownText };
const TURN_HEADER_ROW_CLASS =
	"group/trace h-8 w-fit max-w-full justify-start gap-2.5 px-0 py-0 text-left text-sm font-semibold text-muted-foreground hover:bg-transparent hover:text-foreground has-[>svg]:px-0 max-md:min-h-11";

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
		if (isStructuredQuestionInterrupt(interrupt)) return false;
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
		(interrupt) =>
			!isStructuredQuestionInterrupt(interrupt) && interruptIndex(interrupt, parts) === null
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
			"after:w-px after:bg-muted-foreground/20 last:after:hidden",
			status === "running" && "text-foreground",
			(status === "completed" || status === "reasoning" || status === "error") &&
				"text-muted-foreground",
			status === "awaiting_approval" && "text-muted-foreground",
			(status === "cancelled" || status === "interrupted") && "text-muted-foreground"
		)}
	>
		<div className="relative z-10 mt-0.5 flex size-4 items-center justify-center text-muted-foreground">
			{logo ? (
				// biome-ignore lint/performance/noImgElement: connector paths may be extension-provided.
				<img src={logo.src} alt="" className="size-4 object-contain" />
			) : Icon ? (
				<Icon className="size-4" aria-hidden={true} />
			) : null}
		</div>
		<div className="min-w-0 text-sm leading-5">
			<div>{title}</div>
			{children}
		</div>
	</div>
);

const ReasoningEpisode: FC<{ text: string; running: boolean }> = ({ text, running }) => {
	const {
		scrollRef,
		hasContentAbove,
		hasContentBelow,
		scrollMode,
		handleKeyDown,
		handlePointerDown,
		handleScroll,
		handleWheel,
	} = useReasoningAutoScroll(text, running);

	return (
		<TraceItemRow
			icon={History}
			status="reasoning"
			title={
				running ? (
					<TextShimmerLoader text="Reasoning" size="md" className="font-normal!" />
				) : (
					"Reasoning"
				)
			}
		>
			<div className="relative mt-2">
				<NestedScroll
					ref={scrollRef}
					onKeyDown={handleKeyDown}
					onPointerDown={handlePointerDown}
					onScroll={handleScroll}
					onWheel={handleWheel}
					role="region"
					aria-label="Provider reasoning"
					aria-busy={running}
					tabIndex={0}
					className={cn(
						"max-h-52 overflow-y-auto overscroll-contain rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm leading-6 whitespace-pre-wrap wrap-break-word text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
						scrollMode === "following" ? "scrollbar-hide" : "scrollbar-thin"
					)}
				>
					{text}
				</NestedScroll>
				<div
					aria-hidden="true"
					className={cn(
						"pointer-events-none absolute inset-x-px top-px h-4 rounded-t-lg bg-gradient-to-b from-muted/80 to-transparent transition-opacity",
						hasContentAbove ? "opacity-100" : "opacity-0"
					)}
				/>
				<div
					aria-hidden="true"
					className={cn(
						"pointer-events-none absolute inset-x-px bottom-px h-4 rounded-b-lg bg-gradient-to-t from-muted/80 to-transparent transition-opacity",
						hasContentBelow ? "opacity-100" : "opacity-0"
					)}
				/>
			</div>
		</TraceItemRow>
	);
};

const ActivityRow: FC<{ activity: ActivityData; threadRunning: boolean }> = ({
	activity,
	threadRunning,
}) => {
	const { status, title } = getActivityPresentation(activity, threadRunning);
	const Icon = getActivityIcon(activity.iconKey, activity.category);
	return (
		<TraceItemRow
			icon={Icon}
			logo={getConnectorLogo(activity.integration)}
			title={
				status === "running" ? (
					<TextShimmerLoader text={title} size="md" className="truncate font-normal!" />
				) : (
					title
				)
			}
			status={status}
		/>
	);
};

const TraceLeaf: FC<{
	part: PartState;
	index: number;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	showReasoning: boolean;
	threadRunning: boolean;
}> = ({ part, index, activities, firstActivityIndices, showReasoning, threadRunning }) => {
	if (part.type === "reasoning") {
		if (
			getTraceLeafKind({
				part,
				index,
				activities,
				firstActivityIndices,
				showReasoning,
			}) !== "reasoning"
		) {
			return null;
		}
		return <ReasoningEpisode text={part.text} running={partIsRunning(part)} />;
	}
	if (
		getTraceLeafKind({
			part,
			index,
			activities,
			firstActivityIndices,
			showReasoning,
		}) !== "activity"
	) {
		return null;
	}
	const activityId = getToolActivityId(part);
	const activity = activityId ? activities.get(activityId) : undefined;
	return activity ? <ActivityRow activity={activity} threadRunning={threadRunning} /> : null;
};

const TraceLeafByIndex: FC<{
	index: number;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	showReasoning: boolean;
	threadRunning: boolean;
}> = ({ index, activities, firstActivityIndices, showReasoning, threadRunning }) => (
	<PartByIndexProvider index={index}>
		<ScopedTraceLeaf
			index={index}
			activities={activities}
			firstActivityIndices={firstActivityIndices}
			showReasoning={showReasoning}
			threadRunning={threadRunning}
		/>
	</PartByIndexProvider>
);

const ScopedTraceLeaf: FC<{
	index: number;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	showReasoning: boolean;
	threadRunning: boolean;
}> = ({ index, activities, firstActivityIndices, showReasoning, threadRunning }) => {
	const part = useAuiState((state) => state.part);
	return (
		<TraceLeaf
			part={part}
			index={index}
			activities={activities}
			firstActivityIndices={firstActivityIndices}
			showReasoning={showReasoning}
			threadRunning={threadRunning}
		/>
	);
};

const TraceDetails: FC<{
	indices: readonly number[];
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	showReasoning: boolean;
	threadRunning: boolean;
}> = ({ indices, activities, firstActivityIndices, showReasoning, threadRunning }) => (
	<div className="pl-1">
		{indices.map((index) => (
			<TraceLeafByIndex
				key={index}
				index={index}
				activities={activities}
				firstActivityIndices={firstActivityIndices}
				showReasoning={showReasoning}
				threadRunning={threadRunning}
			/>
		))}
	</div>
);

const TurnHeaderContent: FC<{
	active: boolean;
	label: string;
	reducedMotion: boolean | null;
	showIndicator: boolean;
	swapKey: string;
	turnTimingDisplay: TurnTimingDisplay | null;
	trailing: ReactNode;
}> = ({ active, label, reducedMotion, showIndicator, swapKey, turnTimingDisplay, trailing }) => {
	const [retainIndicatorSlot, setRetainIndicatorSlot] = useState(showIndicator);
	const exiting = retainIndicatorSlot && !showIndicator;
	const renderIndicatorSlot = showIndicator || retainIndicatorSlot;

	useEffect(() => {
		if (showIndicator) setRetainIndicatorSlot(true);
	}, [showIndicator]);

	return (
		<>
			{renderIndicatorSlot ? (
				<motion.span
					initial={false}
					animate={{ opacity: showIndicator ? 1 : 0 }}
					transition={{ duration: reducedMotion ? 0 : 0.14 }}
					className="flex size-6 shrink-0 items-center"
				>
					<TimelineActivityIndicator />
				</motion.span>
			) : null}
			<motion.span
				initial={false}
				animate={{ x: exiting ? -34 : 0 }}
				transition={{
					duration: exiting && !reducedMotion ? 0.22 : 0,
					ease: [0.22, 1, 0.36, 1],
				}}
				onAnimationComplete={() => {
					if (exiting && !showIndicator) setRetainIndicatorSlot(false);
				}}
				className="flex min-w-0 items-center gap-2.5"
			>
				<FadeSwapText
					swapKey={swapKey}
					className="h-5 max-w-[min(28rem,60vw)] overflow-hidden"
					contentClassName="truncate whitespace-nowrap"
				>
					{active ? (
						<TextShimmerLoader text={label} size="md" className="truncate font-semibold!" />
					) : (
						label
					)}
				</FadeSwapText>
				{turnTimingDisplay ? <AssistantTurnTiming display={turnTimingDisplay} /> : null}
				{trailing}
			</motion.span>
		</>
	);
};

type SegmentRenderItem = Extract<TurnRenderItem, { kind: "segment" }>;

interface SegmentInteractionState {
	open?: boolean;
	drawerOpen?: boolean;
}

const TurnSegment: FC<{
	item: SegmentRenderItem;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	parts: readonly PartState[];
	showReasoning: boolean;
	threadRunning: boolean;
	turnTimingDisplay: TurnTimingDisplay | null;
	interaction: SegmentInteractionState | undefined;
	onOpenChange: (open: boolean) => void;
	onDrawerOpenChange: (open: boolean) => void;
}> = ({
	item,
	activities,
	firstActivityIndices,
	parts,
	showReasoning,
	threadRunning,
	turnTimingDisplay,
	interaction,
	onOpenChange,
	onDrawerOpenChange,
}) => {
	const id = useId();
	const isMobile = useMediaQuery("(max-width: 767px)");
	const reducedMotion = useReducedMotion();
	const { indices, phase, segmentId } = item;
	const hasTrace = segmentId !== null;
	const hasExpandableDetails = hasExpandableTraceDetails({
		parts,
		indices,
		activities,
		firstActivityIndices,
		showReasoning,
	});
	const segmentActivities = indices.flatMap((index) => {
		const activityId = getToolActivityId(parts[index] as TracePartLike);
		const activity = activityId ? activities.get(activityId) : undefined;
		return activity ? [activity] : [];
	});
	const active = hasTrace
		? (threadRunning &&
				(indices.some((index) => partIsRunning(parts[index])) ||
					segmentActivities.some((activity) => activity.status === "running"))) ||
			segmentActivities.some((activity) => activity.status === "awaiting_approval")
		: phase === "spellweaving";
	const showIndicator =
		item.live &&
		(threadRunning ||
			segmentActivities.some((activity) => activity.status === "awaiting_approval"));
	const latestActivity = segmentActivities.at(-1);
	const latestActivityTitle = latestActivity
		? getActivityPresentation(latestActivity, threadRunning).title
		: undefined;
	const label = hasTrace
		? (latestActivityTitle ?? (active ? "Spellweaving" : "Reasoned through the request"))
		: phase === "spellweaving"
			? "Spellweaving"
			: "Responded";
	const open = interaction?.open ?? active;
	const drawerOpen = interaction?.drawerOpen ?? false;
	const details = (
		<TraceDetails
			indices={indices}
			activities={activities}
			firstActivityIndices={firstActivityIndices}
			showReasoning={showReasoning}
			threadRunning={threadRunning}
		/>
	);
	const toggle = () => {
		if (!hasExpandableDetails) return;
		if (isMobile) {
			onDrawerOpenChange(true);
			trackActivityTraceInteraction("segment_expanded", {
				activityCount: segmentActivities.length,
				reasoningCount: indices.filter((index) => parts[index]?.type === "reasoning").length,
				surface: "mobile_drawer",
			});
			return;
		}
		const next = !open;
		onOpenChange(next);
		trackActivityTraceInteraction(next ? "segment_expanded" : "segment_collapsed", {
			activityCount: segmentActivities.length,
			reasoningCount: indices.filter((index) => parts[index]?.type === "reasoning").length,
			surface: "desktop_inline",
		});
	};
	return (
		<section
			aria-label={hasTrace ? undefined : "Assistant response status"}
			className="mb-3 w-full select-none leading-normal"
			data-testid="assistant-turn-header"
			data-live={item.live ? "true" : "false"}
			data-segment-id={segmentId ?? "standalone"}
		>
			<Button
				variant="ghost"
				type="button"
				onClick={hasExpandableDetails ? toggle : undefined}
				disabled={!hasExpandableDetails}
				aria-expanded={hasExpandableDetails ? (isMobile ? drawerOpen : open) : undefined}
				aria-controls={hasExpandableDetails ? id : undefined}
				className={cn(TURN_HEADER_ROW_CLASS, "disabled:opacity-100")}
			>
				<TurnHeaderContent
					active={active}
					label={label}
					reducedMotion={reducedMotion}
					showIndicator={showIndicator}
					swapKey={`${active}:${label}`}
					turnTimingDisplay={turnTimingDisplay}
					trailing={
						hasExpandableDetails ? (
							<motion.span
								className="size-4 shrink-0 opacity-0 transition-opacity group-hover/trace:opacity-100 group-focus-visible/trace:opacity-100 max-md:opacity-100"
								animate={{ rotate: !isMobile && open ? 90 : 0 }}
								transition={{
									duration: reducedMotion ? 0 : 0.22,
									ease: [0.22, 1, 0.36, 1],
								}}
								aria-hidden="true"
							>
								<ChevronRightIcon className="size-4" />
							</motion.span>
						) : null
					}
				/>
			</Button>
			<div
				id={id}
				aria-hidden={!hasExpandableDetails}
				className={cn(
					"hidden transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none md:grid",
					hasExpandableDetails && open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
				)}
			>
				<div className="overflow-hidden">
					<div className="mt-3">{details}</div>
				</div>
			</div>
			{isMobile && hasExpandableDetails ? (
				<Drawer
					open={drawerOpen}
					onOpenChange={(next) => {
						onDrawerOpenChange(next);
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

const TurnSegmentSlot: FC<{
	item: SegmentRenderItem;
	activities: ReadonlyMap<string, ActivityData>;
	firstActivityIndices: ReadonlyMap<string, number>;
	parts: readonly PartState[];
	showReasoning: boolean;
	threadRunning: boolean;
	turnTimingDisplay: TurnTimingDisplay | null;
	interaction: SegmentInteractionState | undefined;
	onOpenChange: (open: boolean) => void;
	onDrawerOpenChange: (open: boolean) => void;
}> = ({
	item,
	activities,
	firstActivityIndices,
	parts,
	showReasoning,
	threadRunning,
	turnTimingDisplay,
	interaction,
	onOpenChange,
	onDrawerOpenChange,
}) => {
	return (
		<>
			<TurnSegment
				item={item}
				activities={activities}
				firstActivityIndices={firstActivityIndices}
				parts={parts}
				showReasoning={showReasoning}
				threadRunning={threadRunning}
				turnTimingDisplay={turnTimingDisplay}
				interaction={interaction}
				onOpenChange={onOpenChange}
				onDrawerOpenChange={onDrawerOpenChange}
			/>
			{item.segmentId ? <PendingCards indices={item.indices} /> : null}
		</>
	);
};

const InterleavedPartsInner: FC<{
	bodyTools: Readonly<Record<string, ToolCallMessagePartComponent>>;
	showReasoning: boolean;
}> = ({ bodyTools, showReasoning }) => {
	const parts = useAuiState(({ message }) => message.parts);
	const messageId = useAuiState(({ message }) => message.id);
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message.isLast);
	const threadRunning = isThreadRunning && isLastMessage;
	const rawParts = parts as readonly TracePartLike[];
	const journal = useMemo(() => buildActivityLookup(rawParts), [rawParts]);
	const turnTimingDisplay = useAssistantTurnTiming({
		messageId: String(messageId),
		timing: journal.timing,
		projection: journal.timingProjection,
		threadRunning,
	});
	const firstActivityIndices = useMemo(() => firstToolIndexByActivityId(rawParts), [rawParts]);
	const bodyToolNames = useMemo(() => new Set(Object.keys(bodyTools)), [bodyTools]);
	const renderItems = useMemo(
		() =>
			buildTurnRenderItems({
				parts: rawParts,
				bodyToolNames,
				showReasoning,
				threadRunning,
				timingStatus: journal.timing?.status,
			}),
		[rawParts, bodyToolNames, showReasoning, threadRunning, journal.timing?.status]
	);
	const bodyToolOverride = useMemo<ToolCallMessagePartComponent>(
		() =>
			function BodyToolOverride(props) {
				const Body = bodyTools[props.toolName];
				return Body ? <Body {...props} /> : null;
			},
		[bodyTools]
	);
	const bodyPartComponents = useMemo(
		() => ({
			tools: { Override: bodyToolOverride },
		}),
		[bodyToolOverride]
	);
	const [segmentInteractions, setSegmentInteractions] = useState<
		Record<string, SegmentInteractionState>
	>({});
	const updateSegmentInteraction = (
		segmentId: string,
		field: keyof SegmentInteractionState,
		value: boolean
	) =>
		setSegmentInteractions((current) => ({
			...current,
			[segmentId]: { ...current[segmentId], [field]: value },
		}));

	return (
		<>
			{renderItems.map((item) => {
				if (item.kind === "segment") {
					const segmentId = item.segmentId;
					return (
						<TurnSegmentSlot
							key={item.key}
							item={item}
							activities={journal.byId}
							firstActivityIndices={firstActivityIndices}
							parts={parts}
							showReasoning={showReasoning}
							threadRunning={threadRunning}
							turnTimingDisplay={item.live ? turnTimingDisplay : null}
							interaction={segmentId ? segmentInteractions[segmentId] : undefined}
							onOpenChange={(open) => {
								if (segmentId) updateSegmentInteraction(segmentId, "open", open);
							}}
							onDrawerOpenChange={(drawerOpen) => {
								if (segmentId) {
									updateSegmentInteraction(segmentId, "drawerOpen", drawerOpen);
								}
							}}
						/>
					);
				}

				return (
					<Fragment key={item.key}>
						<MessagePrimitive.PartByIndex
							index={item.index}
							components={item.kind === "body-tool" ? bodyPartComponents : TEXT_PART_COMPONENTS}
						/>
						{item.kind === "body-tool" ? <PendingCards indices={[item.index]} /> : null}
					</Fragment>
				);
			})}
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

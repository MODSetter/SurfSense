import {
	makeAssistantDataUI,
	type ToolCallMessagePartComponent,
	useAuiState,
} from "@assistant-ui/react";
import { ChevronRightIcon } from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TOOLS_BY_NAME, TOOLS_FALLBACK } from "@/components/assistant-ui/assistant-message";
import { ChainOfThoughtItem } from "@/components/prompt-kit/chain-of-thought";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { HitlRenderTargetProvider, isInterruptResult } from "@/lib/hitl";
import { cn } from "@/lib/utils";

export interface ThinkingStep {
	id: string;
	title: string;
	items: string[];
	status: "pending" | "in_progress" | "completed";
	/**
	 * Optional relay metadata forwarded from ``data-thinking-step`` SSE
	 * (e.g. ``spanId`` set by ``AgentEventRelayState.span_metadata_if_active``).
	 * Steps under an open delegating ``task`` carry ``metadata.spanId`` and are
	 * grouped under the preceding parent (``task`` step) as indented children.
	 */
	metadata?: Record<string, unknown>;
}

/**
 * Per-step info joined from the assistant message ``tool-call`` parts via
 * the shared ``metadata.thinkingStepId`` correlation
 * (set on the server in ``AgentEventRelayState.tool_activity_metadata``).
 *
 * Carries enough of the part to:
 *  - identify the opening ``task`` step and substitute the subagent display
 *    name on the parent header (uses ``toolName`` and ``args``);
 *  - render the matching tool component inline under the step row when the
 *    card's result is an HITL interrupt (uses ``toolCallId``, ``argsText``,
 *    ``result``, ``langchainToolCallId``).
 */
interface StepToolInfo {
	toolCallId: string;
	toolName: string;
	args: Record<string, unknown>;
	argsText?: string;
	result?: unknown;
	langchainToolCallId?: string;
}

export type ThinkingStepToolInfoMap = ReadonlyMap<string, StepToolInfo>;

/**
 * Build ``thinkingStepId → StepToolInfo`` from message content. Used to
 *  - identify the opening ``task`` step (parent header, never indents) without
 *    relying on the human-readable title;
 *  - render the parent's display title from ``args.subagent_type`` instead of
 *    the generic "Task" copy;
 *  - mount the matching tool-call card inline under a step row when the
 *    result is an HITL interrupt (see ``TimelineHitlCard``).
 */
export function buildThinkingStepToolInfo(
	content: readonly unknown[] | undefined
): ThinkingStepToolInfoMap {
	const m = new Map<string, StepToolInfo>();
	if (!content) return m;
	for (const part of content) {
		if (!part || typeof part !== "object") continue;
		const o = part as {
			type?: string;
			toolCallId?: string;
			toolName?: string;
			args?: Record<string, unknown>;
			argsText?: string;
			result?: unknown;
			langchainToolCallId?: string;
			metadata?: Record<string, unknown>;
		};
		if (o.type !== "tool-call" || !o.toolName || !o.toolCallId) continue;
		const tid = o.metadata?.thinkingStepId;
		if (typeof tid === "string" && tid.trim().length > 0) {
			m.set(tid, {
				toolCallId: o.toolCallId,
				toolName: o.toolName,
				args: o.args ?? {},
				argsText: o.argsText,
				result: o.result,
				langchainToolCallId: o.langchainToolCallId,
			});
		}
	}
	return m;
}

function asNonEmptyString(v: unknown): string | undefined {
	return typeof v === "string" && v.trim().length > 0 ? v.trim() : undefined;
}

function titleCaseSubagent(raw: string): string {
	// "notion" → "Notion", "doc_research" → "Doc Research".
	return raw
		.split(/[\s_-]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

/**
 * Display title for a step. For the opening ``task`` step we substitute the
 * subagent type from the matching tool-call args (e.g. ``"Notion"`` instead of
 * the generic ``"Task"``). Falls back to the step's own title if the tool-call
 * hasn't streamed in yet.
 */
function resolveDisplayTitle(step: ThinkingStep, info: StepToolInfo | undefined): string {
	if (info?.toolName === "task") {
		const subagent = asNonEmptyString(info.args?.subagent_type);
		if (subagent) return titleCaseSubagent(subagent);
	}
	return step.title;
}

function isDelegatedChild(step: ThinkingStep, info: StepToolInfo | undefined): boolean {
	const sid = asNonEmptyString(step.metadata?.spanId);
	if (!sid) return false;
	// The opening ``task`` step also carries ``spanId`` (it owns the span) but
	// must render as the parent header. Prefer the joined ``toolName`` (set by
	// ``buildThinkingStepToolInfo`` from ``tool-call.metadata.thinkingStepId``).
	// Fall back to the title heuristic when no tool-call is matched — happens
	// for messages persisted before ``thinkingStepId`` shipped, and briefly
	// during streaming if the ``tool-input-start`` frame hasn't been processed
	// yet for some reason.
	if (info) return info.toolName !== "task";
	return step.title !== "Task";
}

interface StepGroup {
	parent: ThinkingStep;
	children: ThinkingStep[];
}

/**
 * Group consecutive delegated child steps under the preceding parent step.
 * If the very first step is a child (no parent yet seen), it's promoted to a
 * parent so it still renders — defensive only, real flows always start with a
 * parent step.
 */
const EMPTY_STEP_TOOL_INFO: ThinkingStepToolInfoMap = new Map();

function groupSteps(
	steps: readonly ThinkingStep[],
	stepToolInfo: ThinkingStepToolInfoMap
): StepGroup[] {
	const groups: StepGroup[] = [];
	for (const step of steps) {
		if (isDelegatedChild(step, stepToolInfo.get(step.id)) && groups.length > 0) {
			groups[groups.length - 1].children.push(step);
		} else {
			groups.push({ parent: step, children: [] });
		}
	}
	return groups;
}

const StepBody: FC<{
	step: ThinkingStep;
	status: "pending" | "in_progress" | "completed";
	displayTitle: string;
}> = ({ step, status, displayTitle }) => (
	<div className="min-w-0">
		<div
			className={cn(
				"text-sm leading-5",
				status === "in_progress" && "text-foreground font-medium",
				status === "completed" && "text-muted-foreground",
				status === "pending" && "text-muted-foreground/60"
			)}
		>
			{displayTitle}
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
);

/**
 * Mount the same tool-call UI used in the message body, but inside the
 * chain-of-thought timeline. The body copy returns ``null`` (see
 * ``withHitlInTimeline`` in ``lib/hitl/render-target``), so the card
 * effectively moves from the body to the timeline for the lifetime of the
 * interrupt (pending → processing → complete / rejected).
 *
 * ``metadata`` is intentionally omitted from the props we forward — the
 * step row already provides any indentation it needs, so we don't want
 * ``withDelegationSpanIndent`` to add a second indent + border on top.
 *
 * ``status`` is a placeholder (HITL UIs read only ``args`` + ``result``)
 * so we don't need to mirror assistant-ui's runtime status object here.
 */
const TimelineHitlCard: FC<{ info: StepToolInfo }> = ({ info }) => {
	const Comp =
		(TOOLS_BY_NAME as Record<string, ToolCallMessagePartComponent | undefined>)[info.toolName] ??
		TOOLS_FALLBACK;
	const props = {
		toolCallId: info.toolCallId,
		toolName: info.toolName,
		args: info.args,
		argsText: info.argsText,
		result: info.result,
		langchainToolCallId: info.langchainToolCallId,
		status: { type: "complete" } as const,
	};
	return (
		<HitlRenderTargetProvider value="timeline">
			{/* biome-ignore lint/suspicious/noExplicitAny: ToolCallMessagePartProps requires
			    runtime-only fields (addResult, resume, MessagePartState) we don't have when
			    re-rendering manually; HITL components only read args + result. */}
			<Comp {...(props as any)} />
		</HitlRenderTargetProvider>
	);
};

function hitlInterruptInfo(info: StepToolInfo | undefined): StepToolInfo | undefined {
	return info && isInterruptResult(info.result) ? info : undefined;
}

/**
 * Chain of thought display component - single collapsible dropdown design.
 *
 * ``stepToolInfo`` joins each step (by ``thinkingStepId``) to its ``tool-call``
 * part so we can:
 *  - replace the generic ``"Task"`` title with the real subagent name
 *    (``args.subagent_type``) on the parent header;
 *  - decide parent-vs-child purely from the matched ``toolName`` instead of
 *    relying on the displayed title.
 */
export const ThinkingStepsDisplay: FC<{
	steps: ThinkingStep[];
	isThreadRunning?: boolean;
	stepToolInfo?: ThinkingStepToolInfoMap;
}> = ({ steps, isThreadRunning = true, stepToolInfo }) => {
	const toolInfo = stepToolInfo ?? EMPTY_STEP_TOOL_INFO;
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
	const inProgressDisplayTitle = inProgressStep
		? resolveDisplayTitle(inProgressStep, toolInfo.get(inProgressStep.id))
		: undefined;
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

	const groups = useMemo(() => groupSteps(steps, toolInfo), [steps, toolInfo]);

	if (steps.length === 0) return null;

	const getHeaderText = () => {
		if (allCompleted) {
			return "Reviewed";
		}
		if (inProgressDisplayTitle) {
			return inProgressDisplayTitle;
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
					onClick={() => setIsOpen((prev) => !prev)}
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
							{groups.map((group, groupIndex) => {
								const isLastGroup = groupIndex === groups.length - 1;
								const parentStatus = getEffectiveStatus(group.parent);
								const parentInfo = toolInfo.get(group.parent.id);
								const parentTitle = resolveDisplayTitle(group.parent, parentInfo);
								const hasChildren = group.children.length > 0;
								// Parent dots are connected by a vertical line that runs through
								// any indented children (their column has no dot, so the line
								// passes cleanly behind them) and overshoots by ~15px to reach
								// the next group's dot center (top-[15px]).
								const showParentLine = !isLastGroup;

								return (
									<div key={group.parent.id} className="relative flex gap-3">
										<div className="relative flex flex-col items-center w-2 self-stretch">
											{showParentLine && (
												<div className="absolute left-1/2 top-[15px] -bottom-[15px] w-px -translate-x-1/2 bg-muted-foreground/30" />
											)}
											<div className="relative z-10 mt-[7px] flex shrink-0 items-center justify-center">
												{parentStatus === "in_progress" ? (
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
											<StepBody
												step={group.parent}
												status={parentStatus}
												displayTitle={parentTitle}
											/>

											{(() => {
												const hitl = hitlInterruptInfo(parentInfo);
												return hitl ? <TimelineHitlCard info={hitl} /> : null;
											})()}

											{hasChildren && (
												<div className="mt-2 ml-3 space-y-2">
													{group.children.map((child) => {
														const childInfo = toolInfo.get(child.id);
														const childHitl = hitlInterruptInfo(childInfo);
														return (
															<div key={child.id}>
																<StepBody
																	step={child}
																	status={getEffectiveStatus(child)}
																	displayTitle={resolveDisplayTitle(child, childInfo)}
																/>
																{childHitl && <TimelineHitlCard info={childHitl} />}
															</div>
														);
													})}
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
	const content = useAuiState(({ message }) => message?.content);

	const stepToolInfo = useMemo(
		() => buildThinkingStepToolInfo(Array.isArray(content) ? content : undefined),
		[content]
	);

	const steps = (data as { steps: ThinkingStep[] } | null)?.steps ?? [];
	if (steps.length === 0) return null;

	return (
		<div className="mb-3 -mx-2 leading-normal">
			<ThinkingStepsDisplay
				steps={steps}
				isThreadRunning={isMessageStreaming}
				stepToolInfo={stepToolInfo}
			/>
		</div>
	);
}

export const ThinkingStepsDataUI = makeAssistantDataUI({
	name: "thinking-steps",
	render: ThinkingStepsDataRenderer,
});

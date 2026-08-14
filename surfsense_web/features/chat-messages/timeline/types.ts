/**
 * Coarse status used by the timeline's chrome (the colored dot, the
 * "in progress" pulse). NOT consulted by per-tool components — those
 * own their own visual state machines (e.g. ``useHitlPhase`` for HITL
 * approval cards).
 *
 * - ``pending``    — known but not started yet (rare; usually only seen briefly during streaming)
 * - ``running``    — currently executing (assistant-ui ``in_progress``)
 * - ``completed``  — finished without error
 * - ``cancelled``  — user rejected (HITL ``__decided__: "reject"``)
 * - ``error``      — threw or returned an error result
 */
export type ItemStatus =
	| "pending"
	| "running"
	| "awaiting_approval"
	| "completed"
	| "cancelled"
	| "interrupted"
	| "error";

export type ActivityCategory =
	| "reasoning"
	| "file"
	| "research"
	| "artifact"
	| "connector"
	| "action";
export type ActivityVisibility = "show" | "aggregate" | "hide";

export interface ActivityIntegration {
	source: "native" | "connector" | "mcp";
	key?: string;
	name?: string;
}

export interface ActivityContext {
	subagentType?: string;
	intent?: "inspect" | "author" | "verify" | "persist" | "discover_skill";
	artifactType?: string;
	skillName?: string;
}

export interface SafeActivityDetail {
	subject?: string;
	count?: number;
	domain?: string;
	filename?: string;
}

interface BaseItem {
	/**
	 * Stable React key for the timeline. When a thinking-step row is joined
	 * with a tool-call part (via ``metadata.thinkingStepId``), this is the
	 * thinking-step ID — preserves identity across rehydration. For
	 * tool-calls with no joined step, this is the ``toolCallId``.
	 */
	id: string;
	status: ItemStatus;
	sequence?: number;
	startedAt?: string;
	completedAt?: string;
	activeTitle?: string;
	completedTitle?: string;
	integration?: ActivityIntegration;
	context?: ActivityContext;
	safeDetail?: SafeActivityDetail;
	/**
	 * Optional sub-bullets shown beneath the row's title. Forwarded
	 * verbatim from ``ThinkingStep.items`` when the timeline item was
	 * built from a thinking-step row.
	 */
	items?: string[];
	/**
	 * Groups items into the delegation tree. All items emitted while a
	 * delegating ``task`` is open carry the same ``spanId``; the ``task``
	 * step itself owns the span (see ``grouping.ts``).
	 */
	spanId?: string;
}

/**
 * Pure agent narration (e.g. "Reviewing the request", "Planning"). NOT
 * a model-level ``<think>`` block — those are rendered in the BODY by
 * the assistant-ui ``Reasoning`` component. This kind covers thinking-
 * step rows that are NOT linked to a tool call.
 */
export interface ReasoningItem extends BaseItem {
	kind: "reasoning";
	title: string;
}

/**
 * A tool invocation. Per-tool components (mounted by the timeline's
 * tool-registry) discriminate the ``result`` shape internally to pick
 * a view (interrupt → approval card; success → result card; etc.).
 *
 * The timeline does NOT inspect ``result`` beyond deriving ``status``.
 */
export interface ToolCallItem extends BaseItem {
	kind: "tool-call";
	toolName: string;
	/** The actual tool-call ID — passed to per-tool components (e.g. for the Revert button). */
	toolCallId: string;
	args: Record<string, unknown>;
	argsText?: string;
	result?: unknown;
	langchainToolCallId?: string;
	/**
	 * Set when the tool-call was joined with a thinking-step row via
	 * ``metadata.thinkingStepId``. In that case ``id`` is the
	 * thinking-step ID, not the ``toolCallId``.
	 */
	thinkingStepId?: string;
}

export type TimelineItem = ReasoningItem | ToolCallItem;

/**
 * The output shape of the grouping pass. Each group is a parent item
 * (typically a delegating ``task`` tool-call) plus the items emitted
 * inside its span. Items with no ``spanId`` become parents with no
 * children.
 */
export interface TimelineGroup {
	parent: TimelineItem;
	children: TimelineItem[];
}

export interface VisibleReasoningBlock {
	id: string;
	text: string;
	status: "running" | "completed" | "interrupted";
	startedAt?: string;
	completedAt?: string;
}

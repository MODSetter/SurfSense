import {
	type ToolCallMessagePartComponent,
	useAuiState,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { CheckIcon, ChevronDownIcon, RotateCcw, XCircleIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import {
	DoomLoopApprovalToolUI,
	isDoomLoopInterrupt,
} from "@/components/tool-ui/doom-loop-approval";
import { GenericHitlApprovalToolUI } from "@/components/tool-ui/generic-hitl-approval";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import {
	markActionRevertedInCache,
	useAgentActionsQuery,
} from "@/hooks/use-agent-actions-query";
import { agentActionsApiService } from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { isInterruptResult } from "@/lib/hitl";
import { cn } from "@/lib/utils";

/**
 * Inline Revert button rendered on a tool card when the matching
 * ``AgentActionLog`` row is reversible and hasn't been reverted yet.
 *
 * Reads from the unified ``useAgentActionsQuery`` cache — the SAME
 * react-query cache the agent-actions sheet consumes. SSE events
 * (``data-action-log`` / ``data-action-log-updated``) and
 * ``POST /threads/{id}/revert/{id}`` responses both flow through the
 * cache via ``setQueryData`` helpers, so the card and the sheet stay
 * in lockstep on every code path: page reload, navigation, live
 * stream, post-stream reversibility flip, and explicit revert clicks.
 *
 * Match key (in priority order):
 * 1. ``a.tool_call_id === toolCallId`` — direct hit in parity_v2 when
 *    the model streamed ``tool_call_chunks`` so the card's synthetic
 *    id IS the LangChain id.
 * 2. ``a.tool_call_id === langchainToolCallId`` — legacy mode (or
 *    parity_v2 with provider-side chunk emission) where the card's
 *    synthetic id is ``call_<run_id>`` and the LangChain id is
 *    backfilled onto the part by ``tool-output-available``.
 * 3. ``(chat_turn_id, tool_name, position-within-turn)`` — fallback
 *    for cards whose synthetic id is ``call_<run_id>`` AND whose
 *    ``langchainToolCallId`` never got backfilled (provider emitted
 *    the tool_call as a single payload with no chunks AND streaming
 *    pre-dated the ``tool-output-available langchainToolCallId``
 *    backfill, e.g. older threads). Reads the parent message's
 *    ``chatTurnId`` and ``content`` via ``useAuiState`` so we can
 *    match position-by-tool-name within the turn against the
 *    action_log rows the server returned in ``created_at`` order.
 */
function ToolCardRevertButton({
	toolCallId,
	toolName,
	langchainToolCallId,
}: {
	toolCallId: string;
	toolName: string;
	langchainToolCallId?: string;
}) {
	const session = useAtomValue(chatSessionStateAtom);
	const threadId = session?.threadId ?? null;
	const queryClient = useQueryClient();
	const { findByToolCallId, findByChatTurnAndTool } = useAgentActionsQuery(threadId);

	// Parent message metadata, read via the narrowest possible
	// selectors so this card doesn't re-render on every text-delta of
	// every other part in the same message during streaming.
	//
	// IMPORTANT — ``useAuiState`` re-renders the component whenever the
	// returned slice's identity changes. Returning ``message?.content``
	// (an array) would re-render on every token because the runtime
	// rebuilds the parts array. Returning a PRIMITIVE (the position
	// number) lets ``useAuiState``'s ``Object.is`` check short-circuit
	// when the position hasn't actually moved — which is the common
	// case during text streaming, when only ``text``/``reasoning``
	// parts are mutating and the same-toolName tool-call ordering is
	// stable. (See Vercel React rule ``rerender-defer-reads``.)
	const chatTurnId = useAuiState(({ message }) => {
		const meta = message?.metadata as { custom?: { chatTurnId?: string } } | undefined;
		return meta?.custom?.chatTurnId ?? null;
	});
	const positionInTurn = useAuiState(({ message }) => {
		const content = message?.content;
		if (!Array.isArray(content)) return -1;
		let n = -1;
		for (const part of content) {
			if (
				part &&
				typeof part === "object" &&
				(part as { type?: string }).type === "tool-call" &&
				(part as { toolName?: string }).toolName === toolName
			) {
				n += 1;
				if ((part as { toolCallId?: string }).toolCallId === toolCallId) return n;
			}
		}
		return -1;
	});

	const action = useMemo(() => {
		// Tier 1 + 2: O(1) Map-backed direct id match. Covers
		// ~all parity_v2 streams and any legacy stream that backfilled
		// ``langchainToolCallId`` via ``tool-output-available``.
		const direct =
			findByToolCallId(toolCallId) ?? findByToolCallId(langchainToolCallId);
		if (direct) return direct;
		// Tier 3: position-within-turn fallback. Only kicks in when the
		// card has a synthetic ``call_<run_id>`` id AND no
		// ``langchainToolCallId`` was ever backfilled — i.e. the tool
		// was emitted as a single non-chunked payload AND streaming
		// pre-dated the on_tool_end backfill.
		if (!chatTurnId || positionInTurn < 0) return null;
		const turnSameTool = findByChatTurnAndTool(chatTurnId, toolName);
		return turnSameTool[positionInTurn] ?? null;
	}, [
		findByToolCallId,
		findByChatTurnAndTool,
		toolCallId,
		langchainToolCallId,
		chatTurnId,
		toolName,
		positionInTurn,
	]);

	const [isReverting, setIsReverting] = useState(false);
	const [confirmOpen, setConfirmOpen] = useState(false);

	if (!action) return null;
	if (!action.reversible) return null;
	if (action.reverted_by_action_id !== null && action.reverted_by_action_id !== undefined)
		return null;
	if (action.is_revert_action) return null;
	if (action.error !== null && action.error !== undefined) return null;
	if (!threadId) return null;

	const handleRevert = async () => {
		setIsReverting(true);
		try {
			const response = await agentActionsApiService.revert(threadId, action.id);
			markActionRevertedInCache(
				queryClient,
				threadId,
				action.id,
				response.new_action_id ?? null
			);
			toast.success(response.message || "Action reverted.");
		} catch (err) {
			// 503 means revert is gated off on this deployment — hide the
			// button silently rather than nagging the user. Any other error
			// is surfaced as a toast so the operator can investigate.
			if (err instanceof AppError && err.status === 503) {
				return;
			}
			const message =
				err instanceof AppError
					? err.message
					: err instanceof Error
						? err.message
						: "Failed to revert action.";
			toast.error(message);
		} finally {
			setIsReverting(false);
			setConfirmOpen(false);
		}
	};

	return (
		<AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
			<AlertDialogTrigger asChild>
				<Button
					size="sm"
					variant="outline"
					className="gap-1.5"
					onClick={(e) => {
						e.stopPropagation();
						setConfirmOpen(true);
					}}
					disabled={isReverting}
				>
					{isReverting ? (
						// Spinner's typed props don't accept ``data-icon`` and
						// it renders an <output>, not an <svg>, so Button's
						// auto-sizing rule doesn't apply. Bare spinner +
						// Button's gap handle layout.
						<Spinner size="xs" />
					) : (
						<RotateCcw data-icon="inline-start" />
					)}
					Revert
				</Button>
			</AlertDialogTrigger>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Revert this action?</AlertDialogTitle>
					<AlertDialogDescription>
						This will undo{" "}
						<span className="font-medium">{getToolDisplayName(action.tool_name)}</span> and add a
						new entry to the history. Your chat is preserved — only the changes the agent made to
						your knowledge base or connected apps will be rolled back where possible.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<AlertDialogFooter>
					<AlertDialogCancel disabled={isReverting}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={(e) => {
							e.preventDefault();
							handleRevert();
						}}
						disabled={isReverting}
						className="gap-1.5"
					>
						{isReverting && <Spinner size="xs" />}
						Revert
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}

/**
 * Compact tool-call card.
 *
 * shadcn composition note: we intentionally use ``Card`` as a visual
 * frame WITHOUT ``CardHeader / CardContent``. The full composition's
 * ``p-6`` padding doesn't fit a compact collapsible header that IS the
 * trigger; using ``Card`` alone preserves the rounded border, shadow,
 * and ``bg-card`` token (semantic colors) without forcing a layout
 * that doesn't fit. All status colors use semantic tokens — no manual
 * dark-mode overrides, no raw hex.
 */
const DefaultToolFallbackInner: ToolCallMessagePartComponent = (props) => {
	const { toolCallId, toolName, argsText, result, status } = props;
	// ``langchainToolCallId`` is a SurfSense-specific extension the
	// streaming pipeline attaches to the tool-call content part so
	// the Revert button can resolve its ``AgentActionLog`` row even
	// when only the LC id is known. assistant-ui's
	// ``ToolCallMessagePartProps`` doesn't list it, but the runtime
	// spreads ``{...part}`` so the prop reaches us at runtime.
	const langchainToolCallId = (props as { langchainToolCallId?: string }).langchainToolCallId;

	const isCancelled = status?.type === "incomplete" && status.reason === "cancelled";
	const isError = status?.type === "incomplete" && status.reason === "error";
	const isRunning = status?.type === "running" || status?.type === "requires-action";

	/*
		Per-card expansion state. Initial value is ``isRunning`` so a
		card streaming in mounts already-expanded (no flash of
		collapsed → expanded on first paint), while a card loaded from
		history (status="complete") mounts collapsed. The useEffect
		below keeps this in lockstep with this card's own ``isRunning``
		when it transitions: false → true auto-expands (e.g. a tool
		that re-runs after edit), true → false auto-collapses once the
		tool finishes. Because the dep is per-card ``isRunning`` and
		not the chat-level streaming flag, sibling cards on the same
		assistant turn each manage their own expansion independently.
		Once ``isRunning`` is false the user controls expansion via
		``onOpenChange``.
	*/
	const [isExpanded, setIsExpanded] = useState(isRunning);
	useEffect(() => {
		setIsExpanded(isRunning);
	}, [isRunning]);
	const errorData = status?.type === "incomplete" ? status.error : undefined;
	const serializedError = useMemo(
		() => (errorData && typeof errorData !== "string" ? JSON.stringify(errorData) : null),
		[errorData]
	);

	const serializedResult = useMemo(
		() =>
			result !== undefined && typeof result !== "string" ? JSON.stringify(result, null, 2) : null,
		[result]
	);

	const cancelledReason =
		isCancelled && status.error
			? typeof status.error === "string"
				? status.error
				: serializedError
			: null;
	const errorReason =
		isError && status.error
			? typeof status.error === "string"
				? status.error
				: serializedError
			: null;

	const displayName = getToolDisplayName(toolName);
	const subtitle = errorReason ?? cancelledReason;

	return (
		<Card
			className={cn(
				"my-4 max-w-lg overflow-hidden",
				isCancelled && "opacity-60",
				isError && "border-destructive/30"
			)}
		>
			{/*
				``group`` lets the chevron (rendered as a sibling of the
				main trigger button) read the Collapsible Root's
				``data-[state=open]`` for rotation. The Collapsible is
				fully controlled via ``isExpanded`` — the useEffect
				above syncs it to ``isRunning`` so the card auto-opens
				while a tool streams in and auto-collapses once it
				finishes. We deliberately DON'T pass ``disabled`` so
				both triggers stay clickable; ``onOpenChange`` is wired
				to a setter that no-ops while ``isRunning`` (see
				``handleOpenChange`` below) which keeps the card pinned
				open mid-stream without losing keyboard / pointer
				affordance the moment streaming ends.
			*/}
			<Collapsible
				className="group"
				open={isExpanded}
				onOpenChange={(next) => {
					// Block manual collapse while the tool is still
					// streaming — otherwise a stray click on either
					// trigger would close the card and hide the live
					// ``argsText`` panel mid-run. After streaming the
					// user has full control again.
					if (isRunning) return;
					setIsExpanded(next);
				}}
			>
				{/*
					Header row: main trigger on the left (icon + title
					col), Revert + chevron-trigger on the right as
					siblings of the main trigger. The chevron is wrapped
					in its OWN ``CollapsibleTrigger`` (Radix supports
					multiple triggers per Root) so clicking the chevron
					toggles the same state as clicking the title row.
					The Revert button stays a separate AlertDialog
					trigger and stops propagation in its onClick so it
					doesn't toggle the collapsible while opening the
					confirm dialog. Keeping these as flat siblings —
					rather than nesting Revert / chevron inside the
					title trigger — avoids invalid HTML
					(button-in-button) and lets the Revert button
					render in BOTH the collapsed and expanded states.
				*/}
				<div className="flex items-stretch transition-colors hover:bg-muted/50">
					<CollapsibleTrigger asChild>
						<button
							type="button"
							className={cn(
								"flex flex-1 min-w-0 items-center gap-3 py-4 pl-5 pr-2 text-left",
								// Inset ring — Card's ``overflow-hidden`` would
								// clip an ``offset-2`` ring; ``ring-inset``
								// paints inside the button box.
								"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
								"disabled:cursor-default"
							)}
						>
							<div
								className={cn(
									"flex size-8 shrink-0 items-center justify-center rounded-lg",
									isError ? "bg-destructive/10" : isCancelled ? "bg-muted" : "bg-primary/10"
								)}
							>
								{isError ? (
									<XCircleIcon className="size-4 text-destructive" />
								) : isCancelled ? (
									<XCircleIcon className="size-4 text-muted-foreground" />
								) : isRunning ? (
									<Spinner size="sm" className="text-primary" />
								) : (
									<CheckIcon className="size-4 text-primary" />
								)}
							</div>

							<div className="flex flex-1 min-w-0 flex-col gap-0.5">
								<div className="flex items-center gap-2">
									<p
										className={cn(
											"text-sm font-semibold truncate",
											isCancelled && "text-muted-foreground line-through",
											isError && "text-destructive"
										)}
									>
										{displayName}
									</p>
									{isRunning && <Badge variant="secondary">Running</Badge>}
									{isError && <Badge variant="destructive">Failed</Badge>}
									{isCancelled && <Badge variant="outline">Cancelled</Badge>}
								</div>
								{subtitle && (
									<p
										className={cn(
											"text-xs truncate",
											isError ? "text-destructive/80" : "text-muted-foreground"
										)}
									>
										{subtitle}
									</p>
								)}
							</div>
						</button>
					</CollapsibleTrigger>

					{/*
						Right-side controls. The Revert button is
						visible whenever the matching action is
						reversible — including the collapsed state —
						but ``ToolCardRevertButton`` itself returns
						``null`` while a tool is still running because
						no action-log row exists yet, so it doesn't
						need an explicit ``isRunning`` gate here.
					*/}
					<div className="flex shrink-0 items-center gap-2 pl-2 pr-5">
						<ToolCardRevertButton
							toolCallId={toolCallId}
							toolName={toolName}
							langchainToolCallId={langchainToolCallId}
						/>
						<CollapsibleTrigger asChild>
							<button
								type="button"
								aria-label={isExpanded ? "Collapse details" : "Expand details"}
								className={cn(
									"flex size-7 shrink-0 items-center justify-center rounded-md",
									"text-muted-foreground hover:bg-muted hover:text-foreground",
									"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
									"disabled:cursor-default"
								)}
							>
								<ChevronDownIcon
									className={cn(
										"size-4 transition-transform duration-200",
										"group-data-[state=open]:rotate-180"
									)}
								/>
							</button>
						</CollapsibleTrigger>
					</div>
				</div>

				{/*
					CollapsibleContent body — auto-open while streaming
					(see ``open`` prop above) so the live ``argsText``
					streams into the Inputs panel directly, no need for
					a separate "Live input" panel. Native
					``overflow-auto`` instead of ``ScrollArea`` because
					Radix's Viewport can let content bleed past
					``max-h-*`` in dynamic flex layouts. ``min-w-0`` on
					the column wrappers guarantees ``break-all`` wraps
					correctly within the bounded ``max-w-lg`` Card.
				*/}
				<CollapsibleContent>
					<Separator />
					<div className="flex flex-col gap-3 px-5 py-3">
						{(argsText || isRunning) && (
							<div className="flex flex-col gap-1 min-w-0">
								<p className="text-xs font-medium text-muted-foreground">Inputs</p>
								<div className="max-h-48 overflow-auto rounded-md bg-muted/40">
									{argsText ? (
										<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
											{argsText}
										</pre>
									) : (
										// Bridges the brief gap between
										// ``tool-input-start`` (creates the
										// card, ``argsText`` undefined) and
										// the first ``tool-input-delta``.
										<p className="px-3 py-2 text-xs italic text-muted-foreground">
											Waiting for input…
										</p>
									)}
								</div>
							</div>
						)}
						{!isCancelled && result !== undefined && (
							<>
								<Separator />
								<div className="flex flex-col gap-1 min-w-0">
									<p className="text-xs font-medium text-muted-foreground">Result</p>
									<div className="max-h-64 overflow-auto rounded-md bg-muted/40">
										<pre className="px-3 py-2 text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
											{typeof result === "string" ? result : serializedResult}
										</pre>
									</div>
								</div>
							</>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</Card>
	);
};

export const ToolFallback: ToolCallMessagePartComponent = (props) => {
	if (isInterruptResult(props.result)) {
		if (isDoomLoopInterrupt(props.result)) {
			return <DoomLoopApprovalToolUI {...props} />;
		}
		return <GenericHitlApprovalToolUI {...props} />;
	}
	return <DefaultToolFallbackInner {...props} />;
};

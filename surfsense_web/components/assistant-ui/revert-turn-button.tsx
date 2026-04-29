"use client";

/**
 * "Revert turn" button rendered at the bottom of every completed
 * assistant turn that has at least one reversible action.
 *
 * The button reads the action map keyed by ``chat_turn_id`` from the
 * SSE side-channel (``data-action-log`` events). It shows a confirmation
 * dialog summarising "N reversible / M total" and, on confirm, calls
 * ``POST /threads/{id}/revert-turn/{chat_turn_id}``.
 *
 * The route returns a per-action result list and never collapses the
 * batch into a 4xx — so we render any failed/not_reversible rows inline
 * with their messages.
 */

import { useAtomValue, useSetAtom } from "jotai";
import { selectAtom } from "jotai/utils";
import { CheckIcon, RotateCcw, XCircleIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
	type AgentActionLite,
	agentActionsByChatTurnIdAtom,
	markAgentActionsRevertedBatchAtom,
} from "@/atoms/chat/agent-actions.atom";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
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
import { Button } from "@/components/ui/button";
import {
	agentActionsApiService,
	type RevertTurnActionResult,
} from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { cn } from "@/lib/utils";

interface RevertTurnButtonProps {
	chatTurnId: string | null | undefined;
}

function formatToolName(name: string): string {
	return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Empty-array sentinel so the per-turn ``selectAtom`` slice returns a
// stable reference when the turn has no recorded actions yet. Without
// this every render allocates a fresh ``[]`` and Jotai's
// equality check would re-render the button on unrelated turn updates.
const EMPTY_ACTIONS: readonly AgentActionLite[] = Object.freeze([]);

export function RevertTurnButton({ chatTurnId }: RevertTurnButtonProps) {
	const session = useAtomValue(chatSessionStateAtom);
	const markRevertedBatch = useSetAtom(markAgentActionsRevertedBatchAtom);
	const [isReverting, setIsReverting] = useState(false);
	const [confirmOpen, setConfirmOpen] = useState(false);
	const [resultsOpen, setResultsOpen] = useState(false);
	const [results, setResults] = useState<RevertTurnActionResult[]>([]);

	// Subscribe ONLY to the slice of the global action map that belongs
	// to ``chatTurnId``. Previously the button read the whole
	// ``agentActionsByChatTurnIdAtom``, which meant every action
	// upsert (one per tool call) re-rendered every Revert button on
	// the page. With ``selectAtom`` we re-render only when our turn's
	// list reference changes — and the upsert/mark atoms produce a
	// fresh list reference for the affected turn only.
	const sliceAtom = useMemo(
		() =>
			selectAtom(
				agentActionsByChatTurnIdAtom,
				(turnIndex) => (chatTurnId ? turnIndex.get(chatTurnId) : undefined) ?? EMPTY_ACTIONS
			),
		[chatTurnId]
	);
	const actions = useAtomValue(sliceAtom);

	const reversibleCount = useMemo(
		() =>
			actions.filter(
				(a) => a.reversible && a.revertedByActionId === null && !a.isRevertAction && !a.error
			).length,
		[actions]
	);
	const totalCount = useMemo(() => actions.filter((a) => !a.isRevertAction).length, [actions]);

	if (!chatTurnId) return null;
	if (reversibleCount === 0) return null;
	const threadId = session?.threadId;
	if (!threadId) return null;

	const handleRevertTurn = async () => {
		setIsReverting(true);
		try {
			const response = await agentActionsApiService.revertTurn(threadId, chatTurnId);
			setResults(response.results);
			const revertedEntries = response.results
				.filter((r) => r.status === "reverted" || r.status === "already_reverted")
				.map((r) => ({ id: r.action_id, newActionId: r.new_action_id ?? null }));
			if (revertedEntries.length > 0) {
				markRevertedBatch({ entries: revertedEntries });
			}
			if (response.status === "ok") {
				toast.success(
					response.reverted === 1 ? "Reverted 1 action." : `Reverted ${response.reverted} actions.`
				);
			} else {
				// Every "not undone" bucket counts as a failure for the
				// user-facing summary. ``skipped`` rows are batch
				// artefacts (revert rows themselves) and intentionally
				// excluded from the failure tally.
				const failureCount =
					response.failed + response.not_reversible + (response.permission_denied ?? 0);
				toast.warning(
					`Reverted ${response.reverted} of ${response.total}. ${failureCount} could not be undone.`
				);
				setResultsOpen(true);
			}
		} catch (err) {
			if (err instanceof AppError && err.status === 503) {
				return;
			}
			const message =
				err instanceof AppError
					? err.message
					: err instanceof Error
						? err.message
						: "Failed to revert turn.";
			toast.error(message);
		} finally {
			setIsReverting(false);
			setConfirmOpen(false);
		}
	};

	return (
		<>
			<AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
				<AlertDialogTrigger asChild>
					<Button
						size="sm"
						variant="ghost"
						className="text-muted-foreground hover:text-foreground gap-1.5"
						onClick={(e) => {
							e.stopPropagation();
							setConfirmOpen(true);
						}}
					>
						<RotateCcw className="size-3.5" />
						<span>Revert turn</span>
						<span className="text-xs tabular-nums opacity-70">
							{reversibleCount}/{totalCount}
						</span>
					</Button>
				</AlertDialogTrigger>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Revert this turn?</AlertDialogTitle>
						<AlertDialogDescription>
							This will undo {reversibleCount} of {totalCount} action
							{totalCount === 1 ? "" : "s"} from this turn in reverse order. The chat history and
							any read-only actions are preserved. Some rows may not be reversible — partial success
							is normal.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isReverting}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleRevertTurn();
							}}
							disabled={isReverting}
						>
							{isReverting ? "Reverting…" : "Revert turn"}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>

			<AlertDialog open={resultsOpen} onOpenChange={setResultsOpen}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Revert results</AlertDialogTitle>
						<AlertDialogDescription>
							Some actions could not be reverted. Review per-row outcomes below.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<ul className="max-h-72 overflow-y-auto space-y-2 text-sm">
						{results.map((r) => (
							<RevertResultRow key={r.action_id} result={r} />
						))}
					</ul>
					<AlertDialogFooter>
						<AlertDialogAction onClick={() => setResultsOpen(false)}>Close</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</>
	);
}

function RevertResultRow({ result }: { result: RevertTurnActionResult }) {
	const isOk = result.status === "reverted" || result.status === "already_reverted";
	const Icon = isOk ? CheckIcon : XCircleIcon;
	return (
		<li className="flex items-start gap-2 rounded-md border bg-muted/30 px-3 py-2">
			<Icon
				className={cn("size-4 mt-0.5 shrink-0", isOk ? "text-emerald-500" : "text-destructive")}
			/>
			<div className="min-w-0 flex-1">
				<p className="font-medium truncate">
					{formatToolName(result.tool_name)}{" "}
					<span className="ml-1 text-xs text-muted-foreground">
						{result.status.replace(/_/g, " ")}
					</span>
				</p>
				{(result.message || result.error) && (
					<p className="text-xs text-muted-foreground mt-0.5">{result.error ?? result.message}</p>
				)}
			</div>
		</li>
	);
}

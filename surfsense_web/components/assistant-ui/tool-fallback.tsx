import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, RotateCcw, XCircleIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
	agentActionByToolCallIdAtom,
	markAgentActionRevertedAtom,
} from "@/atoms/chat/agent-actions.atom";
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
import { Button } from "@/components/ui/button";
import { getToolDisplayName, getToolIcon } from "@/contracts/enums/toolIcons";
import { agentActionsApiService } from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { isInterruptResult } from "@/lib/hitl";
import { cn } from "@/lib/utils";

/**
 * Inline Revert button rendered on a tool card when the matching
 * ``AgentActionLog`` row is reversible and hasn't been reverted yet.
 * Reads from the SSE side-channel atom keyed by the synthetic
 * ``toolCallId`` so it lights up even when ``GET /threads/.../actions``
 * is gated behind ``SURFSENSE_ENABLE_ACTION_LOG=False`` (503).
 */
function ToolCardRevertButton({ toolCallId }: { toolCallId: string }) {
	const session = useAtomValue(chatSessionStateAtom);
	const actionMap = useAtomValue(agentActionByToolCallIdAtom);
	const markReverted = useSetAtom(markAgentActionRevertedAtom);
	const action = actionMap.get(toolCallId);
	const [isReverting, setIsReverting] = useState(false);
	const [confirmOpen, setConfirmOpen] = useState(false);

	if (!action) return null;
	if (!action.reversible) return null;
	if (action.revertedByActionId !== null) return null;
	if (action.isRevertAction) return null;
	if (action.error) return null;
	const threadId = session?.threadId;
	if (!threadId) return null;

	const handleRevert = async () => {
		setIsReverting(true);
		try {
			const response = await agentActionsApiService.revert(threadId, action.id);
			markReverted({ id: action.id, newActionId: response.new_action_id ?? null });
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
				>
					<RotateCcw className="size-3.5" />
					Revert
				</Button>
			</AlertDialogTrigger>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Revert this action?</AlertDialogTitle>
					<AlertDialogDescription>
						This will undo{" "}
						<span className="font-medium">{getToolDisplayName(action.toolName)}</span> and add a
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
					>
						{isReverting ? "Reverting…" : "Revert"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}

const DefaultToolFallbackInner: ToolCallMessagePartComponent = ({
	toolCallId,
	toolName,
	argsText,
	result,
	status,
}) => {
	const [isExpanded, setIsExpanded] = useState(false);

	const isCancelled = status?.type === "incomplete" && status.reason === "cancelled";
	const isError = status?.type === "incomplete" && status.reason === "error";
	const isRunning = status?.type === "running" || status?.type === "requires-action";
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

	const Icon = getToolIcon(toolName);
	const displayName = getToolDisplayName(toolName);

	return (
		<div
			className={cn(
				"my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none",
				isCancelled && "opacity-60",
				isError && "border-destructive/20 bg-destructive/5"
			)}
		>
			<button
				type="button"
				onClick={() => setIsExpanded((prev) => !prev)}
				className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none"
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
						<Icon className="size-4 text-primary animate-pulse" />
					) : (
						<CheckIcon className="size-4 text-primary" />
					)}
				</div>

				<div className="flex-1 min-w-0">
					<p
						className={cn(
							"text-sm font-semibold",
							isError
								? "text-destructive"
								: isCancelled
									? "text-muted-foreground line-through"
									: "text-foreground"
						)}
					>
						{isRunning
							? displayName
							: isCancelled
								? `Cancelled: ${displayName}`
								: isError
									? `Failed: ${displayName}`
									: displayName}
					</p>
					{isRunning && <p className="text-xs text-muted-foreground mt-0.5">Working…</p>}
					{cancelledReason && (
						<p className="text-xs text-muted-foreground mt-0.5 truncate">{cancelledReason}</p>
					)}
					{errorReason && (
						<p className="text-xs text-destructive/80 mt-0.5 truncate">{errorReason}</p>
					)}
				</div>

				{!isRunning && (
					<div className="shrink-0 text-muted-foreground">
						{isExpanded ? (
							<ChevronDownIcon className="size-4" />
						) : (
							<ChevronUpIcon className="size-4" />
						)}
					</div>
				)}
			</button>

			{isExpanded && !isRunning && (
				<>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-3 space-y-3">
						{argsText && (
							<div>
								<p className="text-xs font-medium text-muted-foreground mb-1">Inputs</p>
								<pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all">
									{argsText}
								</pre>
							</div>
						)}
						{!isCancelled && result !== undefined && (
							<>
								<div className="h-px bg-border/30" />
								<div>
									<p className="text-xs font-medium text-muted-foreground mb-1">Result</p>
									<pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all">
										{typeof result === "string" ? result : serializedResult}
									</pre>
								</div>
							</>
						)}
						<div className="flex justify-end">
							<ToolCardRevertButton toolCallId={toolCallId} />
						</div>
					</div>
				</>
			)}
		</div>
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

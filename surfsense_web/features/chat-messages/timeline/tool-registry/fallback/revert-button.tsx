"use client";

import { useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
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
import { Spinner } from "@/components/ui/spinner";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { markActionRevertedInCache } from "@/hooks/use-agent-actions-query";
import { agentActionsApiService } from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { useToolAction } from "./use-tool-action";

/**
 * Inline Revert button rendered on a default-fallback tool card when
 * the matching ``AgentActionLog`` row is reversible and hasn't been
 * reverted yet.
 *
 * Renders ``null`` (silent) in any of these cases:
 *  - no matching action row (still streaming, or never logged)
 *  - action not reversible
 *  - already reverted (``reverted_by_action_id`` set)
 *  - this card IS itself a revert action
 *  - tool errored
 *  - no thread context
 *
 * 503 from the revert API means the deployment has revert gated off;
 * we hide the failure silently rather than nag the user. Other errors
 * surface as toasts.
 */
export function ToolCardRevertButton({
	toolCallId,
	toolName,
	langchainToolCallId,
}: {
	toolCallId: string;
	toolName: string;
	langchainToolCallId?: string;
}) {
	const queryClient = useQueryClient();
	const { threadId, action } = useToolAction({
		toolCallId,
		toolName,
		langchainToolCallId,
	});

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
			markActionRevertedInCache(queryClient, threadId, action.id, response.new_action_id ?? null);
			toast.success(response.message || "Action reverted.");
		} catch (err) {
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
					{isReverting ? <Spinner size="xs" /> : <RotateCcw data-icon="inline-start" />}
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

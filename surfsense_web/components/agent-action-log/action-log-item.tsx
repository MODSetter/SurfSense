"use client";

import { ChevronRight, RotateCcw, ShieldOff, Undo2 } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { getToolDisplayName, getToolIcon } from "@/contracts/enums/toolIcons";
import { type AgentAction, agentActionsApiService } from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";

interface ActionLogItemProps {
	action: AgentAction;
	threadId: number;
	onRevertSuccess: () => void;
}

export function ActionLogItem({ action, threadId, onRevertSuccess }: ActionLogItemProps) {
	const [isExpanded, setIsExpanded] = useState(false);
	const [isReverting, setIsReverting] = useState(false);
	const [confirmOpen, setConfirmOpen] = useState(false);

	const isAlreadyReverted = action.reverted_by_action_id !== null;
	const isRevertAction = action.is_revert_action;
	const hasError = action.error !== null && action.error !== undefined;

	const Icon = getToolIcon(action.tool_name);
	const displayName = getToolDisplayName(action.tool_name);

	const argsPreview = action.args ? JSON.stringify(action.args, null, 2) : null;
	const truncatedArgs =
		argsPreview && argsPreview.length > 600 ? `${argsPreview.slice(0, 600)}…` : argsPreview;

	const canRevert = action.reversible && !isAlreadyReverted && !isRevertAction && !hasError;

	const handleRevert = async () => {
		setIsReverting(true);
		try {
			const response = await agentActionsApiService.revert(threadId, action.id);
			toast.success(response.message || "Action reverted successfully.");
			onRevertSuccess();
		} catch (err) {
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
		<div
			className={cn(
				"rounded-lg border bg-card transition-colors",
				isAlreadyReverted && "opacity-70"
			)}
		>
			<button
				type="button"
				onClick={() => setIsExpanded((v) => !v)}
				className="flex w-full items-start gap-3 p-3 text-left hover:bg-muted/40"
				aria-expanded={isExpanded}
			>
				<div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
					{isRevertAction ? (
						<Undo2 className="size-4 text-muted-foreground" />
					) : (
						<Icon className="size-4 text-muted-foreground" />
					)}
				</div>
				<div className="flex min-w-0 flex-1 flex-col gap-1">
					<div className="flex flex-wrap items-center gap-1.5">
						<span className="truncate text-sm font-medium">{displayName}</span>
						{isRevertAction && (
							<Badge variant="secondary" className="text-[10px]">
								Revert
							</Badge>
						)}
						{hasError && (
							<Badge variant="destructive" className="text-[10px]">
								Error
							</Badge>
						)}
						{!isRevertAction && action.reversible && !isAlreadyReverted && (
							<Badge variant="outline" className="text-[10px]">
								Reversible
							</Badge>
						)}
						{isAlreadyReverted && (
							<Badge variant="secondary" className="text-[10px]">
								Reverted
							</Badge>
						)}
					</div>
					<p className="text-xs text-muted-foreground">{formatRelativeDate(action.created_at)}</p>
				</div>
				<ChevronRight
					className={cn(
						"size-4 shrink-0 text-muted-foreground transition-transform",
						isExpanded && "rotate-90"
					)}
				/>
			</button>

			{isExpanded && (
				<div className="flex flex-col gap-3 border-t bg-muted/20 p-3">
					{truncatedArgs && (
						<div>
							<p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								Arguments
							</p>
							<pre className="max-h-48 overflow-auto rounded-md bg-background p-2 text-[11px] text-foreground/80">
								{truncatedArgs}
							</pre>
						</div>
					)}
					{action.error && (
						<div>
							<p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								Error
							</p>
							<pre className="max-h-32 overflow-auto rounded-md bg-destructive/10 p-2 text-[11px] text-destructive">
								{JSON.stringify(action.error, null, 2)}
							</pre>
						</div>
					)}
					{action.reverse_descriptor && (
						<div>
							<p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								Reverse plan
							</p>
							<pre className="max-h-32 overflow-auto rounded-md bg-background p-2 text-[11px] text-foreground/80">
								{JSON.stringify(action.reverse_descriptor, null, 2)}
							</pre>
						</div>
					)}

					<Separator />

					<div className="flex items-center justify-between">
						<p className="text-[10px] text-muted-foreground">
							Action ID: <span className="font-mono">{action.id}</span>
						</p>
						{canRevert ? (
							<AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
								<AlertDialogTrigger asChild>
									<Button size="sm" variant="outline" className="gap-1.5">
										<RotateCcw className="size-3.5" />
										Revert
									</Button>
								</AlertDialogTrigger>
								<AlertDialogContent>
									<AlertDialogHeader>
										<AlertDialogTitle>Revert this action?</AlertDialogTitle>
										<AlertDialogDescription>
											This will undo <span className="font-medium">{displayName}</span> and append a
											new audit entry. The agent's chat history is preserved — only the tool's
											effects on your knowledge base or connectors will be reversed where possible.
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
						) : (
							<div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
								<ShieldOff className="size-3.5" />
								{isAlreadyReverted
									? "Already reverted"
									: isRevertAction
										? "Revert entry"
										: hasError
											? "Cannot revert errored action"
											: "Not reversible"}
							</div>
						)}
					</div>
				</div>
			)}
		</div>
	);
}

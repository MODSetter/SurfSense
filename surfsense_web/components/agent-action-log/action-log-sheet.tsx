"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAtom, useAtomValue } from "jotai";
import { Activity, RefreshCcw } from "lucide-react";
import { useCallback } from "react";
import { actionLogSheetAtom } from "@/atoms/agent/action-log-sheet.atom";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
	agentActionsQueryKey,
	useAgentActionsQuery,
} from "@/hooks/use-agent-actions-query";
import { ActionLogItem } from "./action-log-item";

function EmptyState() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
			<div className="flex size-12 items-center justify-center rounded-full bg-muted">
				<Activity className="size-5 text-muted-foreground" />
			</div>
			<div className="flex flex-col gap-1">
				<p className="text-sm font-medium">No actions logged yet</p>
				<p className="text-xs text-muted-foreground">
					Once the agent calls a tool in this thread, it will show up here. From the log you can
					inspect arguments and revert reversible actions.
				</p>
			</div>
		</div>
	);
}

function DisabledState() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
			<div className="flex size-12 items-center justify-center rounded-full bg-muted">
				<Activity className="size-5 text-muted-foreground" />
			</div>
			<div className="flex flex-col gap-1">
				<p className="text-sm font-medium">Action log is disabled</p>
				<p className="text-xs text-muted-foreground">
					This deployment hasn't enabled the agent action log. An admin can flip
					<code className="ml-1 rounded bg-muted px-1 text-[10px]">
						SURFSENSE_ENABLE_ACTION_LOG
					</code>
					.
				</p>
			</div>
		</div>
	);
}

const SKELETON_KEYS = ["s1", "s2", "s3", "s4"] as const;

function LoadingState() {
	return (
		<div className="flex flex-col gap-2 p-4">
			{SKELETON_KEYS.map((key) => (
				<Skeleton key={key} className="h-16 w-full rounded-lg" />
			))}
		</div>
	);
}

export function ActionLogSheet() {
	const [state, setState] = useAtom(actionLogSheetAtom);
	const queryClient = useQueryClient();

	const { data: flags } = useAtomValue(agentFlagsAtom);
	const actionLogEnabled = !!flags?.enable_action_log && !flags?.disable_new_agent_stack;
	const revertEnabled = !!flags?.enable_revert_route && !flags?.disable_new_agent_stack;

	const threadId = state.threadId;

	const { data, items, isLoading, isFetching, isError, error, refetch } = useAgentActionsQuery(
		threadId,
		{ enabled: state.open && actionLogEnabled }
	);

	const handleRevertSuccess = useCallback(() => {
		if (threadId !== null) {
			queryClient.invalidateQueries({ queryKey: agentActionsQueryKey(threadId) });
		}
	}, [queryClient, threadId]);

	return (
		<Sheet open={state.open} onOpenChange={(open) => setState((s) => ({ ...s, open }))}>
			<SheetContent
				side="right"
				className="flex h-full w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
			>
				<SheetHeader className="shrink-0 border-b px-4 py-4">
					<div className="flex items-center justify-between gap-2">
						<div className="flex items-center gap-2">
							<Activity className="size-4 text-muted-foreground" />
							<SheetTitle className="text-base font-semibold">Agent actions</SheetTitle>
							{data?.total !== undefined && data.total > 0 && (
								<Badge variant="secondary" className="text-[10px]">
									{data.total}
								</Badge>
							)}
						</div>
						<Button
							size="sm"
							variant="ghost"
							onClick={() => refetch()}
							disabled={isFetching || !actionLogEnabled}
							className="size-8 p-0"
							aria-label="Refresh action log"
						>
							<RefreshCcw className={isFetching ? "size-3.5 animate-spin" : "size-3.5"} />
						</Button>
					</div>
					<SheetDescription className="text-xs text-muted-foreground">
						Audit trail of every tool call the agent made in this thread.
						{revertEnabled
							? " Reversible actions can be undone in place."
							: " Reverts are read-only on this deployment."}
					</SheetDescription>
				</SheetHeader>

				<Separator />

				<div className="flex min-h-0 flex-1 flex-col overflow-y-auto scrollbar-thin">
					{!actionLogEnabled ? (
						<DisabledState />
					) : threadId === null ? (
						<EmptyState />
					) : isLoading ? (
						<LoadingState />
					) : isError ? (
						<div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
							<p className="text-sm font-medium text-destructive">Failed to load actions</p>
							<p className="text-xs text-muted-foreground">
								{error instanceof Error ? error.message : "Unknown error"}
							</p>
							<Button size="sm" variant="outline" onClick={() => refetch()}>
								Try again
							</Button>
						</div>
					) : items.length === 0 ? (
						<EmptyState />
					) : (
						<div className="flex flex-col gap-2 p-3">
							{items.map((action) => (
								<ActionLogItem
									key={action.id}
									action={action}
									threadId={threadId}
									onRevertSuccess={handleRevertSuccess}
								/>
							))}
							{data?.has_more && (
								<p className="py-2 text-center text-[11px] text-muted-foreground">
									Showing {items.length} of {data.total}. Older actions are paginated.
								</p>
							)}
						</div>
					)}
				</div>
			</SheetContent>
		</Sheet>
	);
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAtom, useAtomValue } from "jotai";
import { RefreshCcw, Workflow } from "lucide-react";
import { useCallback } from "react";
import { actionLogDialogAtom } from "@/atoms/agent/action-log-dialog.atom";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { agentActionsQueryKey, useAgentActionsQuery } from "@/hooks/use-agent-actions-query";
import { ActionLogItem } from "./action-log-item";

function EmptyState() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 pb-12 text-center">
			<div className="flex max-w-[260px] flex-col gap-1.5">
				<p className="text-sm font-semibold tracking-tight">No actions logged yet</p>
				<p className="text-xs leading-relaxed text-muted-foreground">
					A complete audit trail of every tool the agent uses in this thread will appear here
				</p>
			</div>
		</div>
	);
}

function DisabledState() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 pb-12 text-center">
			<div className="flex size-12 items-center justify-center rounded-full border border-popover-border bg-muted/40">
				<Workflow className="size-5 text-muted-foreground" strokeWidth={1.75} />
			</div>
			<div className="flex max-w-[280px] flex-col gap-1.5">
				<p className="text-sm font-semibold tracking-tight">Action log is disabled</p>
				<p className="text-xs leading-relaxed text-muted-foreground">
					This deployment hasn't enabled the agent action log. An admin can enable{" "}
					<code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px] text-foreground">
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

export function ActionLogDialog() {
	const [state, setState] = useAtom(actionLogDialogAtom);
	const queryClient = useQueryClient();

	const { data: flags } = useAtomValue(agentFlagsAtom);
	const actionLogEnabled = !!flags?.enable_action_log && !flags?.disable_new_agent_stack;

	const threadId = state.threadId;

	const { data, items, isLoading, isFetching, isError, error, refetch } = useAgentActionsQuery(
		threadId,
		{ enabled: state.open && actionLogEnabled }
	);

	const handleOpenChange = useCallback(
		(open: boolean) => {
			setState((current) => (open ? { ...current, open } : { open: false, threadId: null }));
		},
		[setState]
	);

	const handleRevertSuccess = useCallback(() => {
		if (threadId !== null) {
			queryClient.invalidateQueries({ queryKey: agentActionsQueryKey(threadId) });
		}
	}, [queryClient, threadId]);

	return (
		<Dialog open={state.open} onOpenChange={handleOpenChange}>
			<DialogContent className="select-none flex h-[90vh] max-h-[640px] w-[95vw] max-w-[900px] flex-col gap-0 overflow-hidden p-0 [--card:var(--popover)] md:h-[80vh]">
				<div className="shrink-0 px-6 pb-3 pt-6 pr-28">
					<div className="flex items-center gap-2">
						<DialogTitle className="text-lg font-semibold">Agent actions</DialogTitle>
						{data?.total !== undefined && data.total > 0 ? (
							<Badge variant="secondary" className="text-[10px]">
								{data.total}
							</Badge>
						) : null}
					</div>
					<DialogDescription className="sr-only">
						Audit trail of every tool call the agent made in this thread.
					</DialogDescription>
					<Separator className="mt-4" />
				</div>

				<Button
					size="sm"
					variant="ghost"
					onClick={() => refetch()}
					disabled={isFetching || !actionLogEnabled}
					className="absolute right-14 top-4 size-8 rounded-full p-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
					aria-label="Refresh action log"
				>
					<RefreshCcw className={isFetching ? "size-3.5 animate-spin" : "size-3.5"} />
				</Button>

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
						<div className="flex flex-col gap-2 px-4 pb-4">
							{items.map((action) => (
								<ActionLogItem
									key={action.id}
									action={action}
									threadId={threadId}
									onRevertSuccess={handleRevertSuccess}
								/>
							))}
							{data?.has_more ? (
								<p className="py-2 text-center text-[11px] text-muted-foreground">
									Showing {items.length} of {data.total}. Older actions are paginated.
								</p>
							) : null}
						</div>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}

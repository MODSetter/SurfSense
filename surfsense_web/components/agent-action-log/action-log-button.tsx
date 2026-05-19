"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Workflow } from "lucide-react";
import { useCallback } from "react";
import { openActionLogDialogAtom } from "@/atoms/agent/action-log-dialog.atom";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface ActionLogButtonProps {
	threadId: number | null;
}

/**
 * Header button that opens the agent action log dialog for the current
 * thread. Renders nothing when:
 *   - the action log feature flag is off (graceful no-op for older
 *     deployments), OR
 *   - there is no active thread (lazy-created chats haven't started).
 */
export function ActionLogButton({ threadId }: ActionLogButtonProps) {
	const { data: flags } = useAtomValue(agentFlagsAtom);
	const open = useSetAtom(openActionLogDialogAtom);

	const enabled = !!flags?.enable_action_log && !flags?.disable_new_agent_stack;

	const handleClick = useCallback(() => {
		if (threadId !== null) open(threadId);
	}, [open, threadId]);

	if (!enabled || threadId === null) return null;

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					size="sm"
					variant="ghost"
					className="size-8 p-0"
					aria-label="Open agent action log"
					onClick={handleClick}
				>
					<Workflow className="size-4 text-muted-foreground" />
				</Button>
			</TooltipTrigger>
			<TooltipContent>Agent actions</TooltipContent>
		</Tooltip>
	);
}

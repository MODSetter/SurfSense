"use client";

import { ChevronRightIcon } from "lucide-react";
import { type FC, useEffect, useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { HitlApprovalCard, usePendingInterrupt } from "@/features/chat-messages/hitl";
import { cn } from "@/lib/utils";
import { groupItems } from "./grouping";
import { resolveItemTitle } from "./subagent-rename";
import { TimelineGroupRow } from "./timeline-group-row";
import type { ItemStatus, TimelineItem } from "./types";

/**
 * Force a stale "running" to read as "completed" once the thread
 * stops, so the chrome doesn't keep pulsing forever after a stream
 * is aborted or disconnected.
 */
function effectiveStatus(status: ItemStatus, isThreadRunning: boolean): ItemStatus {
	if (status === "running" && !isThreadRunning) return "completed";
	return status;
}

/**
 * The "process" surface in the body | timeline split. Pure consumer
 * of ``TimelineItem[]`` — owns the collapsible chrome and tree
 * indent only. Pending HITL interrupts mount ``HitlApprovalCard`` at
 * the bottom; the card owns its own decision/pager state.
 */
export const Timeline: FC<{
	items: readonly TimelineItem[];
	isThreadRunning?: boolean;
}> = ({ items, isThreadRunning = true }) => {
	const pendingValue = usePendingInterrupt();
	const pendingInterrupt = pendingValue?.pendingInterrupt ?? null;
	const onSubmit = pendingValue?.onSubmit;
	const hasPending = pendingInterrupt !== null;

	// Apply the override here so downstream (grouping, headers, dots)
	// sees the corrected status without threading a callback. Keeps
	// ``buildTimeline`` pure.
	const effectiveItems = useMemo<TimelineItem[]>(
		() =>
			items.map((it) => ({
				...it,
				status: effectiveStatus(it.status, isThreadRunning),
			})),
		[items, isThreadRunning]
	);

	const inProgressItem = useMemo(
		() => effectiveItems.find((it) => it.status === "running"),
		[effectiveItems]
	);
	const inProgressTitle = useMemo(
		() => (inProgressItem ? resolveItemTitle(inProgressItem, getToolDisplayName) : undefined),
		[inProgressItem]
	);

	// "Settled" includes cancelled/errored, not just completed —
	// rejecting an interrupt leaves items in ``cancelled`` and the
	// timeline still needs to auto-collapse.
	const allSettled = useMemo(
		() =>
			effectiveItems.length > 0 &&
			!isThreadRunning &&
			!hasPending &&
			effectiveItems.every(
				(it) => it.status === "completed" || it.status === "cancelled" || it.status === "error"
			),
		[effectiveItems, isThreadRunning, hasPending]
	);
	const isProcessing = (isThreadRunning || hasPending) && !allSettled;

	const [isOpen, setIsOpen] = useState(() => isProcessing);
	useEffect(() => {
		if (isProcessing) {
			setIsOpen(true);
			return;
		}
		if (allSettled) {
			setIsOpen(false);
		}
	}, [allSettled, isProcessing]);

	const groups = useMemo(() => groupItems(effectiveItems), [effectiveItems]);

	if (effectiveItems.length === 0 && !hasPending) return null;

	const headerText = (() => {
		if (allSettled) return "Reviewed";
		if (hasPending) return "Awaiting your decision";
		if (inProgressTitle) return inProgressTitle;
		if (isProcessing) return "Processing";
		return "Reviewed";
	})();

	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<div className="rounded-lg">
				<Button
					variant="ghost"
					type="button"
					onClick={() => setIsOpen((prev) => !prev)}
					className={cn(
						"h-auto w-full justify-start gap-1.5 p-0 text-left text-sm font-normal transition-colors hover:bg-transparent",
						"text-muted-foreground hover:text-accent-foreground"
					)}
				>
					{isProcessing ? (
						<TextShimmerLoader text={headerText} size="sm" />
					) : (
						<span>{headerText}</span>
					)}
					<ChevronRightIcon
						data-icon="inline-end"
						className={cn("transition-transform duration-200", isOpen && "rotate-90")}
					/>
				</Button>

				<div
					className={cn(
						"grid transition-[grid-template-rows] duration-300 ease-out",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-3 pl-1">
							{groups.map((group, idx) => {
								const showLine = idx < groups.length - 1 || hasPending;
								return (
									<TimelineGroupRow
										key={group.parent.id}
										group={group}
										parentStatus={group.parent.status}
										showParentLine={showLine}
									/>
								);
							})}
							{pendingInterrupt && onSubmit && (
								<div className="pl-5">
									<HitlApprovalCard pendingInterrupt={pendingInterrupt} onSubmit={onSubmit} />
								</div>
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

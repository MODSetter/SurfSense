"use client";

import { ChevronRightIcon } from "lucide-react";
import { type FC, useEffect, useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { PagerChrome, useHitlBundle } from "@/features/chat-messages/hitl";
import { cn } from "@/lib/utils";
import { groupItems } from "./grouping";
import { resolveItemTitle } from "./subagent-rename";
import { TimelineGroupRow } from "./timeline-group-row";
import type { ItemStatus, TimelineItem } from "./types";

/**
 * Override coarse status when the thread isn't running anymore: a
 * stale "running" must read as "completed" so the chrome stops
 * pulsing. Mirrors the legacy ``getEffectiveStatus`` from
 * ``thinking-steps.tsx``.
 */
function effectiveStatus(status: ItemStatus, isThreadRunning: boolean): ItemStatus {
	if (status === "running" && !isThreadRunning) return "completed";
	return status;
}

/**
 * True when a tool-call's result is an HITL interrupt the user has
 * NOT decided on yet. The backend marks the step as ``completed``
 * (the tool DID complete — it returned an interrupt as its result),
 * which would normally collapse the timeline. This predicate lets the
 * chrome treat "waiting on user" as still-in-progress.
 *
 * Decided interrupts (``__decided__`` set to "approve"/"reject"/
 * "edit") count as completed for chrome purposes — the resume stream
 * will take it from there.
 */
function isPendingInterrupt(result: unknown): boolean {
	if (typeof result !== "object" || result === null) return false;
	const r = result as { __interrupt__?: unknown; __decided__?: unknown };
	return r.__interrupt__ === true && r.__decided__ === undefined;
}

/**
 * The chain-of-thought timeline. The "process" surface in the
 * `body | timeline` split — owns chrome (collapsible header, tree
 * dots/lines, indent, group iteration) and dispatches to per-kind
 * items for the actual content.
 *
 * Rendering responsibilities (kept here, not on items):
 *  - Outer max-width container.
 *  - Collapsible header with state-aware label ("Reviewed" /
 *    "Processing" / current step title) and shimmer.
 *  - Open/close state derived from ``isThreadRunning`` + completion.
 *  - Status dot + vertical connector line per group (delegates the
 *    inner row to ``TimelineGroupRow``).
 *  - Mounting ``PagerChrome`` once at the bottom when the HITL bundle
 *    is active (multi-approval coordination — see
 *    ``hitl/bundle/bundle-context.tsx``).
 *
 * Pure consumption of ``TimelineItem[]`` — does NOT call
 * ``buildTimeline`` itself. The data-renderer adapter does that and
 * passes the items in.
 */
export const Timeline: FC<{
	items: readonly TimelineItem[];
	isThreadRunning?: boolean;
}> = ({ items, isThreadRunning = true }) => {
	const bundle = useHitlBundle();

	// Apply the runtime ``isThreadRunning`` override to every item once,
	// up-front, so downstream code (grouping, group rows, item headers,
	// status dot, all children) sees the corrected coarse status without
	// having to thread a callback through. ``buildTimeline`` stays pure;
	// the override is purely a render-time concern that lives here.
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

	// Detect a tool-call that's parked on an HITL interrupt the user hasn't
	// decided yet. Treated as "still in progress" by the chrome so the
	// timeline doesn't auto-collapse on the user mid-decision (the LangGraph
	// thread paused, but the agent's work is conceptually unfinished).
	const pendingInterruptItem = useMemo(
		() => effectiveItems.find((it) => it.kind === "tool-call" && isPendingInterrupt(it.result)),
		[effectiveItems]
	);
	const pendingInterruptTitle = useMemo(
		() =>
			pendingInterruptItem ? resolveItemTitle(pendingInterruptItem, getToolDisplayName) : undefined,
		[pendingInterruptItem]
	);

	const allCompleted = useMemo(
		() =>
			effectiveItems.length > 0 &&
			!isThreadRunning &&
			!pendingInterruptItem &&
			effectiveItems.every((it) => it.status === "completed"),
		[effectiveItems, isThreadRunning, pendingInterruptItem]
	);
	const isProcessing = (isThreadRunning || !!pendingInterruptItem) && !allCompleted;

	const [isOpen, setIsOpen] = useState(() => isProcessing);
	useEffect(() => {
		if (isProcessing) {
			setIsOpen(true);
			return;
		}
		if (allCompleted) {
			setIsOpen(false);
		}
	}, [allCompleted, isProcessing]);

	const groups = useMemo(() => groupItems(effectiveItems), [effectiveItems]);

	if (effectiveItems.length === 0) return null;

	const headerText = (() => {
		if (allCompleted) return "Reviewed";
		if (inProgressTitle) return inProgressTitle;
		// Pending HITL: prefer the tool's own name so the user knows WHICH
		// approval is gating progress (e.g. "Update Notion page") rather
		// than a generic "Awaiting approval" label.
		if (pendingInterruptTitle) return pendingInterruptTitle;
		if (isProcessing) return "Processing";
		return "Reviewed";
	})();

	return (
		<div className="mx-auto w-full max-w-(--thread-max-width) px-2 py-2">
			<div className="rounded-lg">
				<button
					type="button"
					onClick={() => setIsOpen((prev) => !prev)}
					className={cn(
						"flex w-full items-center gap-1.5 text-left text-sm transition-colors",
						"text-muted-foreground hover:text-foreground"
					)}
				>
					{isProcessing ? (
						<TextShimmerLoader text={headerText} size="sm" />
					) : (
						<span>{headerText}</span>
					)}
					<ChevronRightIcon
						className={cn("size-4 transition-transform duration-200", isOpen && "rotate-90")}
					/>
				</button>

				<div
					className={cn(
						"grid transition-[grid-template-rows] duration-300 ease-out",
						isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
					)}
				>
					<div className="overflow-hidden">
						<div className="mt-3 pl-1">
							{groups.map((group, groupIndex) => (
								<TimelineGroupRow
									key={group.parent.id}
									group={group}
									parentStatus={group.parent.status}
									showParentLine={groupIndex < groups.length - 1}
								/>
							))}

							{bundle && <PagerChrome />}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

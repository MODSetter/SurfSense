"use client";

import type { FC } from "react";
import { cn } from "@/lib/utils";
import { ReasoningItem, ToolCallItem } from "./items";
import type { ItemStatus, TimelineGroup, TimelineItem } from "./types";

function renderItem(item: TimelineItem) {
	if (item.kind === "reasoning") return <ReasoningItem item={item} />;
	return <ToolCallItem item={item} />;
}

/**
 * Single group row in the timeline tree: status dot + connector line in
 * the gutter, parent item content + indented children in the body.
 *
 * The connector line overshoots by ~15px to land on the next group's
 * dot center; the line passes BEHIND any indented children (whose
 * column has no dot of its own) for a clean tree look.
 */
export const TimelineGroupRow: FC<{
	group: TimelineGroup;
	parentStatus: ItemStatus;
	showParentLine: boolean;
}> = ({ group, parentStatus, showParentLine }) => {
	const hasChildren = group.children.length > 0;

	return (
		<div className="relative flex gap-3">
			<div className="relative flex flex-col items-center w-2 self-stretch">
				{showParentLine && (
					<div className="absolute left-1/2 top-[15px] -bottom-[15px] w-px -translate-x-1/2 bg-muted-foreground/30" />
				)}
				<div className="relative z-10 mt-[7px] flex shrink-0 items-center justify-center">
					{parentStatus === "running" ? (
						<span className="relative flex size-2">
							<span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
							<span className="relative inline-flex size-2 rounded-full bg-primary" />
						</span>
					) : (
						<span
							className={cn(
								"size-2 rounded-full",
								parentStatus === "error"
									? "bg-destructive"
									: parentStatus === "cancelled"
										? "bg-muted-foreground/40"
										: "bg-muted-foreground/30"
							)}
						/>
					)}
				</div>
			</div>

			<div className="flex-1 min-w-0 pb-4">
				{renderItem(group.parent)}

				{hasChildren && (
					<div className="mt-2 ml-3 space-y-2">
						{group.children.map((child) => (
							<div key={child.id}>{renderItem(child)}</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
};

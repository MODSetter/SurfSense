"use client";

import type { FC } from "react";
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
}> = ({ group, showParentLine }) => {
	const hasChildren = group.children.length > 0;

	return (
		<div className="relative min-w-0 pb-4">
			{showParentLine ? (
				<div className="absolute top-5 bottom-0 left-[7.5px] w-px bg-muted-foreground/25" />
			) : null}
			<div className="relative min-w-0">
				{renderItem(group.parent)}

				{hasChildren && (
					<div className="mt-2 ml-2 space-y-2 border-l border-muted-foreground/25 pl-5">
						{group.children.map((child) => (
							<div key={child.id}>{renderItem(child)}</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
};

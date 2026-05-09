import type { FC } from "react";
import { ChainOfThoughtItem } from "@/components/prompt-kit/chain-of-thought";
import { cn } from "@/lib/utils";
import type { ItemStatus } from "../types";

/**
 * The title row + sub-bullets shared by every timeline item kind. The
 * timeline's chrome (status dot, indent, vertical line) renders to the
 * left; this fills the right column.
 *
 * Status-aware text styling matches the legacy ``StepBody`` semantics:
 *   running   → emphasised (font-medium foreground)
 *   completed → muted
 *   pending   → muted/60
 *   error     → destructive
 *   cancelled → strikethrough muted
 *
 * Sub-bullets render via ``ChainOfThoughtItem`` (reused from
 * ``components/prompt-kit/chain-of-thought``) — same component the
 * legacy ``StepBody`` used.
 */
export const ItemHeader: FC<{
	title: string;
	status: ItemStatus;
	items?: readonly string[];
	itemKey: string;
}> = ({ title, status, items, itemKey }) => (
	<div className="min-w-0">
		<div
			className={cn(
				"text-sm leading-5",
				status === "running" && "text-foreground font-medium",
				status === "completed" && "text-muted-foreground",
				status === "pending" && "text-muted-foreground/60",
				status === "error" && "text-destructive",
				status === "cancelled" && "text-muted-foreground line-through"
			)}
		>
			{title}
		</div>

		{items && items.length > 0 && (
			<div className="mt-1 space-y-0.5">
				{items.map((item) => (
					<ChainOfThoughtItem key={`${itemKey}-${item}`} className="text-xs">
						{item}
					</ChainOfThoughtItem>
				))}
			</div>
		)}
	</div>
);

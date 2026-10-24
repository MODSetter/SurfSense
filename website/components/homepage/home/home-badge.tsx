import type * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The marketing site's pill label: section kickers, tags, facts in a row.
 *
 * Its own component rather than shadcn's `secondary` badge: that variant fills
 * with `--secondary`, a few steps off this page's ground, and the token cannot
 * deepen because hovers and tinted cells depend on it. `--home-badge` is the
 * fill made for this ground.
 */
export function HomeBadge({ className, ...props }: React.ComponentProps<"span">) {
	return (
		<span
			className={cn(
				"inline-flex w-fit shrink-0 items-center gap-1 rounded-full bg-(--home-badge) px-4 py-1.5 text-sm font-medium whitespace-nowrap text-foreground",
				className
			)}
			{...props}
		/>
	);
}

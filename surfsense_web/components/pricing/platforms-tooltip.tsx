"use client";

import { PLUGIN_PLATFORMS } from "@/components/pricing/pricing-content";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Underlines "9 platforms" in the Individual plan's feature list and, on
 * hover/focus, lists every platform it covers plus the web crawler — the
 * same ten tiles as `/plugins` (`app/(home)/plugins/page.tsx`).
 */
export function PlatformsTooltip({ children }: { children: string }) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<span className="cursor-default underline decoration-dotted underline-offset-4">
					{children}
				</span>
			</TooltipTrigger>
			<TooltipContent className="max-w-64">
				<p>{[...PLUGIN_PLATFORMS, "Web Crawl"].join(", ")}</p>
			</TooltipContent>
		</Tooltip>
	);
}

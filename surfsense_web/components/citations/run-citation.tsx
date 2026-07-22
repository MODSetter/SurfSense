"use client";

import { useSetAtom } from "jotai";
import { Database } from "lucide-react";
import type { FC } from "react";
import { openRunCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Inline citation badge for a scraper run; opens the run in the citation panel. */
export const RunCitation: FC<{ runId: string }> = ({ runId }) => {
	const openRunPanel = useSetAtom(openRunCitationPanelAtom);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					onClick={() => openRunPanel({ runId })}
					className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
					aria-label="View scraper run"
				>
					<Database className="size-3" />
					run
				</Button>
			</TooltipTrigger>
			<TooltipContent>View scraper run</TooltipContent>
		</Tooltip>
	);
};

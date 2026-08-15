"use client";

import { useSetAtom } from "jotai";
import { Database } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { openRunCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { RunCitationPanelContent } from "@/components/citations/run-citation-panel";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/use-media-query";

/** Inline citation badge for a scraper run; opens the run in the citation panel. */
export const RunCitation: FC<{ runId: string }> = ({ runId }) => {
	const openRunPanel = useSetAtom(openRunCitationPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false);

	return (
		<>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						onClick={() => (isDesktop ? openRunPanel({ runId }) : setMobilePreviewOpen(true))}
						className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
						aria-label="See where this came from"
					>
						<Database className="size-3" />
						Source
					</Button>
				</TooltipTrigger>
				<TooltipContent>See where this came from</TooltipContent>
			</Tooltip>
			<Drawer
				open={mobilePreviewOpen}
				onOpenChange={setMobilePreviewOpen}
				shouldScaleBackground={false}
			>
				<DrawerContent
					className="h-[85vh] max-h-[85vh] z-80 overflow-hidden"
					overlayClassName="z-80"
				>
					<DrawerHandle />
					<DrawerHeader className="pb-0">
						<DrawerTitle>Source</DrawerTitle>
					</DrawerHeader>
					<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
						<RunCitationPanelContent runId={runId} />
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
};

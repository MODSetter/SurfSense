"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { LayersIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
	artifactsPanelOpenAtom,
	chatArtifactsAtom,
	toggleArtifactsPanelAtom,
} from "../state/artifacts-panel.atom";

/** Header toggle that opens the artifacts sidebar. Hidden when the thread has none. */
export function ArtifactsToggleButton() {
	const artifacts = useAtomValue(chatArtifactsAtom);
	const isOpen = useAtomValue(artifactsPanelOpenAtom);
	const toggle = useSetAtom(toggleArtifactsPanelAtom);

	if (artifacts.length === 0) return null;

	const label = isOpen ? "Hide artifacts" : "Show artifacts";

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					onClick={() => toggle()}
					aria-pressed={isOpen}
					className={cn(
						"relative h-8 w-8 shrink-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground",
						isOpen && "bg-accent text-accent-foreground"
					)}
				>
					<LayersIcon className="h-4 w-4" />
					<span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium text-primary-foreground tabular-nums">
						{artifacts.length}
					</span>
					<span className="sr-only">{label}</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="bottom">{label}</TooltipContent>
		</Tooltip>
	);
}

"use client";

import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import type { LivePodcast } from "@/hooks/use-podcast-live";
import { BriefReview } from "./brief-review";

interface PodcastReviewSheetProps {
	podcast: LivePodcast;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/**
 * The podcast panel: hosts the brief gate, the only approval in the lifecycle
 * — after it the episode generates unattended.
 */
export function PodcastReviewSheet({ podcast, open, onOpenChange }: PodcastReviewSheetProps) {
	const close = () => onOpenChange(false);

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="right" className="flex w-full flex-col sm:max-w-xl">
				{podcast.status === "awaiting_brief" && podcast.spec ? (
					<>
						<SheetHeader>
							<SheetTitle>Review podcast brief</SheetTitle>
							<SheetDescription>
								Confirm the language, voices, and length — the episode generates unattended after
								this.
							</SheetDescription>
						</SheetHeader>
						<div className="overflow-y-auto px-4 pb-4">
							<BriefReview podcast={podcast} spec={podcast.spec} onApproved={close} />
						</div>
					</>
				) : (
					<SheetHeader>
						<SheetTitle>{podcast.title}</SheetTitle>
						<SheetDescription>Nothing is awaiting review right now.</SheetDescription>
					</SheetHeader>
				)}
			</SheetContent>
		</Sheet>
	);
}

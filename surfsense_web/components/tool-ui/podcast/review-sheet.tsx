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
import { TranscriptReview } from "./transcript-review";

interface PodcastReviewSheetProps {
	podcast: LivePodcast;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/**
 * The podcast panel: hosts whichever gate the lifecycle is waiting on. The
 * pushed status decides the content, so the same sheet serves both gates and
 * simply closes once the podcast moves on.
 */
export function PodcastReviewSheet({ podcast, open, onOpenChange }: PodcastReviewSheetProps) {
	const close = () => onOpenChange(false);

	const gate =
		podcast.status === "awaiting_brief" && podcast.spec ? (
			<>
				<SheetHeader>
					<SheetTitle>Review podcast brief</SheetTitle>
					<SheetDescription>
						Confirm the language, voices, and length before the transcript is drafted.
					</SheetDescription>
				</SheetHeader>
				<div className="overflow-y-auto px-4 pb-4">
					<BriefReview podcast={podcast} spec={podcast.spec} onApproved={close} />
				</div>
			</>
		) : podcast.status === "awaiting_review" ? (
			<>
				<SheetHeader>
					<SheetTitle>Review transcript</SheetTitle>
					<SheetDescription>
						Approve the script to render the audio, or regenerate a fresh draft.
					</SheetDescription>
				</SheetHeader>
				<div className="min-h-0 flex-1 px-4 pb-4">
					<TranscriptReview podcast={podcast} onDecided={close} />
				</div>
			</>
		) : (
			<SheetHeader>
				<SheetTitle>{podcast.title}</SheetTitle>
				<SheetDescription>Nothing is awaiting review right now.</SheetDescription>
			</SheetHeader>
		);

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="right" className="flex w-full flex-col sm:max-w-xl">
				{gate}
			</SheetContent>
		</Sheet>
	);
}

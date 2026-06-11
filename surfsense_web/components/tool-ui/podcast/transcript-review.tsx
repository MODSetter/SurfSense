"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import type { PodcastDetail } from "@/contracts/types/podcast.types";
import type { LivePodcast } from "@/hooks/use-podcast-live";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { speakerLabel } from "./schema";

interface TranscriptReviewProps {
	podcast: LivePodcast;
	onDecided: () => void;
}

/**
 * Gate 2: a go/no-go on the drafted script before the expensive render.
 * Read-only by design — approve it, regenerate a fresh draft, or cancel.
 */
export function TranscriptReview({ podcast, onDecided }: TranscriptReviewProps) {
	const [detail, setDetail] = useState<PodcastDetail | null>(null);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [pendingAction, setPendingAction] = useState<"approve" | "regenerate" | "cancel" | null>(
		null
	);

	useEffect(() => {
		let cancelled = false;
		setDetail(null);
		setLoadError(null);
		podcastsApiService
			.getDetail(podcast.id)
			.then((data) => {
				if (!cancelled) setDetail(data);
			})
			.catch((error) => {
				if (!cancelled) {
					setLoadError(error instanceof Error ? error.message : "Failed to load the transcript");
				}
			});
		return () => {
			cancelled = true;
		};
	}, [podcast.id]);

	const act = async (action: "approve" | "regenerate" | "cancel", run: () => Promise<unknown>) => {
		setPendingAction(action);
		try {
			await run();
			onDecided();
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Action failed");
		} finally {
			setPendingAction(null);
		}
	};

	if (loadError) {
		return <p className="text-sm text-destructive">{loadError}</p>;
	}

	if (!detail) {
		return <TextShimmerLoader text="Loading transcript" size="sm" />;
	}

	const turns = detail.transcript?.turns ?? [];

	return (
		<div className="flex h-full flex-col gap-4">
			<div className="flex-1 space-y-3 overflow-y-auto rounded-lg border bg-muted/30 p-4 select-text">
				{turns.map((turn, idx) => (
					<div key={`${idx}-${turn.speaker}`} className="text-sm">
						<span className="font-medium text-primary">
							{speakerLabel(detail.spec, turn.speaker)}:
						</span>{" "}
						<span className="text-muted-foreground">{turn.text}</span>
					</div>
				))}
				{turns.length === 0 ? (
					<p className="text-sm text-muted-foreground">No transcript available.</p>
				) : null}
			</div>

			<div className="flex justify-end gap-2">
				<Button
					type="button"
					variant="ghost"
					disabled={pendingAction !== null}
					onClick={() => act("cancel", () => podcastsApiService.cancel(podcast.id))}
				>
					{pendingAction === "cancel" ? <Loader2 className="size-4 animate-spin" /> : null}
					Cancel podcast
				</Button>
				<Button
					type="button"
					variant="outline"
					disabled={pendingAction !== null}
					onClick={() =>
						act("regenerate", () => podcastsApiService.regenerateTranscript(podcast.id))
					}
				>
					{pendingAction === "regenerate" ? <Loader2 className="size-4 animate-spin" /> : null}
					Regenerate
				</Button>
				<Button
					type="button"
					disabled={pendingAction !== null || turns.length === 0}
					onClick={() => act("approve", () => podcastsApiService.approveTranscript(podcast.id))}
				>
					{pendingAction === "approve" ? <Loader2 className="size-4 animate-spin" /> : null}
					Approve &amp; render audio
				</Button>
			</div>
		</div>
	);
}

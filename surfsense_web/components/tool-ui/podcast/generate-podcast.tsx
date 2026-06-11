"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import type { PodcastSpec } from "@/contracts/types/podcast.types";
import { usePodcastLive } from "@/hooks/use-podcast-live";
import { PodcastErrorState, PodcastPlayer } from "./player";
import { PodcastReviewSheet } from "./review-sheet";
import type { GeneratePodcastArgs, GeneratePodcastResult } from "./schema";

function WorkingState({ title, label }: { title: string; label: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text={label} size="sm" />
			</div>
		</div>
	);
}

function NoticeState({ title, message }: { title: string; message: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-muted-foreground">{title}</p>
				<p className="text-xs text-muted-foreground mt-0.5">{message}</p>
			</div>
		</div>
	);
}

function briefSummary(spec: PodcastSpec | null): string | null {
	if (!spec) return null;
	const speakers = spec.speakers.length === 1 ? "1 speaker" : `${spec.speakers.length} speakers`;
	return `${spec.language} · ${speakers} · ${spec.duration.min_minutes}–${spec.duration.max_minutes} min`;
}

function ReviewGateCard({
	title,
	heading,
	summary,
	buttonLabel,
	onReview,
}: {
	title: string;
	heading: string;
	summary: string | null;
	buttonLabel: string;
	onReview: () => void;
}) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<p className="text-xs text-muted-foreground mt-0.5">{heading}</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="flex items-center justify-between gap-3 px-5 py-4">
				<p className="text-xs text-muted-foreground">{summary}</p>
				<Button type="button" size="sm" onClick={onReview}>
					{buttonLabel}
				</Button>
			</div>
		</div>
	);
}

/** Status-driven card for an authenticated viewer, fed by Zero push. */
function LivePodcastCard({
	podcastId,
	fallbackTitle,
}: {
	podcastId: number;
	fallbackTitle: string;
}) {
	const { podcast, isLoading } = usePodcastLive(podcastId);
	const [reviewOpen, setReviewOpen] = useState(false);

	if (!podcast) {
		if (isLoading) {
			return <WorkingState title={fallbackTitle} label="Loading podcast" />;
		}
		return (
			<NoticeState
				title="Podcast Unavailable"
				message="This podcast no longer exists or you don't have access to it."
			/>
		);
	}

	const title = podcast.title || fallbackTitle;

	switch (podcast.status) {
		case "pending":
			return <WorkingState title={title} label="Preparing brief" />;
		case "drafting":
			return <WorkingState title={title} label="Drafting transcript" />;
		case "rendering":
			return <WorkingState title={title} label="Rendering audio" />;
		case "awaiting_brief":
		case "awaiting_review": {
			const isBriefGate = podcast.status === "awaiting_brief";
			return (
				<>
					<ReviewGateCard
						title={title}
						heading={
							isBriefGate ? "Brief ready for your review" : "Transcript ready for your review"
						}
						summary={briefSummary(podcast.spec)}
						buttonLabel={isBriefGate ? "Review brief" : "Review transcript"}
						onReview={() => setReviewOpen(true)}
					/>
					<PodcastReviewSheet podcast={podcast} open={reviewOpen} onOpenChange={setReviewOpen} />
				</>
			);
		}
		case "ready":
			return (
				<PodcastPlayer
					podcastId={podcast.id}
					title={title}
					durationMs={podcast.durationSeconds ? podcast.durationSeconds * 1000 : undefined}
				/>
			);
		case "failed":
			return <PodcastErrorState title={title} error={podcast.error || "Generation failed"} />;
		case "cancelled":
			return <NoticeState title="Podcast Cancelled" message="This podcast was cancelled." />;
	}
}

/**
 * Tool UI for `generate_podcast`. The tool only prepares the podcast (it
 * returns with the brief awaiting review), so this card follows the lifecycle
 * by Zero push and opens the review panel at each gate. Public shared chats
 * have no Zero session; their snapshots only ever contain finished episodes,
 * so the player renders directly against the share-token endpoints.
 */
export const GeneratePodcastToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<GeneratePodcastArgs, GeneratePodcastResult>) => {
	const pathname = usePathname();
	const isPublicRoute = !!pathname?.startsWith("/public/");
	const title = args.podcast_title || "SurfSense Podcast";

	if (status.type === "running" || status.type === "requires-action") {
		return <WorkingState title={title} label="Preparing podcast" />;
	}

	if (status.type === "incomplete") {
		if (status.reason === "cancelled") {
			return <NoticeState title="Podcast Cancelled" message="Podcast preparation was cancelled." />;
		}
		if (status.reason === "error") {
			return (
				<PodcastErrorState
					title={title}
					error={typeof status.error === "string" ? status.error : "An error occurred"}
				/>
			);
		}
	}

	if (!result) {
		return <WorkingState title={title} label="Preparing podcast" />;
	}

	if (result.podcast_id) {
		if (isPublicRoute) {
			return <PodcastPlayer podcastId={result.podcast_id} title={result.title || title} />;
		}
		return <LivePodcastCard podcastId={result.podcast_id} fallbackTitle={result.title || title} />;
	}

	if (result.status === "failed" || result.status === "error") {
		return <PodcastErrorState title={title} error={result.error || "Generation failed"} />;
	}

	// Legacy saved chats: results identified only by a Celery task id can't be
	// recovered through the lifecycle API.
	return (
		<NoticeState
			title="Podcast Unavailable"
			message="This podcast was generated with an older version. Please generate a new one."
		/>
	);
};

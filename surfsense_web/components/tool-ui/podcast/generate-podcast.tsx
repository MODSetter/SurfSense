"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { Loader2, RotateCcw } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { type LivePodcast, usePodcastLive } from "@/hooks/use-podcast-live";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { BriefReview } from "./brief-review";
import { PodcastErrorState, PodcastPlayer } from "./player";
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

/**
 * Regenerating reopens the brief and ultimately replaces the current audio,
 * so a stray click is guarded by an inline confirm step.
 */
function RegenerateButton({ podcast }: { podcast: LivePodcast }) {
	const [confirming, setConfirming] = useState(false);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const regenerate = async () => {
		setIsSubmitting(true);
		try {
			await podcastsApiService.regenerate(podcast.id);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Failed to regenerate the podcast");
		} finally {
			setIsSubmitting(false);
			setConfirming(false);
		}
	};

	if (!confirming) {
		return (
			<Button
				type="button"
				variant="ghost"
				size="sm"
				className="text-muted-foreground"
				onClick={() => setConfirming(true)}
			>
				<RotateCcw className="size-3.5" /> Regenerate
			</Button>
		);
	}

	return (
		<div className="flex items-center gap-2">
			<span className="text-xs text-muted-foreground">
				Reopen the brief and replace this episode?
			</span>
			<Button
				type="button"
				variant="ghost"
				size="sm"
				onClick={() => setConfirming(false)}
				disabled={isSubmitting}
			>
				Keep it
			</Button>
			<Button
				type="button"
				variant="destructive"
				size="sm"
				onClick={regenerate}
				disabled={isSubmitting}
			>
				{isSubmitting ? <Loader2 className="size-3.5 animate-spin" /> : null}
				Regenerate
			</Button>
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
			// The gate lives right in the chat: the form is the card, so there
			// is nothing to open and nothing to dismiss.
			if (!podcast.spec) {
				return <WorkingState title={title} label="Preparing brief" />;
			}
			return (
				<div className="my-4 max-w-xl overflow-hidden rounded-2xl border bg-muted/30">
					<div className="px-5 pt-5 pb-3 select-none">
						<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
						<p className="text-xs text-muted-foreground mt-0.5">
							Confirm the language, voices, and length — the episode generates automatically after
							you approve.
						</p>
					</div>
					<div className="mx-5 h-px bg-border/50" />
					<div className="px-5 py-4">
						<BriefReview podcast={podcast} spec={podcast.spec} />
					</div>
				</div>
			);
		case "awaiting_review":
			// Legacy rows parked at the removed transcript gate; the only way
			// forward is regenerating through the brief gate.
			return (
				<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
					<div className="px-5 pt-5 pb-4">
						<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
						<p className="text-xs text-muted-foreground mt-0.5">
							This podcast was drafted before audio rendering became automatic.
						</p>
					</div>
					<div className="mx-5 h-px bg-border/50" />
					<div className="flex justify-end px-5 py-3">
						<RegenerateButton podcast={podcast} />
					</div>
				</div>
			);
		case "ready":
			return (
				<div>
					<PodcastPlayer
						podcastId={podcast.id}
						title={title}
						durationMs={podcast.durationSeconds ? podcast.durationSeconds * 1000 : undefined}
					/>
					<div className="-mt-2 mb-4 flex max-w-lg justify-end">
						<RegenerateButton podcast={podcast} />
					</div>
				</div>
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
 * by Zero push, rendering the brief form inline at the gate. Public shared
 * chats have no Zero session; their snapshots only ever contain finished
 * episodes, so the player renders directly against the share-token endpoints.
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

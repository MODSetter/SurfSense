"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useParams, usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Audio } from "@/components/tool-ui/audio";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { clearActivePodcastTaskId, setActivePodcastTaskId } from "@/lib/chat/podcast-state";

/**
 * Zod schemas for runtime validation
 */
const GeneratePodcastArgsSchema = z.object({
	source_content: z.string(),
	podcast_title: z.string().nullish(),
	user_prompt: z.string().nullish(),
});

const GeneratePodcastResultSchema = z.object({
	// Support both old and new status values for backwards compatibility
	status: z.enum([
		"pending",
		"generating",
		"ready",
		"failed",
		// Legacy values from old saved chats
		"processing",
		"already_generating",
		"success",
		"error",
	]),
	podcast_id: z.number().nullish(),
	task_id: z.string().nullish(), // Legacy field for old saved chats
	title: z.string().nullish(),
	transcript_entries: z.number().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

const PodcastStatusResponseSchema = z.object({
	status: z.enum(["pending", "generating", "ready", "failed"]),
	id: z.number(),
	title: z.string(),
	transcript_entries: z.number().nullish(),
	error: z.string().nullish(),
});

const PodcastTranscriptEntrySchema = z.object({
	speaker_id: z.number(),
	dialog: z.string(),
});

const PodcastDetailsSchema = z.object({
	podcast_transcript: z.array(PodcastTranscriptEntrySchema).nullish(),
});

/**
 * Types derived from Zod schemas
 */
type GeneratePodcastArgs = z.infer<typeof GeneratePodcastArgsSchema>;
type GeneratePodcastResult = z.infer<typeof GeneratePodcastResultSchema>;
type PodcastStatusResponse = z.infer<typeof PodcastStatusResponseSchema>;
type PodcastTranscriptEntry = z.infer<typeof PodcastTranscriptEntrySchema>;

/**
 * Parse and validate podcast status response
 */
function parsePodcastStatusResponse(data: unknown): PodcastStatusResponse | null {
	const result = PodcastStatusResponseSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid podcast status response:", result.error.issues);
		return null;
	}
	return result.data;
}

/**
 * Parse and validate podcast details
 */
function parsePodcastDetails(data: unknown): { podcast_transcript?: PodcastTranscriptEntry[] } {
	const result = PodcastDetailsSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid podcast details:", result.error.issues);
		return {};
	}
	return {
		podcast_transcript: result.data.podcast_transcript ?? undefined,
	};
}

function PodcastGeneratingState({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text="Generating podcast" size="sm" />
			</div>
		</div>
	);
}

function PodcastErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Podcast Generation Failed</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm font-medium text-foreground line-clamp-2">{title}</p>
				<p className="text-sm text-muted-foreground mt-1">{error}</p>
			</div>
		</div>
	);
}

function AudioLoadingState({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text="Loading audio" size="sm" />
			</div>
		</div>
	);
}

function PodcastPlayer({
	podcastId,
	title,
	durationMs,
}: {
	podcastId: number;
	title: string;
	durationMs?: number;
}) {
	const params = useParams();
	const pathname = usePathname();
	const isPublicRoute = pathname?.startsWith("/public/");
	const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

	const [audioSrc, setAudioSrc] = useState<string | null>(null);
	const [transcript, setTranscript] = useState<PodcastTranscriptEntry[] | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const objectUrlRef = useRef<string | null>(null);

	// Cleanup object URL on unmount
	useEffect(() => {
		return () => {
			if (objectUrlRef.current) {
				URL.revokeObjectURL(objectUrlRef.current);
			}
		};
	}, []);

	// Fetch audio and podcast details (including transcript)
	const loadPodcast = useCallback(async () => {
		setIsLoading(true);
		setError(null);

		try {
			// Revoke previous object URL if exists
			if (objectUrlRef.current) {
				URL.revokeObjectURL(objectUrlRef.current);
				objectUrlRef.current = null;
			}

			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

			try {
				let audioBlob: Blob;
				let rawPodcastDetails: unknown = null;

				if (shareToken) {
					// Public view - use public endpoints (baseApiService handles no-auth for /api/v1/public/)
					const [blob, details] = await Promise.all([
						baseApiService.getBlob(`/api/v1/public/${shareToken}/podcasts/${podcastId}/stream`),
						baseApiService.get(`/api/v1/public/${shareToken}/podcasts/${podcastId}`),
					]);
					audioBlob = blob;
					rawPodcastDetails = details;
				} else {
					// Authenticated view - fetch audio and details in parallel
					const [audioResponse, details] = await Promise.all([
						authenticatedFetch(
							`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcastId}/audio`,
							{ method: "GET", signal: controller.signal }
						),
						baseApiService.get<unknown>(`/api/v1/podcasts/${podcastId}`),
					]);

					if (!audioResponse.ok) {
						throw new Error(`Failed to load audio: ${audioResponse.status}`);
					}

					audioBlob = await audioResponse.blob();
					rawPodcastDetails = details;
				}

				// Create object URL from blob
				const objectUrl = URL.createObjectURL(audioBlob);
				objectUrlRef.current = objectUrl;
				setAudioSrc(objectUrl);

				// Parse and validate podcast details, then set transcript
				if (rawPodcastDetails) {
					const podcastDetails = parsePodcastDetails(rawPodcastDetails);
					if (podcastDetails.podcast_transcript) {
						setTranscript(podcastDetails.podcast_transcript);
					}
				}
			} finally {
				clearTimeout(timeoutId);
			}
		} catch (err) {
			console.error("Error loading podcast:", err);
			if (err instanceof DOMException && err.name === "AbortError") {
				setError("Request timed out. Please try again.");
			} else {
				setError(err instanceof Error ? err.message : "Failed to load podcast");
			}
		} finally {
			setIsLoading(false);
		}
	}, [podcastId, shareToken]);

	// Load podcast when component mounts
	useEffect(() => {
		loadPodcast();
	}, [loadPodcast]);

	if (isLoading) {
		return <AudioLoadingState title={title} />;
	}

	if (error || !audioSrc) {
		return <PodcastErrorState title={title} error={error || "Failed to load audio"} />;
	}

	const hasTranscript = transcript && transcript.length > 0;

	return (
		<div className="my-4">
			<Audio
				id={`podcast-${podcastId}`}
				src={audioSrc}
				title={title}
				durationMs={durationMs}
				className={hasTranscript ? "rounded-b-none border-b-0" : undefined}
			/>
			{hasTranscript && (
				<div className="max-w-lg overflow-hidden rounded-b-2xl border border-t-0 bg-muted/30 select-none">
					<div className="mx-5 h-px bg-border/50" />
					<Accordion type="single" collapsible className="px-5">
						<AccordionItem value="transcript" className="border-b-0">
							<AccordionTrigger className="py-3 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground hover:no-underline">
								View transcript
							</AccordionTrigger>
							<AccordionContent className="pb-0">
								<div className="space-y-2 max-h-64 sm:max-h-96 overflow-y-auto select-text">
									{transcript.map((entry, idx) => (
										<div key={`${idx}-${entry.speaker_id}`} className="text-xs sm:text-sm">
											<span className="font-medium text-primary">
												Speaker {entry.speaker_id + 1}:
											</span>{" "}
											<span className="text-muted-foreground">{entry.dialog}</span>
										</div>
									))}
								</div>
							</AccordionContent>
						</AccordionItem>
					</Accordion>
				</div>
			)}
		</div>
	);
}

/**
 * Polling component that checks podcast status and shows player when ready
 */
function PodcastStatusPoller({ podcastId, title }: { podcastId: number; title: string }) {
	const [podcastStatus, setPodcastStatus] = useState<PodcastStatusResponse | null>(null);
	const pollingRef = useRef<NodeJS.Timeout | null>(null);

	// Set active podcast state when this component mounts
	useEffect(() => {
		setActivePodcastTaskId(String(podcastId));

		// Clear when component unmounts
		return () => {
			clearActivePodcastTaskId();
		};
	}, [podcastId]);

	// Poll for podcast status
	useEffect(() => {
		const pollStatus = async () => {
			try {
				const rawResponse = await baseApiService.get<unknown>(`/api/v1/podcasts/${podcastId}`);
				const response = parsePodcastStatusResponse(rawResponse);
				if (response) {
					setPodcastStatus(response);

					// Stop polling if podcast is ready or failed
					if (response.status === "ready" || response.status === "failed") {
						if (pollingRef.current) {
							clearInterval(pollingRef.current);
							pollingRef.current = null;
						}
						clearActivePodcastTaskId();
					}
				}
			} catch (err) {
				console.error("Error polling podcast status:", err);
				// Don't stop polling on network errors, continue polling
			}
		};

		// Initial poll
		pollStatus();

		// Poll every 5 seconds
		pollingRef.current = setInterval(pollStatus, 5000);

		return () => {
			if (pollingRef.current) {
				clearInterval(pollingRef.current);
			}
		};
	}, [podcastId]);

	// Show loading state while pending or generating
	if (
		!podcastStatus ||
		podcastStatus.status === "pending" ||
		podcastStatus.status === "generating"
	) {
		return <PodcastGeneratingState title={title} />;
	}

	// Show error state
	if (podcastStatus.status === "failed") {
		return <PodcastErrorState title={title} error={podcastStatus.error || "Generation failed"} />;
	}

	// Show player when ready
	if (podcastStatus.status === "ready") {
		return <PodcastPlayer podcastId={podcastStatus.id} title={podcastStatus.title || title} />;
	}

	// Fallback
	return <PodcastErrorState title={title} error="Unexpected state" />;
}

/**
 * Generate Podcast Tool UI Component
 *
 * This component is registered with assistant-ui to render custom UI
 * when the generate_podcast tool is called by the agent.
 *
 * It polls for task completion and auto-updates when the podcast is ready.
 */
export const GeneratePodcastToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<GeneratePodcastArgs, GeneratePodcastResult>) => {
	// Guard: when rendered without props (e.g. as <GeneratePodcastToolUI /> in provider),
	// render nothing — actual rendering happens via assistant-message.tsx by_name map.
	if (!status && !result && !args) return null;

	const title = args?.podcast_title || "SurfSense Podcast";

	// Loading state - tool is still running (agent processing)
	if (status?.type === "running" || status?.type === "requires-action") {
		return <PodcastGeneratingState title={title} />;
	}

	// Incomplete/cancelled state
	if (status?.type === "incomplete") {
		if (status.reason === "cancelled") {
			return (
				<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
					<div className="px-5 pt-5 pb-4">
						<p className="text-sm font-semibold text-muted-foreground">Podcast Cancelled</p>
						<p className="text-xs text-muted-foreground mt-0.5">Podcast generation was cancelled</p>
					</div>
				</div>
			);
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

	// No result yet
	if (!result) {
		return <PodcastGeneratingState title={title} />;
	}

	// Failed result (new: "failed", legacy: "error")
	if (result.status === "failed" || result.status === "error") {
		return <PodcastErrorState title={title} error={result.error || "Generation failed"} />;
	}

	// Already generating - show simple warning, don't create another poller
	// The FIRST tool call will display the podcast when ready
	// (new: "generating", legacy: "already_generating")
	if (result.status === "generating" || result.status === "already_generating") {
		return (
			<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
				<div className="px-5 pt-5 pb-4">
					<p className="text-sm font-semibold text-foreground">Podcast already in progress</p>
					<p className="text-xs text-muted-foreground mt-0.5">
						Please wait for the current podcast to complete.
					</p>
				</div>
			</div>
		);
	}

	// Pending - poll for completion (new: "pending" with podcast_id)
	if (result.status === "pending" && result.podcast_id) {
		return <PodcastStatusPoller podcastId={result.podcast_id} title={result.title || title} />;
	}

	// Ready with podcast_id (new: "ready", legacy: "success")
	if ((result.status === "ready" || result.status === "success") && result.podcast_id) {
		return <PodcastPlayer podcastId={result.podcast_id} title={result.title || title} />;
	}

	// Legacy: old chats with Celery task_id (status: "processing" or "success" without podcast_id)
	// These can't be recovered since the old task polling endpoint no longer exists
	if (result.task_id && !result.podcast_id) {
		return (
			<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
				<div className="px-5 pt-5 pb-4">
					<p className="text-sm font-semibold text-muted-foreground">Podcast Unavailable</p>
					<p className="text-xs text-muted-foreground mt-0.5">
						This podcast was generated with an older version. Please generate a new one.
					</p>
				</div>
			</div>
		);
	}

	// Fallback - missing required data
	return <PodcastErrorState title={title} error="Missing podcast ID" />;
};

"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, MicIcon } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { Audio } from "@/components/tool-ui/audio";
import { Spinner } from "@/components/ui/spinner";
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

/**
 * Loading state component shown while podcast is being generated
 */
function PodcastGeneratingState({ title }: { title: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="relative shrink-0">
					<div className="flex size-12 sm:size-16 items-center justify-center rounded-full bg-primary/20">
						<MicIcon className="size-6 sm:size-8 text-primary" />
					</div>
					{/* Animated rings */}
					<div className="absolute inset-1 animate-ping rounded-full bg-primary/20" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-lg leading-tight">
						{title}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">
							Generating podcast. This may take a few minutes.
						</span>
					</div>
					<div className="mt-2 sm:mt-3">
						<div className="h-1 sm:h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
							<div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}

/**
 * Error state component shown when podcast generation fails
 */
function PodcastErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="flex size-12 sm:size-16 shrink-0 items-center justify-center rounded-full bg-destructive/10">
					<AlertCircleIcon className="size-6 sm:size-8 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight">
						{title}
					</h3>
					<p className="mt-1 text-destructive text-xs sm:text-sm">Failed to generate podcast</p>
					<p className="mt-1.5 sm:mt-2 text-muted-foreground text-xs sm:text-sm">{error}</p>
				</div>
			</div>
		</div>
	);
}

/**
 * Audio loading state component
 */
function AudioLoadingState({ title }: { title: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-muted/30 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="flex size-12 sm:size-16 shrink-0 items-center justify-center rounded-full bg-primary/10">
					<MicIcon className="size-6 sm:size-8 text-primary/50" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight">
						{title}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">Loading audio...</span>
					</div>
				</div>
			</div>
		</div>
	);
}

function PodcastPlayer({
	podcastId,
	title,
	description,
	durationMs,
}: {
	podcastId: number;
	title: string;
	description: string;
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

	return (
		<div className="my-4">
			<Audio
				id={`podcast-${podcastId}`}
				src={audioSrc}
				title={title}
				description={description}
				durationMs={durationMs}
				className="w-full"
			/>
			{/* Transcript section */}
			{transcript && transcript.length > 0 && (
				<details className="mt-2 sm:mt-3 rounded-lg border bg-muted/30 p-2.5 sm:p-3">
					<summary className="cursor-pointer font-medium text-muted-foreground text-xs sm:text-sm hover:text-foreground">
						View transcript ({transcript.length} entries)
					</summary>
					<div className="mt-2 sm:mt-3 space-y-2 sm:space-y-3 max-h-64 sm:max-h-96 overflow-y-auto">
						{transcript.map((entry, idx) => (
							<div key={`${idx}-${entry.speaker_id}`} className="text-xs sm:text-sm">
								<span className="font-medium text-primary">Speaker {entry.speaker_id + 1}:</span>{" "}
								<span className="text-muted-foreground">{entry.dialog}</span>
							</div>
						))}
					</div>
				</details>
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
		return (
			<PodcastPlayer
				podcastId={podcastStatus.id}
				title={podcastStatus.title || title}
				description={
					podcastStatus.transcript_entries
						? `${podcastStatus.transcript_entries} dialogue entries`
						: "SurfSense AI-generated podcast"
				}
			/>
		);
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
export const GeneratePodcastToolUI = makeAssistantToolUI<
	GeneratePodcastArgs,
	GeneratePodcastResult
>({
	toolName: "generate_podcast",
	render: function GeneratePodcastUI({ args, result, status }) {
		const title = args.podcast_title || "SurfSense Podcast";

		// Loading state - tool is still running (agent processing)
		if (status.type === "running" || status.type === "requires-action") {
			return <PodcastGeneratingState title={title} />;
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<MicIcon className="size-3.5 sm:size-4" />
							<span className="line-through">Podcast generation cancelled</span>
						</p>
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
				<div className="my-4 overflow-hidden rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 sm:p-4">
					<div className="flex items-center gap-2.5 sm:gap-3">
						<div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-full bg-amber-500/20">
							<MicIcon className="size-4 sm:size-5 text-amber-500" />
						</div>
						<div className="min-w-0">
							<p className="text-amber-600 dark:text-amber-400 text-xs sm:text-sm font-medium">
								Podcast already in progress
							</p>
							<p className="text-muted-foreground text-[10px] sm:text-xs mt-0.5">
								Please wait for the current podcast to complete.
							</p>
						</div>
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
			return (
				<PodcastPlayer
					podcastId={result.podcast_id}
					title={result.title || title}
					description={
						result.transcript_entries
							? `${result.transcript_entries} dialogue entries`
							: "SurfSense AI-generated podcast"
					}
				/>
			);
		}

		// Legacy: old chats with Celery task_id (status: "processing" or "success" without podcast_id)
		// These can't be recovered since the old task polling endpoint no longer exists
		if (result.task_id && !result.podcast_id) {
			return (
				<div className="my-4 overflow-hidden rounded-xl border border-muted p-4">
					<div className="flex items-center gap-3">
						<div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted">
							<MicIcon className="size-5 text-muted-foreground" />
						</div>
						<div>
							<p className="text-muted-foreground text-sm">
								This podcast was generated with an older version and cannot be displayed.
							</p>
							<p className="text-muted-foreground text-xs mt-0.5">
								Please generate a new podcast to listen.
							</p>
						</div>
					</div>
				</div>
			);
		}

		// Fallback - missing required data
		return <PodcastErrorState title={title} error="Missing podcast ID" />;
	},
});

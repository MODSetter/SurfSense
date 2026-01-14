"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, Loader2Icon, MicIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { Audio } from "@/components/tool-ui/audio";
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
	status: z.enum(["processing", "already_generating", "success", "error"]),
	task_id: z.string().nullish(),
	podcast_id: z.number().nullish(),
	title: z.string().nullish(),
	transcript_entries: z.number().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

const TaskStatusResponseSchema = z.object({
	status: z.enum(["processing", "success", "error"]),
	podcast_id: z.number().nullish(),
	title: z.string().nullish(),
	transcript_entries: z.number().nullish(),
	state: z.string().nullish(),
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
type TaskStatusResponse = z.infer<typeof TaskStatusResponseSchema>;
type PodcastTranscriptEntry = z.infer<typeof PodcastTranscriptEntrySchema>;

/**
 * Parse and validate task status response
 */
function parseTaskStatusResponse(data: unknown): TaskStatusResponse {
	const result = TaskStatusResponseSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid task status response:", result.error.issues);
		return { status: "error", error: "Invalid response from server" };
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
		<div className="my-4 overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 p-6">
			<div className="flex items-center gap-4">
				<div className="relative">
					<div className="flex size-16 items-center justify-center rounded-full bg-primary/20">
						<MicIcon className="size-8 text-primary" />
					</div>
					{/* Animated rings */}
					<div className="absolute inset-1 animate-ping rounded-full bg-primary/20" />
				</div>
				<div className="flex-1">
					<h3 className="font-semibold text-foreground text-lg">{title}</h3>
					<div className="mt-2 flex items-center gap-2 text-muted-foreground">
						<Loader2Icon className="size-4 animate-spin" />
						<span className="text-sm">Generating podcast. This may take a few minutes</span>
					</div>
					<div className="mt-3">
						<div className="h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
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
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-6">
			<div className="flex items-center gap-4">
				<div className="flex size-16 shrink-0 items-center justify-center rounded-full bg-destructive/10">
					<AlertCircleIcon className="size-8 text-destructive" />
				</div>
				<div className="flex-1">
					<h3 className="font-semibold text-foreground">{title}</h3>
					<p className="mt-1 text-destructive text-sm">Failed to generate podcast</p>
					<p className="mt-2 text-muted-foreground text-sm">{error}</p>
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
		<div className="my-4 overflow-hidden rounded-xl border bg-muted/30 p-6">
			<div className="flex items-center gap-4">
				<div className="flex size-16 items-center justify-center rounded-full bg-primary/10">
					<MicIcon className="size-8 text-primary/50" />
				</div>
				<div className="flex-1">
					<h3 className="font-semibold text-foreground">{title}</h3>
					<div className="mt-2 flex items-center gap-2 text-muted-foreground">
						<Loader2Icon className="size-4 animate-spin" />
						<span className="text-sm">Loading audio...</span>
					</div>
				</div>
			</div>
		</div>
	);
}

/**
 * Podcast Player Component - Fetches audio and transcript with authentication
 */
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
				// Fetch audio blob and podcast details in parallel
				const [audioResponse, rawPodcastDetails] = await Promise.all([
					authenticatedFetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcastId}/audio`,
						{ method: "GET", signal: controller.signal }
					),
					baseApiService.get<unknown>(`/api/v1/podcasts/${podcastId}`),
				]);

				if (!audioResponse.ok) {
					throw new Error(`Failed to load audio: ${audioResponse.status}`);
				}

				const audioBlob = await audioResponse.blob();

				// Create object URL from blob
				const objectUrl = URL.createObjectURL(audioBlob);
				objectUrlRef.current = objectUrl;
				setAudioSrc(objectUrl);

				// Parse and validate podcast details, then set transcript
				const podcastDetails = parsePodcastDetails(rawPodcastDetails);
				if (podcastDetails.podcast_transcript) {
					setTranscript(podcastDetails.podcast_transcript);
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
	}, [podcastId]);

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
				<details className="mt-3 rounded-lg border bg-muted/30 p-3">
					<summary className="cursor-pointer font-medium text-muted-foreground text-sm hover:text-foreground">
						View transcript ({transcript.length} entries)
					</summary>
					<div className="mt-3 space-y-3 max-h-96 overflow-y-auto">
						{transcript.map((entry, idx) => (
							<div key={`${idx}-${entry.speaker_id}`} className="text-sm">
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
 * Polling component that checks task status and shows player when complete
 */
function PodcastTaskPoller({ taskId, title }: { taskId: string; title: string }) {
	const [taskStatus, setTaskStatus] = useState<TaskStatusResponse>({ status: "processing" });
	const pollingRef = useRef<NodeJS.Timeout | null>(null);

	// Set active podcast state when this component mounts
	useEffect(() => {
		setActivePodcastTaskId(taskId);

		// Clear when component unmounts
		return () => {
			// Only clear if this task is still the active one
			clearActivePodcastTaskId();
		};
	}, [taskId]);

	// Poll for task status
	useEffect(() => {
		const pollStatus = async () => {
			try {
				const rawResponse = await baseApiService.get<unknown>(
					`/api/v1/podcasts/task/${taskId}/status`
				);
				const response = parseTaskStatusResponse(rawResponse);
				setTaskStatus(response);

				// Stop polling if task is complete or errored
				if (response.status !== "processing") {
					if (pollingRef.current) {
						clearInterval(pollingRef.current);
						pollingRef.current = null;
					}
					// Clear the active podcast state when task completes
					clearActivePodcastTaskId();
				}
			} catch (err) {
				console.error("Error polling task status:", err);
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
	}, [taskId]);

	// Show loading state while processing
	if (taskStatus.status === "processing") {
		return <PodcastGeneratingState title={title} />;
	}

	// Show error state
	if (taskStatus.status === "error") {
		return <PodcastErrorState title={title} error={taskStatus.error || "Generation failed"} />;
	}

	// Show player when complete
	if (taskStatus.status === "success" && taskStatus.podcast_id) {
		return (
			<PodcastPlayer
				podcastId={taskStatus.podcast_id}
				title={taskStatus.title || title}
				description={
					taskStatus.transcript_entries
						? `${taskStatus.transcript_entries} dialogue entries`
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
					<div className="my-4 rounded-xl border border-muted p-4 text-muted-foreground">
						<p className="flex items-center gap-2">
							<MicIcon className="size-4" />
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

		// Error result
		if (result.status === "error") {
			return <PodcastErrorState title={title} error={result.error || "Unknown error"} />;
		}

		// Already generating - show simple warning, don't create another poller
		// The FIRST tool call will display the podcast when ready
		if (result.status === "already_generating") {
			return (
				<div className="my-4 overflow-hidden rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
					<div className="flex items-center gap-3">
						<div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-amber-500/20">
							<MicIcon className="size-5 text-amber-500" />
						</div>
						<div>
							<p className="text-amber-600 dark:text-amber-400 text-sm font-medium">
								Podcast already in progress
							</p>
							<p className="text-muted-foreground text-xs mt-0.5">
								Please wait for the current podcast to complete.
							</p>
						</div>
					</div>
				</div>
			);
		}

		// Processing - poll for completion
		if (result.status === "processing" && result.task_id) {
			return <PodcastTaskPoller taskId={result.task_id} title={result.title || title} />;
		}

		// Success with podcast_id (direct result, not via polling)
		if (result.status === "success" && result.podcast_id) {
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

		// Fallback - missing required data
		return <PodcastErrorState title={title} error="Missing task ID or podcast ID" />;
	},
});

"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, Loader2Icon, MicIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Audio } from "@/components/tool-ui/audio";
import { baseApiService } from "@/lib/apis/base-api.service";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";

/**
 * Type definitions for the generate_podcast tool
 */
interface GeneratePodcastArgs {
	source_content: string;
	podcast_title?: string;
	user_prompt?: string;
}

interface GeneratePodcastResult {
	status: "processing" | "success" | "error";
	task_id?: string;
	podcast_id?: number;
	title?: string;
	transcript_entries?: number;
	message?: string;
	error?: string;
}

interface TaskStatusResponse {
	status: "processing" | "success" | "error";
	podcast_id?: number;
	title?: string;
	transcript_entries?: number;
	state?: string;
	error?: string;
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
					<div className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
				</div>
				<div className="flex-1">
					<h3 className="font-semibold text-foreground text-lg">{title}</h3>
					<div className="mt-2 flex items-center gap-2 text-muted-foreground">
						<Loader2Icon className="size-4 animate-spin" />
						<span className="text-sm">Generating podcast... This may take a few minutes</span>
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
 * Podcast Player Component - Fetches audio with authentication
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

	// Fetch audio with authentication
	const loadAudio = useCallback(async () => {
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
				// Fetch audio blob with authentication
				const response = await podcastsApiService.loadPodcast({
					request: { id: podcastId },
					controller,
				});

				// Create object URL from blob
				const objectUrl = URL.createObjectURL(response);
				objectUrlRef.current = objectUrl;
				setAudioSrc(objectUrl);
			} finally {
				clearTimeout(timeoutId);
			}
		} catch (err) {
			console.error("Error loading podcast audio:", err);
			if (err instanceof DOMException && err.name === "AbortError") {
				setError("Request timed out. Please try again.");
			} else {
				setError(err instanceof Error ? err.message : "Failed to load audio");
			}
		} finally {
			setIsLoading(false);
		}
	}, [podcastId]);

	// Load audio when component mounts
	useEffect(() => {
		loadAudio();
	}, [loadAudio]);

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
		</div>
	);
}

/**
 * Polling component that checks task status and shows player when complete
 */
function PodcastTaskPoller({
	taskId,
	title,
}: {
	taskId: string;
	title: string;
}) {
	const [taskStatus, setTaskStatus] = useState<TaskStatusResponse>({ status: "processing" });
	const [pollCount, setPollCount] = useState(0);
	const pollingRef = useRef<NodeJS.Timeout | null>(null);

	// Poll for task status
	useEffect(() => {
		const pollStatus = async () => {
			try {
				const response = await baseApiService.get<TaskStatusResponse>(
					`/api/v1/podcasts/task/${taskId}/status`
				);
				setTaskStatus(response);

				// Stop polling if task is complete or errored
				if (response.status !== "processing") {
					if (pollingRef.current) {
						clearInterval(pollingRef.current);
						pollingRef.current = null;
					}
				}
			} catch (err) {
				console.error("Error polling task status:", err);
				// Don't stop polling on network errors, just increment count
			}
			setPollCount((prev) => prev + 1);
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

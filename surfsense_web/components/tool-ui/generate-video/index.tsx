"use client";

import { makeAssistantToolUI, useAssistantState } from "@assistant-ui/react";
import { Player } from "@remotion/player";
import { AlertTriangleIcon, VideoIcon } from "lucide-react";
import { Component, type ReactNode, useEffect, useRef, useState } from "react";
import { fetchAgentVideo } from "./api";
import { VideoErrorState } from "./components/VideoErrorState";
import { VideoLoadingState } from "./components/VideoLoadingState";
import { useVideoLifecycle } from "./hooks/useVideoLifecycle";
import { BACKEND_URL } from "@/lib/env-config";
import type { GenerateVideoArgs, GenerateVideoResult } from "./types";
import { MAX_ATTEMPTS } from "./types";

class PlayerErrorBoundary extends Component<
	{ topic: string; children: ReactNode },
	{ error: string | null }
> {
	state = { error: null };
	static getDerivedStateFromError(err: unknown) {
		return { error: err instanceof Error ? err.message : "Render error" };
	}
	render() {
		if (this.state.error) {
			return <VideoErrorState title={this.props.topic} error={this.state.error} />;
		}
		return this.props.children;
	}
}

function parseMessageId(assistantUiMessageId: string | undefined): number | null {
	if (!assistantUiMessageId) return null;
	const match = assistantUiMessageId.match(/^msg-(\d+)$/);
	return match ? Number.parseInt(match[1], 10) : null;
}

/** Hook managing the agent-rendered MP4 path: idle → fetching → ready | failed */
function useAgentVideo(result: GenerateVideoResult | null) {
	const [phase, setPhase] = useState<"idle" | "fetching" | "ready" | "failed">("idle");
	const [mp4Url, setMp4Url] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);
	const controllerRef = useRef<AbortController | null>(null);

	useEffect(() => {
		if (!result) return;
		// If the tool result already contains a pre-rendered URL, use it immediately.
		if (result.mp4_url) {
			setMp4Url(`${BACKEND_URL}${result.mp4_url}`);
			setPhase("ready");
			return;
		}
		// Otherwise kick off the agent pipeline.
		const controller = new AbortController();
		controllerRef.current = controller;
		setPhase("fetching");

		fetchAgentVideo(
			result.search_space_id,
			result.thread_id,
			result.topic,
			result.source_content,
			controller.signal,
		)
			.then((url) => {
				setMp4Url(`${BACKEND_URL}${url}`);
				setPhase("ready");
			})
			.catch((err: unknown) => {
				if (err instanceof Error && err.name === "AbortError") return;
				setError(err instanceof Error ? err.message : String(err));
				setPhase("failed");
			});

		return () => controller.abort();
	}, [result]);

	return { phase, mp4Url, error };
}

/** Native HTML5 video player for agent-rendered MP4s */
function AgentVideoPlayer({ url, topic }: { url: string; topic: string }) {
	return (
		<video
			src={url}
			controls
			autoPlay
			loop
			playsInline
			style={{ width: "100%", borderRadius: 8, backgroundColor: "#0a0a0f" }}
			aria-label={topic}
		>
			Your browser does not support the video tag.
		</video>
	);
}

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status, toolCallId }) {
		const topic = args.topic || "Video";
		const messageId = parseMessageId(useAssistantState(({ message }) => message?.id));
		const [useAgent, setUseAgent] = useState(false);

		// JIT path
		const { phase, attempt, component, durationInFrames, finalError, runtimeWarning, generationId, playerRef } =
			useVideoLifecycle(result ?? null, toolCallId, messageId);

		// Agent path
		const agentVideo = useAgentVideo(useAgent ? (result ?? null) : null);

		if (status.type === "running" || status.type === "requires-action") {
			return <VideoLoadingState topic={topic} attempt={0} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<VideoIcon className="size-3.5 sm:size-4" />
							<span className="line-through">Video generation cancelled</span>
						</p>
					</div>
				);
			}
			const errMsg = typeof status.error === "string" ? status.error : "An error occurred";
			return <VideoErrorState title={topic} error={errMsg} />;
		}

		// ── Mode toggle (shown once the JIT player is ready) ──────────────────
		const modeToggle = (phase === "success" || agentVideo.phase === "ready" || agentVideo.phase === "fetching" || agentVideo.phase === "failed") && (
			<div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
				<span className={!useAgent ? "font-semibold text-foreground" : ""}>JIT</span>
				<button
					type="button"
					onClick={() => setUseAgent((v) => !v)}
					className="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:bg-primary"
					data-state={useAgent ? "checked" : "unchecked"}
					aria-label="Toggle agent rendering"
				>
					<span
						className="pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
						data-state={useAgent ? "checked" : "unchecked"}
					/>
				</button>
				<span className={useAgent ? "font-semibold text-foreground" : ""}>Agent (rendered MP4)</span>
			</div>
		);

		// ── Agent path ─────────────────────────────────────────────────────────
		if (useAgent) {
			if (agentVideo.phase === "fetching") {
				return (
					<div className="my-4">
						{modeToggle}
						<VideoLoadingState topic={topic} attempt={0} />
					</div>
				);
			}
			if (agentVideo.phase === "failed") {
				return (
					<div className="my-4">
						{modeToggle}
						<VideoErrorState title={topic} error={agentVideo.error || "Agent rendering failed"} />
					</div>
				);
			}
			if (agentVideo.phase === "ready" && agentVideo.mp4Url) {
				return (
					<div className="my-4">
						{modeToggle}
						<AgentVideoPlayer url={agentVideo.mp4Url} topic={topic} />
					</div>
				);
			}
		}

		// ── JIT path (default) ─────────────────────────────────────────────────
		if (phase === "idle" || phase === "generating") {
			return (
				<div>
					{runtimeWarning && (
						<div className="mb-2 flex items-center gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-300">
							<AlertTriangleIcon className="size-3.5 shrink-0" />
							{runtimeWarning}
						</div>
					)}
					<VideoLoadingState topic={topic} attempt={attempt} />
				</div>
			);
		}

		if (phase === "failed") {
			return (
				<VideoErrorState
					title={topic}
					error={finalError || `Generation failed after ${MAX_ATTEMPTS} attempts`}
				/>
			);
		}

		if (phase === "success" && component) {
			return (
				<div className="my-4">
					{modeToggle}
					<PlayerErrorBoundary topic={topic}>
						<Player
							ref={playerRef}
							key={generationId}
							component={component}
							durationInFrames={durationInFrames}
							fps={30}
							compositionWidth={1920}
							compositionHeight={1080}
							style={{ width: "100%", borderRadius: 8 }}
							controls
							autoPlay
							loop
						/>
					</PlayerErrorBoundary>
				</div>
			);
		}

		return <VideoErrorState title={topic} error="Missing video component" />;
	},
});

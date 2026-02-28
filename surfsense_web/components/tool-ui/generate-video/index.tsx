"use client";

import { makeAssistantToolUI, useAssistantState } from "@assistant-ui/react";
import { Player } from "@remotion/player";
import { AlertTriangleIcon, VideoIcon } from "lucide-react";
import { Component, type ReactNode } from "react";
import { VideoErrorState } from "./components/VideoErrorState";
import { VideoLoadingState } from "./components/VideoLoadingState";
import { useVideoLifecycle } from "./hooks/useVideoLifecycle";
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

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status, toolCallId }) {
		const topic = args.topic || "Video";
		const messageId = parseMessageId(useAssistantState(({ message }) => message?.id));

		const { phase, attempt, component, durationInFrames, finalError, runtimeWarning, generationId, playerRef } =
			useVideoLifecycle(result ?? null, toolCallId, messageId);

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

"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Player } from "@remotion/player";
import { VideoIcon } from "lucide-react";
import { VideoErrorState } from "./components/VideoErrorState";
import { VideoLoadingState } from "./components/VideoLoadingState";
import { useVideoLifecycle } from "./hooks/useVideoLifecycle";
import { GenerateVideoArgsSchema, GenerateVideoResultSchema } from "./types";
import type { GenerateVideoArgs, GenerateVideoResult } from "./types";

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status }) {
		const topic = args.topic || "Video";

		const { phase, attempt, component, durationInFrames, finalError, playerRef } =
			useVideoLifecycle(result ?? null);

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
			return <VideoLoadingState topic={topic} attempt={attempt} />;
		}

		if (phase === "failed") {
			return (
				<VideoErrorState
					title={topic}
					error={finalError || "Generation failed after 3 attempts"}
				/>
			);
		}

		if (phase === "success" && component) {
			return (
				<div className="my-4">
					<Player
						ref={playerRef}
						key={component.toString()}
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
				</div>
			);
		}

		return <VideoErrorState title={topic} error="Missing video component" />;
	},
});

export { GenerateVideoArgsSchema, GenerateVideoResultSchema };

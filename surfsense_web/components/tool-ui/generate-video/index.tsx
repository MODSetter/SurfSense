"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { VideoIcon } from "lucide-react";
import { BACKEND_URL } from "@/lib/env-config";
import { VideoErrorState } from "./components/VideoErrorState";
import { VideoLoadingState } from "./components/VideoLoadingState";
import type { GenerateVideoArgs, GenerateVideoResult } from "./types";

function VideoPlayer({ url, topic }: { url: string; topic: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<video
				src={url}
				controls
				autoPlay
				loop
				playsInline
				className="w-full bg-black"
				style={{ borderRadius: 8 }}
				aria-label={topic}
			>
				Your browser does not support the video tag.
			</video>
		</div>
	);
}

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status }) {
		const topic = args.topic || "Video";

		if (status.type === "running" || status.type === "requires-action") {
			return <VideoLoadingState topic={topic} />;
		}

		if (status.type === "incomplete") {
			const errorMessage =
				status.reason === "cancelled"
					? "Video generation cancelled"
					: typeof status.error === "string"
						? status.error
						: "An error occurred";

			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<VideoIcon className="size-3.5 sm:size-4" />
							<span className="line-through">{errorMessage}</span>
						</p>
					</div>
				);
			}

			return <VideoErrorState title={topic} error={errorMessage} />;
		}

		if (!result) {
			return <VideoLoadingState topic={topic} />;
		}

		if (result.status === "error") {
			return <VideoErrorState title={topic} error={result.error || "Video generation failed"} />;
		}

		if (result.status === "success" && result.mp4_url) {
			const fullUrl = `${BACKEND_URL}${result.mp4_url}`;
			return <VideoPlayer url={fullUrl} topic={topic} />;
		}

		return <VideoErrorState title={topic} error="No video URL received" />;
	},
});

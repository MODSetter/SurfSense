"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { DownloadIcon, VideoIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { VideoErrorState } from "./components/VideoErrorState";
import { VideoLoadingState } from "./components/VideoLoadingState";
import type { GenerateVideoArgs, GenerateVideoResult } from "./types";
import {
	generateVideoScript,
	renderVideo,
	getRenderProgress,
	type VideoInput,
	type ProgressResponse,
} from "@/lib/apis/video-api.service";

type PipelineState =
	| { step: "idle" }
	| { step: "generating_script" }
	| { step: "rendering"; progress: number }
	| { step: "done"; url: string; size: number }
	| { step: "error"; message: string };

function VideoPlayer({ url, topic, size }: { url: string; topic: string; size?: number }) {
	const sizeLabel = size ? `${(size / 1_048_576).toFixed(1)} MB` : null;

	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<video
				src={url}
				controls
				autoPlay
				playsInline
				className="w-full bg-black"
				style={{ borderRadius: "8px 8px 0 0" }}
				aria-label={topic}
			>
				Your browser does not support the video tag.
			</video>
			<div className="flex items-center justify-between px-4 py-2.5 sm:px-5 sm:py-3 bg-muted/30">
				<div className="flex items-center gap-2 min-w-0">
					<VideoIcon className="size-3.5 sm:size-4 text-muted-foreground shrink-0" />
					<span className="text-xs sm:text-sm text-muted-foreground truncate">{topic}</span>
					{sizeLabel && (
						<span className="text-[10px] sm:text-xs text-muted-foreground/60 shrink-0">
							({sizeLabel})
						</span>
					)}
				</div>
				<a
					href={url}
					download={`${topic.replace(/[^a-zA-Z0-9]/g, "_")}.mp4`}
					className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors shrink-0"
				>
					<DownloadIcon className="size-3.5" />
					<span className="hidden sm:inline">Download</span>
				</a>
			</div>
		</div>
	);
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function VideoGenerationPipeline({
	topic,
	sourceContent,
	searchSpaceId,
}: {
	topic: string;
	sourceContent: string;
	searchSpaceId: number;
}) {
	const [state, setState] = useState<PipelineState>({ step: "idle" });
	const startedRef = useRef(false);

	const run = useCallback(async () => {
		if (startedRef.current) return;
		startedRef.current = true;

		try {
			setState({ step: "generating_script" });
			const videoInput: VideoInput = await generateVideoScript(
				searchSpaceId,
				topic,
				sourceContent,
			);

			setState({ step: "rendering", progress: 0 });
			const { renderId, bucketName } = await renderVideo(videoInput);

			let pending = true;
			while (pending) {
				const result: ProgressResponse = await getRenderProgress(renderId, bucketName);
				switch (result.type) {
					case "error":
						setState({ step: "error", message: result.message });
						pending = false;
						break;
					case "done":
						setState({ step: "done", url: result.url, size: result.size });
						pending = false;
						break;
					case "progress":
						setState({ step: "rendering", progress: result.progress });
						await wait(1500);
						break;
				}
			}
		} catch (err) {
			setState({
				step: "error",
				message: err instanceof Error ? err.message : "Video generation failed",
			});
		}
	}, [topic, sourceContent, searchSpaceId]);

	useEffect(() => {
		run();
	}, [run]);

	switch (state.step) {
		case "idle":
		case "generating_script":
			return <VideoLoadingState topic={topic} step="generating_script" />;
		case "rendering":
			return <VideoLoadingState topic={topic} step="rendering" progress={state.progress} />;
		case "done":
			return <VideoPlayer url={state.url} topic={topic} size={state.size} />;
		case "error":
			return <VideoErrorState title={topic} error={state.message} />;
	}
}

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status }) {
		const topic = args.topic || "Video";

		if (status.type === "running" || status.type === "requires-action") {
			return <VideoLoadingState topic={topic} step="running" />;
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
			return <VideoLoadingState topic={topic} step="running" />;
		}

		if (result.status === "error") {
			return <VideoErrorState title={topic} error={result.error || "Video generation failed"} />;
		}

		if (
			result.status === "success" &&
			result.source_content &&
			result.search_space_id
		) {
			return (
				<VideoGenerationPipeline
					topic={result.topic || topic}
					sourceContent={result.source_content}
					searchSpaceId={result.search_space_id}
				/>
			);
		}

		return <VideoErrorState title={topic} error="Missing video generation data" />;
	},
});

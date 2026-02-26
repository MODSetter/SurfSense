"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { VideoIcon } from "lucide-react";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { VideoPreview } from "@/components/tool-ui/video/video-preview";

const GenerateVideoArgsSchema = z.object({
	topic: z.string(),
	source_content: z.string(),
});

const GenerateVideoResultSchema = z.object({
	status: z.enum(["ready", "failed"]),
	code: z.string().nullish(),
	title: z.string().nullish(),
	duration_frames: z.number().nullish(),
	error: z.string().nullish(),
});

type GenerateVideoArgs = z.infer<typeof GenerateVideoArgsSchema>;
type GenerateVideoResult = z.infer<typeof GenerateVideoResultSchema>;

function VideoGeneratingState({ topic }: { topic: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<VideoIcon className="size-4 sm:size-6 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{topic}
					</h3>
					<TextShimmerLoader text="Composing visual content" size="sm" />
				</div>
			</div>
		</div>
	);
}

function VideoErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-muted/60">
					<VideoIcon className="size-4 sm:size-6 text-muted-foreground" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-muted-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{title}
					</h3>
					<p className="text-muted-foreground/60 text-[11px] sm:text-xs mt-0.5 truncate">{error}</p>
				</div>
			</div>
		</div>
	);
}

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status }) {
		const topic = args.topic || "Video";

		if (status.type === "running" || status.type === "requires-action") {
			return <VideoGeneratingState topic={topic} />;
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
			if (status.reason === "error") {
				return (
					<VideoErrorState
						title={topic}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		if (!result) {
			return <VideoGeneratingState topic={topic} />;
		}

		if (result.status === "failed") {
			return (
				<VideoErrorState
					title={result.title || topic}
					error={result.error || "Generation failed"}
				/>
			);
		}

		if (result.status === "ready" && result.code) {
			return (
				<div className="my-4">
					<VideoPreview code={result.code} />
				</div>
			);
		}

		return <VideoErrorState title={topic} error="Missing video code" />;
	},
});

"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { ImageIcon } from "lucide-react";

const DisplayImageArgsSchema = z.object({
	url: z.string().optional(),
	alt: z.string().optional(),
	caption: z.string().optional(),
});

const DisplayImageResultSchema = z.object({
	url: z.string().optional(),
	alt: z.string().optional(),
	caption: z.string().optional(),
}).passthrough();

type DisplayImageArgs = z.infer<typeof DisplayImageArgsSchema>;
type DisplayImageResult = z.infer<typeof DisplayImageResultSchema>;

export const DisplayImageToolUI = makeAssistantToolUI<DisplayImageArgs, DisplayImageResult>({
	toolName: "display_image",
	render: ({ args, result, status }) => {
		const isLoading = status.type === "running";
		const imageUrl = result?.url ?? args?.url;
		const altText = result?.alt ?? args?.alt ?? "Image";
		const caption = result?.caption ?? args?.caption;

		if (isLoading) {
			return (
				<div className="my-3 flex items-center gap-2 rounded-lg border bg-card/60 px-4 py-3">
					<ImageIcon className="size-4 animate-pulse text-muted-foreground" />
					<span className="text-sm text-muted-foreground">Loading image...</span>
				</div>
			);
		}

		if (!imageUrl) return null;

		return (
			<div className="my-3 rounded-lg border bg-card/60 overflow-hidden">
				<img
					src={imageUrl}
					alt={altText}
					className="w-full max-h-96 object-contain"
				/>
				{caption && (
					<p className="px-4 py-2 text-sm text-muted-foreground">{caption}</p>
				)}
			</div>
		);
	},
});

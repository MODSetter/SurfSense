"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { ExternalLinkIcon, Loader2Icon } from "lucide-react";

const LinkPreviewArgsSchema = z.object({
	url: z.string(),
}).passthrough();

const LinkPreviewResultSchema = z.object({
	url: z.string().optional(),
	title: z.string().optional(),
	description: z.string().optional(),
	image: z.string().optional(),
	favicon: z.string().optional(),
	error: z.string().optional(),
}).passthrough();

type LinkPreviewArgs = z.infer<typeof LinkPreviewArgsSchema>;
type LinkPreviewResult = z.infer<typeof LinkPreviewResultSchema>;

export const LinkPreviewToolUI = makeAssistantToolUI<LinkPreviewArgs, LinkPreviewResult>({
	toolName: "link_preview",
	render: ({ args, result, status }) => {
		const isLoading = status.type === "running";
		const url = result?.url ?? args?.url;

		if (isLoading) {
			return (
				<div className="my-2 flex items-center gap-2 rounded-lg border bg-card/60 px-4 py-3">
					<Loader2Icon className="size-4 animate-spin text-muted-foreground" />
					<span className="text-sm text-muted-foreground">Loading preview...</span>
				</div>
			);
		}

		if (result?.error || !url) return null;

		return (
			<a
				href={url}
				target="_blank"
				rel="noopener noreferrer"
				className="my-2 flex items-start gap-3 rounded-lg border bg-card/60 p-3 hover:bg-card transition-colors no-underline"
			>
				{result?.favicon && (
					<img src={result.favicon} alt="" className="size-4 mt-0.5 shrink-0" />
				)}
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium truncate">{result?.title ?? url}</p>
					{result?.description && (
						<p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{result.description}</p>
					)}
					<p className="text-xs text-muted-foreground truncate mt-1">{url}</p>
				</div>
				<ExternalLinkIcon className="size-3.5 shrink-0 text-muted-foreground mt-0.5" />
			</a>
		);
	},
});

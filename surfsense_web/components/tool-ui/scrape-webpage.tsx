"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { GlobeIcon, Loader2Icon, CheckCircle2Icon, XCircleIcon } from "lucide-react";

const ScrapeWebpageArgsSchema = z.object({
	url: z.string(),
}).passthrough();

const ScrapeWebpageResultSchema = z.object({
	url: z.string().optional(),
	title: z.string().optional(),
	content: z.string().optional(),
	error: z.string().optional(),
	success: z.boolean().optional(),
}).passthrough();

type ScrapeWebpageArgs = z.infer<typeof ScrapeWebpageArgsSchema>;
type ScrapeWebpageResult = z.infer<typeof ScrapeWebpageResultSchema>;

export const ScrapeWebpageToolUI = makeAssistantToolUI<ScrapeWebpageArgs, ScrapeWebpageResult>({
	toolName: "scrape_webpage",
	render: ({ args, result, status }) => {
		const isLoading = status.type === "running";
		const url = result?.url ?? args?.url;
		const hasError = result?.error || result?.success === false;
		const isSuccess = result?.success !== false && !result?.error && status.type === "complete";

		return (
			<div className="my-3 flex items-center gap-3 rounded-lg border bg-card/60 px-4 py-3">
				<div className="flex size-8 items-center justify-center rounded-full bg-primary/10 shrink-0">
					{isLoading ? (
						<Loader2Icon className="size-4 animate-spin text-primary" />
					) : hasError ? (
						<XCircleIcon className="size-4 text-destructive" />
					) : (
						<GlobeIcon className="size-4 text-primary" />
					)}
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium">
						{isLoading ? "Scraping webpage..." : hasError ? "Failed to scrape" : "Scraped webpage"}
					</p>
					{url && (
						<p className="text-xs text-muted-foreground truncate">{url}</p>
					)}
					{hasError && result?.error && (
						<p className="text-xs text-destructive mt-0.5">{result.error}</p>
					)}
				</div>
				{isSuccess && <CheckCircle2Icon className="size-4 text-green-500 shrink-0" />}
			</div>
		);
	},
});

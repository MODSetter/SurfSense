"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, FileTextIcon, GlobeIcon } from "lucide-react";
import { z } from "zod";
import { Citation } from "@/components/tool-ui/citation";

const ScrapeWebpageArgsSchema = z.object({
	url: z.string(),
	max_length: z.number().nullish(),
});

const ScrapeWebpageResultSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	kind: z.literal("article"),
	href: z.string(),
	title: z.string(),
	description: z.string().nullish(),
	content: z.string().nullish(),
	domain: z.string().nullish(),
	author: z.string().nullish(),
	date: z.string().nullish(),
	word_count: z.number().nullish(),
	was_truncated: z.boolean().nullish(),
	crawler_type: z.string().nullish(),
	error: z.string().nullish(),
});

type ScrapeWebpageArgs = z.infer<typeof ScrapeWebpageArgsSchema>;
type ScrapeWebpageResult = z.infer<typeof ScrapeWebpageResultSchema>;

function ScrapeErrorState({ url, error }: { url: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 max-w-md">
			<div className="flex items-center gap-4">
				<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-6 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="font-medium text-destructive text-sm">Failed to scrape webpage</p>
					<p className="text-muted-foreground text-xs mt-0.5 truncate">{url}</p>
					<p className="text-muted-foreground text-xs mt-1">{error}</p>
				</div>
			</div>
		</div>
	);
}

function ScrapeCancelledState({ url }: { url: string }) {
	return (
		<div className="my-4 rounded-xl border border-muted p-4 text-muted-foreground max-w-md">
			<p className="flex items-center gap-2">
				<FileTextIcon className="size-4" />
				<span className="line-through truncate">Scraping: {url}</span>
			</p>
		</div>
	);
}

function ScrapeLoadingState({ url }: { url: string }) {
	return (
		<div className="my-4 max-w-md animate-pulse rounded-xl border bg-card p-4">
			<div className="flex flex-col gap-2">
				<div className="flex items-center gap-1.5">
					<GlobeIcon className="size-3.5 text-muted-foreground" />
					<div className="h-3 w-24 rounded bg-muted" />
				</div>
				<div className="h-4 w-3/4 rounded bg-muted" />
			</div>
			<p className="text-xs text-muted-foreground mt-3 truncate">{url}</p>
		</div>
	);
}

function buildFaviconUrl(domain: string): string {
	return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
}

function ParsedCitation({ result }: { result: ScrapeWebpageResult }) {
	return (
		<Citation
			id={result.id}
			href={result.href}
			title={result.title}
			snippet={result.description ?? undefined}
			domain={result.domain ?? undefined}
			favicon={result.domain ? buildFaviconUrl(result.domain) : undefined}
			author={result.author ?? undefined}
			publishedAt={result.date ?? undefined}
			type="article"
		/>
	);
}

export const ScrapeWebpageToolUI = makeAssistantToolUI<ScrapeWebpageArgs, ScrapeWebpageResult>({
	toolName: "scrape_webpage",
	render: function ScrapeWebpageUI({ args, result, status }) {
		const url = args.url || "Unknown URL";

		if (status.type === "running" || status.type === "requires-action") {
			return <ScrapeLoadingState url={url} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return <ScrapeCancelledState url={url} />;
			}
			if (status.reason === "error") {
				return (
					<ScrapeErrorState
						url={url}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		if (!result) {
			return <ScrapeLoadingState url={url} />;
		}

		if (result.error) {
			return <ScrapeErrorState url={url} error={result.error} />;
		}

		return (
			<div className="my-4">
				<ParsedCitation result={result} />
			</div>
		);
	},
});

export {
	ScrapeWebpageArgsSchema,
	ScrapeWebpageResultSchema,
	type ScrapeWebpageArgs,
	type ScrapeWebpageResult,
};

"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, FileTextIcon } from "lucide-react";
import { z } from "zod";
import {
	Article,
	ArticleErrorBoundary,
	ArticleLoading,
	parseSerializableArticle,
} from "@/components/tool-ui/article";

// ============================================================================
// Zod Schemas
// ============================================================================

/**
 * Schema for scrape_webpage tool arguments
 */
const ScrapeWebpageArgsSchema = z.object({
	url: z.string(),
	max_length: z.number().nullish(),
});

/**
 * Schema for scrape_webpage tool result
 */
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

// ============================================================================
// Types
// ============================================================================

type ScrapeWebpageArgs = z.infer<typeof ScrapeWebpageArgsSchema>;
type ScrapeWebpageResult = z.infer<typeof ScrapeWebpageResultSchema>;

/**
 * Error state component shown when webpage scraping fails
 */
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

/**
 * Cancelled state component
 */
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

/**
 * Parsed Article component with error handling
 */
function ParsedArticle({ result }: { result: unknown }) {
	const article = parseSerializableArticle(result);

	return (
		<Article
			{...article}
			maxWidth="480px"
			responseActions={[{ id: "open", label: "Open Source", variant: "default" }]}
			onResponseAction={(id) => {
				if (id === "open" && article.href) {
					window.open(article.href, "_blank", "noopener,noreferrer");
				}
			}}
		/>
	);
}

/**
 * Scrape Webpage Tool UI Component
 *
 * This component is registered with assistant-ui to render an article card
 * when the scrape_webpage tool is called by the agent.
 *
 * It displays scraped webpage content including:
 * - Title and description
 * - Author and date (if available)
 * - Word count
 * - Link to original source
 */
export const ScrapeWebpageToolUI = makeAssistantToolUI<ScrapeWebpageArgs, ScrapeWebpageResult>({
	toolName: "scrape_webpage",
	render: function ScrapeWebpageUI({ args, result, status }) {
		const url = args.url || "Unknown URL";

		// Loading state - tool is still running
		if (status.type === "running" || status.type === "requires-action") {
			return (
				<div className="my-4">
					<ArticleLoading title={`Scraping ${url}...`} />
				</div>
			);
		}

		// Incomplete/cancelled state
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

		// No result yet
		if (!result) {
			return (
				<div className="my-4">
					<ArticleLoading title={`Extracting content from ${url}...`} />
				</div>
			);
		}

		// Error result from the tool
		if (result.error) {
			return <ScrapeErrorState url={url} error={result.error} />;
		}

		// Success - render the article card
		return (
			<div className="my-4">
				<ArticleErrorBoundary>
					<ParsedArticle result={result} />
				</ArticleErrorBoundary>
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

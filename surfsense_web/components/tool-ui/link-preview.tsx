"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { AlertCircleIcon, ExternalLinkIcon, LinkIcon } from "lucide-react";
import { z } from "zod";
import {
	MediaCard,
	MediaCardErrorBoundary,
	MediaCardLoading,
	parseSerializableMediaCard,
	type SerializableMediaCard,
} from "@/components/tool-ui/media-card";

// ============================================================================
// Zod Schemas
// ============================================================================

/**
 * Schema for link_preview tool arguments
 */
const LinkPreviewArgsSchema = z.object({
	url: z.string(),
	title: z.string().nullish(),
});

/**
 * Schema for link_preview tool result
 */
const LinkPreviewResultSchema = z.object({
	id: z.string(),
	assetId: z.string(),
	kind: z.literal("link"),
	href: z.string(),
	title: z.string(),
	description: z.string().nullish(),
	thumb: z.string().nullish(),
	domain: z.string().nullish(),
	error: z.string().nullish(),
});

// ============================================================================
// Types
// ============================================================================

type LinkPreviewArgs = z.infer<typeof LinkPreviewArgsSchema>;
type LinkPreviewResult = z.infer<typeof LinkPreviewResultSchema>;

/**
 * Error state component shown when link preview fails
 */
function LinkPreviewErrorState({ url, error }: { url: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 max-w-md">
			<div className="flex items-center gap-4">
				<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-6 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="font-medium text-destructive text-sm">Failed to load preview</p>
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
function LinkPreviewCancelledState({ url }: { url: string }) {
	return (
		<div className="my-4 rounded-xl border border-muted p-4 text-muted-foreground max-w-md">
			<p className="flex items-center gap-2">
				<LinkIcon className="size-4" />
				<span className="line-through truncate">Preview: {url}</span>
			</p>
		</div>
	);
}

/**
 * Parsed MediaCard component with error handling
 */
function ParsedMediaCard({ result }: { result: unknown }) {
	const card = parseSerializableMediaCard(result);

	return (
		<MediaCard
			{...card}
			maxWidth="420px"
			responseActions={[{ id: "open", label: "Open", variant: "default" }]}
			onResponseAction={(id) => {
				if (id === "open" && card.href) {
					window.open(card.href, "_blank", "noopener,noreferrer");
				}
			}}
		/>
	);
}

/**
 * Link Preview Tool UI Component
 *
 * This component is registered with assistant-ui to render a rich
 * link preview card when the link_preview tool is called by the agent.
 *
 * It displays website metadata including:
 * - Title and description
 * - Thumbnail/Open Graph image
 * - Domain name
 * - Clickable link to open in new tab
 */
export const LinkPreviewToolUI = makeAssistantToolUI<LinkPreviewArgs, LinkPreviewResult>({
	toolName: "link_preview",
	render: function LinkPreviewUI({ args, result, status }) {
		const url = args.url || "Unknown URL";

		// Loading state - tool is still running
		if (status.type === "running" || status.type === "requires-action") {
			return (
				<div className="my-4">
					<MediaCardLoading title={`Loading preview for ${url}...`} />
				</div>
			);
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return <LinkPreviewCancelledState url={url} />;
			}
			if (status.reason === "error") {
				return (
					<LinkPreviewErrorState
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
					<MediaCardLoading title={`Fetching metadata for ${url}...`} />
				</div>
			);
		}

		// Error result from the tool
		if (result.error) {
			return <LinkPreviewErrorState url={url} error={result.error} />;
		}

		// Success - render the media card
		return (
			<div className="my-4">
				<MediaCardErrorBoundary>
					<ParsedMediaCard result={result} />
				</MediaCardErrorBoundary>
			</div>
		);
	},
});

// ============================================================================
// Multi Link Preview Schemas
// ============================================================================

/**
 * Schema for multi_link_preview tool arguments
 */
const MultiLinkPreviewArgsSchema = z.object({
	urls: z.array(z.string()),
});

/**
 * Schema for error items in multi_link_preview result
 */
const MultiLinkPreviewErrorSchema = z.object({
	url: z.string(),
	error: z.string(),
});

/**
 * Schema for multi_link_preview tool result
 */
const MultiLinkPreviewResultSchema = z.object({
	previews: z.array(LinkPreviewResultSchema),
	errors: z.array(MultiLinkPreviewErrorSchema).nullish(),
});

type MultiLinkPreviewArgs = z.infer<typeof MultiLinkPreviewArgsSchema>;
type MultiLinkPreviewResult = z.infer<typeof MultiLinkPreviewResultSchema>;

export const MultiLinkPreviewToolUI = makeAssistantToolUI<
	MultiLinkPreviewArgs,
	MultiLinkPreviewResult
>({
	toolName: "multi_link_preview",
	render: function MultiLinkPreviewUI({ args, result, status }) {
		const urls = args.urls || [];

		// Loading state
		if (status.type === "running" || status.type === "requires-action") {
			return (
				<div className="my-4 grid gap-4 sm:grid-cols-2">
					{urls.slice(0, 4).map((url, index) => (
						<MediaCardLoading key={`loading-${url}-${index}`} title="Loading..." />
					))}
				</div>
			);
		}

		// Incomplete state
		if (status.type === "incomplete") {
			return (
				<div className="my-4 text-muted-foreground text-sm">
					<p className="flex items-center gap-2">
						<LinkIcon className="size-4" />
						<span>Link previews cancelled</span>
					</p>
				</div>
			);
		}

		// No result
		if (!result || !result.previews) {
			return null;
		}

		// Render grid of previews
		return (
			<div className="my-4 grid gap-4 sm:grid-cols-2">
				{result.previews.map((preview) => (
					<MediaCardErrorBoundary key={preview.id}>
						<ParsedMediaCard result={preview} />
					</MediaCardErrorBoundary>
				))}
				{result.errors?.map((err) => (
					<LinkPreviewErrorState key={err.url} url={err.url} error={err.error} />
				))}
			</div>
		);
	},
});

export {
	LinkPreviewArgsSchema,
	LinkPreviewResultSchema,
	MultiLinkPreviewArgsSchema,
	MultiLinkPreviewResultSchema,
	type LinkPreviewArgs,
	type LinkPreviewResult,
	type MultiLinkPreviewArgs,
	type MultiLinkPreviewResult,
};

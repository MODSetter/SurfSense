"use client";

import { useQuery } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { ExternalLink, FileText } from "lucide-react";
import dynamic from "next/dynamic";
import type { FC } from "react";
import { useState } from "react";
import { openCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { useCitationMetadata } from "@/components/assistant-ui/citation-metadata-context";
import { CitationPanelContent } from "@/components/citation-panel/citation-panel";
import { Citation } from "@/components/tool-ui/citation";
import { CitationHoverPopover } from "@/components/tool-ui/citation/citation-hover-popover";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/use-media-query";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// Lazily load MarkdownViewer here to break the static import cycle:
// `markdown-viewer.tsx` → `citation-renderer.tsx` → `inline-citation.tsx`
// would otherwise pull `markdown-viewer.tsx` back in at module-init time.
// Only `SurfsenseDocCitation` (popover body) ever renders this viewer, so
// the lazy boundary is invisible to most call paths.
const MarkdownViewer = dynamic(
	() => import("@/components/markdown-viewer").then((m) => m.MarkdownViewer),
	{ ssr: false, loading: () => <Spinner size="xs" /> }
);

interface InlineCitationProps {
	chunkId: number;
	isDocsChunk?: boolean;
}

/**
 * Inline citation badge for knowledge-base chunks (numeric chunk IDs) and
 * Surfsense documentation chunks (`isDocsChunk`). Negative chunk IDs render as
 * a static "doc" pill (anonymous/synthetic uploads).
 *
 * Numeric KB chunks: clicking opens the citation panel in the right
 * sidebar (alongside the chat — does not replace it). The panel shows
 * the cited chunk surrounded by adjacent chunks (via the API's
 * `chunk_window`), with the cited one highlighted and an option to
 * expand the window or jump into the full document via the editor panel.
 *
 * Surfsense docs chunks: rendered as a hover-controlled shadcn Popover that
 * lazily fetches and previews the cited chunk inline, since those docs aren't
 * indexed into the user's search space and have no tab to open.
 */
export const InlineCitation: FC<InlineCitationProps> = ({ chunkId, isDocsChunk = false }) => {
	if (chunkId < 0) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>
					<span
						className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
						role="note"
					>
						<FileText className="size-3" />
						doc
					</span>
				</TooltipTrigger>
				<TooltipContent>Uploaded document</TooltipContent>
			</Tooltip>
		);
	}

	if (isDocsChunk) {
		return <SurfsenseDocCitation chunkId={chunkId} />;
	}

	return <NumericChunkCitation chunkId={chunkId} />;
};

const NumericChunkCitation: FC<{ chunkId: number }> = ({ chunkId }) => {
	const isTouchLike = useMediaQuery("(hover: none), (pointer: coarse)");
	const openCitationPanel = useSetAtom(openCitationPanelAtom);
	const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false);

	const handleClick = () => {
		if (isTouchLike) {
			setMobilePreviewOpen(true);
			return;
		}
		openCitationPanel({ chunkId });
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleClick}
				className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
				title={`View source chunk #${chunkId}`}
				aria-label={`View cited chunk ${chunkId}`}
			>
				{chunkId}
			</Button>
			<Drawer open={mobilePreviewOpen} onOpenChange={setMobilePreviewOpen} shouldScaleBackground={false}>
				<DrawerContent
					className="h-[85vh] max-h-[85vh] z-80 overflow-hidden"
					overlayClassName="z-80"
				>
					<DrawerHandle />
					<DrawerHeader className="pb-0">
						<DrawerTitle>Citation</DrawerTitle>
					</DrawerHeader>
					<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
						<CitationPanelContent chunkId={chunkId} showHeader={false} />
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
};

const SurfsenseDocCitation: FC<{ chunkId: number }> = ({ chunkId }) => {
	const isTouchLike = useMediaQuery("(hover: none), (pointer: coarse)");
	const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false);
	const docQuery = useSurfsenseDocPreviewQuery(chunkId, mobilePreviewOpen);

	const handleMobileClick = () => {
		setMobilePreviewOpen(true);
	};

	return (
		<>
			<CitationHoverPopover
				id={`doc-${chunkId}`}
				contentClassName="w-96 max-w-[calc(100vw-2rem)] p-0"
				align="start"
				trigger={(hoverProps) => (
					<Button
						type="button"
						variant="ghost"
						size={null}
						onClick={isTouchLike ? handleMobileClick : undefined}
						className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
						aria-label={`Show Surfsense documentation chunk ${chunkId}`}
						title="Surfsense documentation"
						{...hoverProps}
					>
						<FileText className="size-3" />
						doc
					</Button>
				)}
			>
				<SurfsenseDocPreview chunkId={chunkId} />
			</CitationHoverPopover>
			<Drawer open={mobilePreviewOpen} onOpenChange={setMobilePreviewOpen} shouldScaleBackground={false}>
				<DrawerContent
					className="max-h-[85vh] z-80"
					overlayClassName="z-80"
				>
					<DrawerHandle />
					<DrawerHeader className="pb-0">
						<DrawerTitle>Surfsense documentation</DrawerTitle>
					</DrawerHeader>
					<SurfsenseDocPreviewContent chunkId={chunkId} query={docQuery} contentClassName="max-h-[60vh]" />
				</DrawerContent>
			</Drawer>
		</>
	);
};

function useSurfsenseDocPreviewQuery(chunkId: number, enabled = true) {
	return useQuery({
		queryKey: cacheKeys.documents.byChunk(`doc-${chunkId}`),
		queryFn: () => documentsApiService.getSurfsenseDocByChunk(chunkId),
		staleTime: 5 * 60 * 1000,
		enabled,
	});
}

type SurfsenseDocPreviewQuery = ReturnType<typeof useSurfsenseDocPreviewQuery>;

const SurfsenseDocPreview: FC<{ chunkId: number }> = ({ chunkId }) => {
	const query = useSurfsenseDocPreviewQuery(chunkId);

	return <SurfsenseDocPreviewContent chunkId={chunkId} query={query} />;
};

const SurfsenseDocPreviewContent: FC<{
	chunkId: number;
	query: SurfsenseDocPreviewQuery;
	contentClassName?: string;
}> = ({ chunkId, query, contentClassName = "max-h-72" }) => {
	const { data, isLoading, error } = query;

	const citedChunk = data?.chunks.find((c) => c.id === chunkId) ?? data?.chunks[0];

	return (
		<>
			<div className="flex items-center justify-between gap-2 border-b px-3 py-2">
				<div className="min-w-0">
					<p className="truncate text-sm font-medium">
						{data?.title ?? "Surfsense documentation"}
					</p>
					<p className="text-[11px] text-muted-foreground">Chunk #{chunkId}</p>
				</div>
				{data?.public_url && (
					<a
						href={data.public_url}
						target="_blank"
						rel="noopener noreferrer"
						className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/10"
					>
						<ExternalLink className="size-3" />
						Open
					</a>
				)}
			</div>
			<div className={`${contentClassName} overflow-auto px-3 py-2 text-sm`}>
				{isLoading && (
					<div className="flex items-center gap-2 py-4 text-muted-foreground">
						<Spinner size="xs" />
						<span className="text-xs">Loading…</span>
					</div>
				)}
				{error && (
					<p className="py-4 text-xs text-destructive">
						{error instanceof Error ? error.message : "Failed to load chunk"}
					</p>
				)}
				{!isLoading && !error && citedChunk?.content && (
					<MarkdownViewer content={citedChunk.content} maxLength={1500} enableCitations />
				)}
				{!isLoading && !error && !citedChunk?.content && (
					<p className="py-4 text-xs text-muted-foreground">No content available.</p>
				)}
			</div>
		</>
	);
};

import { tryGetHostname } from "@/lib/url";

interface UrlCitationProps {
	url: string;
}

/**
 * Inline citation for live web search results (URL-based chunk IDs).
 * Renders a compact chip with favicon + domain and a hover popover showing the
 * page title and snippet (extracted deterministically from web_search tool results).
 */
export const UrlCitation: FC<UrlCitationProps> = ({ url }) => {
	const domain = tryGetHostname(url) ?? url;
	const meta = useCitationMetadata(url);

	return (
		<Citation
			id={`url-cite-${url}`}
			href={url}
			title={meta?.title || domain}
			snippet={meta?.snippet}
			domain={domain}
			favicon={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
			variant="inline"
			type="webpage"
		/>
	);
};

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { ExternalLink, FileText } from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { pendingChunkHighlightAtom } from "@/atoms/document-viewer/pending-chunk-highlight.atom";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { useCitationMetadata } from "@/components/assistant-ui/citation-metadata-context";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Citation } from "@/components/tool-ui/citation";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface InlineCitationProps {
	chunkId: number;
	isDocsChunk?: boolean;
}

const POPOVER_HOVER_CLOSE_DELAY_MS = 150;

/**
 * Inline citation badge for knowledge-base chunks (numeric chunk IDs) and
 * Surfsense documentation chunks (`isDocsChunk`). Negative chunk IDs render as
 * a static "doc" pill (anonymous/synthetic uploads).
 *
 * Numeric KB chunks: clicking resolves the parent document via
 * `getDocumentByChunk`, opens the document in the right side panel (alongside
 * the chat — does not replace it), and stages the cited chunk text in
 * `pendingChunkHighlightAtom` so `EditorPanelContent` can scroll to and softly
 * highlight it inside the rendered markdown.
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
						className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-primary/10 px-1.5 text-[11px] font-medium text-primary align-baseline shadow-sm"
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
	const queryClient = useQueryClient();
	const setPendingHighlight = useSetAtom(pendingChunkHighlightAtom);
	const openEditorPanel = useSetAtom(openEditorPanelAtom);
	const [resolving, setResolving] = useState(false);

	const handleClick = useCallback(async () => {
		if (resolving) return;
		setResolving(true);
		console.log("[citation:click] start", { chunkId });
		try {
			const data = await queryClient.fetchQuery({
				// Local key with explicit window. The shared `cacheKeys.documents.byChunk`
				// is window-agnostic (latent footgun); namespace the call to avoid
				// reusing a different-window cached result.
				queryKey: ["documents", "by-chunk", chunkId, "w0"] as const,
				queryFn: () =>
					documentsApiService.getDocumentByChunk({ chunk_id: chunkId, chunk_window: 0 }),
				staleTime: 5 * 60 * 1000,
			});
			const cited = data.chunks.find((c) => c.id === chunkId) ?? data.chunks[0];
			console.log("[citation:click] fetched doc-by-chunk", {
				docId: data.id,
				docTitle: data.title,
				chunksReturned: data.chunks.length,
				citedChunkId: cited?.id,
				citedChunkContentLen: cited?.content?.length ?? 0,
				citedChunkPreview:
					cited?.content && cited.content.length > 120
						? `${cited.content.slice(0, 120)}…(+${cited.content.length - 120})`
						: (cited?.content ?? ""),
			});
			// Stage the highlight BEFORE opening the panel so `EditorPanelContent`
			// already sees the pending intent on its very first render — avoids a
			// "fetch → render → no-pending → next-tick render with pending" race.
			setPendingHighlight({
				documentId: data.id,
				chunkId,
				chunkText: cited?.content ?? "",
			});
			openEditorPanel({
				documentId: data.id,
				searchSpaceId: data.search_space_id,
				title: data.title,
			});
			console.log("[citation:click] staged highlight + opened editor panel", {
				documentId: data.id,
			});
		} catch (err) {
			console.warn("[citation:click] failed", err);
			toast.error(err instanceof Error ? err.message : "Couldn't open cited document");
		} finally {
			setResolving(false);
		}
	}, [chunkId, openEditorPanel, queryClient, resolving, setPendingHighlight]);

	return (
		<button
			type="button"
			onClick={handleClick}
			disabled={resolving}
			className="ml-0.5 inline-flex h-5 min-w-5 cursor-pointer items-center justify-center rounded-md bg-muted/60 px-1.5 text-[11px] font-medium text-muted-foreground align-baseline shadow-sm transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none disabled:cursor-progress disabled:opacity-70"
			title={`View source chunk #${chunkId}`}
			aria-label={`Jump to cited chunk ${chunkId}`}
		>
			{resolving ? <Spinner size="xs" /> : chunkId}
		</button>
	);
};

const SurfsenseDocCitation: FC<{ chunkId: number }> = ({ chunkId }) => {
	const [open, setOpen] = useState(false);
	const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const cancelClose = useCallback(() => {
		if (closeTimerRef.current) {
			clearTimeout(closeTimerRef.current);
			closeTimerRef.current = null;
		}
	}, []);

	const scheduleClose = useCallback(() => {
		cancelClose();
		closeTimerRef.current = setTimeout(() => {
			setOpen(false);
			closeTimerRef.current = null;
		}, POPOVER_HOVER_CLOSE_DELAY_MS);
	}, [cancelClose]);

	useEffect(() => () => cancelClose(), [cancelClose]);

	const { data, isLoading, error } = useQuery({
		queryKey: cacheKeys.documents.byChunk(`doc-${chunkId}`),
		queryFn: () => documentsApiService.getSurfsenseDocByChunk(chunkId),
		enabled: open,
		staleTime: 5 * 60 * 1000,
	});

	const citedChunk = data?.chunks.find((c) => c.id === chunkId) ?? data?.chunks[0];

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<button
					type="button"
					onClick={() => setOpen((prev) => !prev)}
					onMouseEnter={() => {
						cancelClose();
						setOpen(true);
					}}
					onMouseLeave={scheduleClose}
					onFocus={() => {
						cancelClose();
						setOpen(true);
					}}
					onBlur={scheduleClose}
					className="ml-0.5 inline-flex h-5 min-w-5 cursor-pointer items-center justify-center gap-0.5 rounded-md bg-primary/10 px-1.5 text-[11px] font-medium text-primary align-baseline shadow-sm transition-colors hover:bg-primary/15 focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none"
					aria-label={`Show Surfsense documentation chunk ${chunkId}`}
					title="Surfsense documentation"
				>
					<FileText className="size-3" />
					doc
				</button>
			</PopoverTrigger>
			<PopoverContent
				className="w-96 max-w-[calc(100vw-2rem)] p-0"
				align="start"
				sideOffset={6}
				onMouseEnter={cancelClose}
				onMouseLeave={scheduleClose}
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				<div className="flex items-center justify-between gap-2 border-b px-3 py-2">
					<div className="min-w-0">
						<p className="truncate text-sm font-medium">
							{data?.title ?? "Surfsense documentation"}
						</p>
						<p className="text-[11px] text-muted-foreground">Chunk #{chunkId}</p>
					</div>
					{data?.source && (
						<a
							href={data.source}
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/10"
						>
							<ExternalLink className="size-3" />
							Open
						</a>
					)}
				</div>
				<div className="max-h-72 overflow-auto px-3 py-2 text-sm">
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
						<MarkdownViewer content={citedChunk.content} maxLength={1500} />
					)}
					{!isLoading && !error && !citedChunk?.content && (
						<p className="py-4 text-xs text-muted-foreground">No content available.</p>
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
};

function extractDomain(url: string): string {
	try {
		const hostname = new URL(url).hostname;
		return hostname.replace(/^www\./, "");
	} catch {
		return url;
	}
}

interface UrlCitationProps {
	url: string;
}

/**
 * Inline citation for live web search results (URL-based chunk IDs).
 * Renders a compact chip with favicon + domain and a hover popover showing the
 * page title and snippet (extracted deterministically from web_search tool results).
 */
export const UrlCitation: FC<UrlCitationProps> = ({ url }) => {
	const domain = extractDomain(url);
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

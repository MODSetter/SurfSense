"use client";

import { useQuery } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { ChevronDown, ChevronUp, ExternalLink, XIcon } from "lucide-react";
import type { FC } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { documentsApiService } from "@/lib/apis/documents-api.service";

const DEFAULT_CHUNK_WINDOW = 5;
const EXPANDED_CHUNK_WINDOW = 50;

interface CitationPanelContentProps {
	chunkId: number;
	onClose?: () => void;
}

/**
 * Right-panel citation viewer. Shows the cited chunk surrounded by
 * adjacent chunks (±N chunks via the API's `chunk_window` parameter),
 * with the cited one visually highlighted and auto-scrolled into view.
 * The window can be expanded to a wider range, or the user can jump to
 * the full document via the editor panel.
 */
export const CitationPanelContent: FC<CitationPanelContentProps> = ({ chunkId, onClose }) => {
	const openEditorPanel = useSetAtom(openEditorPanelAtom);
	const [expanded, setExpanded] = useState(false);

	useEffect(() => {
		setExpanded(false);
	}, []);

	const chunkWindow = expanded ? EXPANDED_CHUNK_WINDOW : DEFAULT_CHUNK_WINDOW;

	const { data, isLoading, error } = useQuery({
		queryKey: ["citation-panel", chunkId, chunkWindow] as const,
		queryFn: () =>
			documentsApiService.getDocumentByChunk({
				chunk_id: chunkId,
				chunk_window: chunkWindow,
			}),
		staleTime: 5 * 60 * 1000,
	});

	const cited = useMemo(() => data?.chunks.find((c) => c.id === chunkId) ?? null, [data, chunkId]);

	const totalChunks = data?.total_chunks ?? data?.chunks.length ?? 0;
	const startIndex = data?.chunk_start_index ?? 0;
	const citedIndexInWindow = data
		? Math.max(
				0,
				data.chunks.findIndex((c) => c.id === chunkId)
			)
		: 0;
	const shownAbove = citedIndexInWindow;
	const shownBelow = data ? Math.max(0, data.chunks.length - 1 - citedIndexInWindow) : 0;
	const hasMoreAbove = startIndex > 0;
	const hasMoreBelow = data ? startIndex + data.chunks.length < totalChunks : false;

	// Scroll the cited chunk into view inside the panel's scroll container
	// (not the page). We anchor the scroll to the panel's scroll element
	// so opening the citation doesn't yank the chat scroll on the left.
	const scrollContainerRef = useRef<HTMLDivElement | null>(null);
	const citedRef = useRef<HTMLDivElement | null>(null);
	useEffect(() => {
		if (!cited) return;
		const id = requestAnimationFrame(() => {
			const container = scrollContainerRef.current;
			const target = citedRef.current;
			if (!container || !target) return;
			const containerRect = container.getBoundingClientRect();
			const targetRect = target.getBoundingClientRect();
			const offset = targetRect.top - containerRect.top + container.scrollTop;
			container.scrollTo({
				top: Math.max(0, offset - 16),
				behavior: "smooth",
			});
		});
		return () => cancelAnimationFrame(id);
	}, [cited]);

	const handleOpenFullDocument = () => {
		if (!data) return;
		openEditorPanel({
			documentId: data.id,
			searchSpaceId: data.search_space_id,
			title: data.title,
		});
	};

	return (
		<>
			<div className="shrink-0 border-b">
				<div className="flex h-14 items-center justify-between px-4">
					<h2 className="text-lg font-medium text-muted-foreground select-none">Citation</h2>
					<div className="flex items-center gap-1 shrink-0">
						{onClose && (
							<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
								<XIcon className="size-4" />
								<span className="sr-only">Close citation panel</span>
							</Button>
						)}
					</div>
				</div>
				<div className="flex h-10 items-center justify-between gap-2 border-t px-4">
					<div className="min-w-0 flex flex-1 items-center gap-2">
						<p className="truncate text-sm text-muted-foreground">
							{data?.title ?? (isLoading ? "Loading…" : `Chunk #${chunkId}`)}
						</p>
					</div>
					<div className="flex items-center gap-2 shrink-0 text-[11px] text-muted-foreground">
						<span>Chunk #{chunkId}</span>
						{totalChunks > 0 && <span>· {totalChunks} chunks</span>}
					</div>
				</div>
			</div>

			<div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-5 py-4">
				{isLoading && (
					<div className="flex items-center gap-2 py-8 text-muted-foreground">
						<Spinner size="sm" />
						<span className="text-sm">Loading citation…</span>
					</div>
				)}

				{error && (
					<p className="py-8 text-sm text-destructive">
						{error instanceof Error ? error.message : "Failed to load citation"}
					</p>
				)}

				{!isLoading && !error && data && (
					<>
						{hasMoreAbove && (
							<p className="mb-3 text-center text-[11px] text-muted-foreground">
								… {startIndex} earlier chunk{startIndex === 1 ? "" : "s"} not shown
							</p>
						)}
						<div className="space-y-3">
							{data.chunks.map((chunk) => {
								const isCited = chunk.id === chunkId;
								return (
									<div
										key={chunk.id}
										ref={isCited ? citedRef : null}
										data-cited={isCited || undefined}
										className={
											isCited
												? "rounded-md border-2 border-primary bg-primary/5 px-4 py-3 shadow-sm"
												: "rounded-md border border-border/40 bg-muted/20 px-4 py-3 opacity-70 transition-opacity hover:opacity-100"
										}
									>
										<div className="mb-1.5 flex items-center justify-between">
											<span
												className={
													isCited
														? "text-[11px] font-semibold text-primary"
														: "text-[11px] font-medium text-muted-foreground"
												}
											>
												{isCited ? "Cited chunk" : `Chunk #${chunk.id}`}
											</span>
											{isCited && (
												<span className="text-[11px] text-muted-foreground">#{chunk.id}</span>
											)}
										</div>
										<div className="text-sm">
											<MarkdownViewer content={chunk.content} enableCitations />
										</div>
									</div>
								);
							})}
						</div>
						{hasMoreBelow && (
							<p className="mt-3 text-center text-[11px] text-muted-foreground">
								… {totalChunks - (startIndex + data.chunks.length)} later chunk
								{totalChunks - (startIndex + data.chunks.length) === 1 ? "" : "s"} not shown
							</p>
						)}
					</>
				)}
			</div>

			{!isLoading && !error && data && (
				<div className="shrink-0 flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3">
					<div className="text-[11px] text-muted-foreground">
						Showing {shownAbove} above · cited · {shownBelow} below
					</div>
					<div className="flex items-center gap-2">
						{(hasMoreAbove || hasMoreBelow) && !expanded && (
							<Button
								variant="ghost"
								size="sm"
								className="h-8 text-xs"
								onClick={() => setExpanded(true)}
							>
								<ChevronDown className="mr-1 size-3.5" />
								More context
							</Button>
						)}
						{expanded && (
							<Button
								variant="ghost"
								size="sm"
								className="h-8 text-xs"
								onClick={() => setExpanded(false)}
							>
								<ChevronUp className="mr-1 size-3.5" />
								Less
							</Button>
						)}
						<Button
							variant="default"
							size="sm"
							className="h-8 text-xs"
							onClick={handleOpenFullDocument}
						>
							<ExternalLink className="mr-1 size-3.5" />
							Open full document
						</Button>
					</div>
				</div>
			)}
		</>
	);
};

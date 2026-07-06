"use client";

import { useQuery } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { XIcon } from "lucide-react";
import type { FC } from "react";
import { useEffect, useMemo, useRef } from "react";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { documentsApiService } from "@/lib/apis/documents-api.service";

const DEFAULT_CHUNK_WINDOW = 5;

interface CitationPanelContentProps {
	chunkId: number;
	onClose?: () => void;
	showHeader?: boolean;
}

/**
 * Right-panel citation viewer. Shows the cited chunk surrounded by
 * adjacent chunks (±N chunks via the API's `chunk_window` parameter),
 * with the cited one visually highlighted and auto-scrolled into view.
 * The user can jump to the full document via the editor panel.
 */
export const CitationPanelContent: FC<CitationPanelContentProps> = ({
	chunkId,
	onClose,
	showHeader = true,
}) => {
	const openEditorPanel = useSetAtom(openEditorPanelAtom);

	const chunkWindow = DEFAULT_CHUNK_WINDOW;

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
			searchSpaceId: data.workspace_id,
			title: data.title,
		});
	};

	return (
		<>
			<div className="shrink-0">
				{showHeader && (
					<div className="shrink-0 flex h-12 items-center justify-between px-3 border-b">
						<h2 className="select-none text-lg font-semibold">Citation</h2>
						<div className="flex items-center gap-1 shrink-0">
							{onClose && (
								<Button
									variant="ghost"
									size="icon"
									onClick={onClose}
									className="h-8 w-8 rounded-full shrink-0 text-muted-foreground hover:text-accent-foreground"
								>
									<XIcon className="h-4 w-4" />
									<span className="sr-only">Close citation panel</span>
								</Button>
							)}
						</div>
					</div>
				)}
				<div className="grid h-10 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-4">
					<div className="min-w-0 flex flex-1 items-center gap-2">
						<p className="truncate text-sm text-muted-foreground">
							{data?.title ?? (isLoading ? "Loading…" : `Chunk #${chunkId}`)}
						</p>
					</div>
					<div className="flex items-center gap-3 shrink-0 text-[11px] text-muted-foreground">
						{totalChunks > 0 && <span>{totalChunks} chunks</span>}
						{!isLoading && !error && data && (
							<Button
								variant="default"
								size="sm"
								className="h-6 px-1.5 text-[11px]"
								onClick={handleOpenFullDocument}
							>
								Open
							</Button>
						)}
					</div>
				</div>
			</div>

			<div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-5 py-4">
				{isLoading && (
					<div className="flex min-h-full items-center justify-center text-muted-foreground">
						<Spinner size="md" />
					</div>
				)}

				{error && (
					<div className="flex min-h-full items-center justify-center text-center">
						<p className="text-sm text-destructive">
							{error instanceof Error ? error.message : "Failed to load citation"}
						</p>
					</div>
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
												? "rounded-md border-2 border-primary bg-accent px-4 py-3 shadow-sm"
												: "rounded-md bg-accent px-4 py-3 opacity-70 transition-opacity hover:opacity-100"
										}
									>
										<div className="mb-1.5 flex items-center justify-between">
											<span
												className={
													isCited
														? "text-[11px] text-muted-foreground"
														: "text-[11px] font-medium text-muted-foreground"
												}
											>
												Chunk #{chunk.id}
											</span>
											{isCited && (
												<span className="text-[11px] font-semibold text-primary">Cited chunk</span>
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
		</>
	);
};

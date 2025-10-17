"use client";

import { ChevronDown, ChevronUp, ExternalLink, Loader2 } from "lucide-react";
import type React from "react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useDocumentByChunk } from "@/hooks/use-document-by-chunk";
import { cn } from "@/lib/utils";

interface SourceDetailSheetProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	chunkId: number;
	sourceType: string;
	title: string;
	description?: string;
	url?: string;
	children?: ReactNode;
}

const formatDocumentType = (type: string) => {
	return type
		.split("_")
		.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
		.join(" ");
};

export function SourceDetailSheet({
	open,
	onOpenChange,
	chunkId,
	sourceType,
	title,
	description,
	url,
	children,
}: SourceDetailSheetProps) {
	const { document, loading, error, fetchDocumentByChunk, clearDocument } = useDocumentByChunk();
	const chunksContainerRef = useRef<HTMLDivElement>(null);
	const highlightedChunkRef = useRef<HTMLDivElement>(null);
	const [summaryOpen, setSummaryOpen] = useState(false);

	// Check if this is a source type that should render directly from node
	const isDirectRenderSource =
		sourceType === "TAVILY_API" ||
		sourceType === "LINKUP_API" ||
		sourceType === "SEARXNG_API" ||
		sourceType === "BAIDU_SEARCH_API";

	useEffect(() => {
		if (open && chunkId && !isDirectRenderSource) {
			fetchDocumentByChunk(chunkId);
		} else if (!open && !isDirectRenderSource) {
			clearDocument();
		}
	}, [open, chunkId, isDirectRenderSource, fetchDocumentByChunk, clearDocument]);

	useEffect(() => {
		// Scroll to highlighted chunk when document loads
		if (document && highlightedChunkRef.current && chunksContainerRef.current) {
			setTimeout(() => {
				highlightedChunkRef.current?.scrollIntoView({
					behavior: "smooth",
					block: "start",
				});
			}, 100);
		}
	}, [document]);

	const handleUrlClick = (e: React.MouseEvent, clickUrl: string) => {
		e.preventDefault();
		e.stopPropagation();
		window.open(clickUrl, "_blank", "noopener,noreferrer");
	};

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			{children}
			<SheetContent side="right" className="w-full sm:max-w-5xl lg:max-w-7xl">
				<SheetHeader className="px-6 py-4 border-b">
					<SheetTitle className="flex items-center gap-3 text-lg">
						{getConnectorIcon(sourceType)}
						{document?.title || title}
					</SheetTitle>
					<SheetDescription className="text-base mt-2">
						{document
							? formatDocumentType(document.document_type)
							: sourceType && formatDocumentType(sourceType)}
					</SheetDescription>
				</SheetHeader>

				{!isDirectRenderSource && loading && (
					<div className="flex items-center justify-center h-64 px-6">
						<Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
					</div>
				)}

				{!isDirectRenderSource && error && (
					<div className="flex items-center justify-center h-64 px-6">
						<p className="text-sm text-destructive">{error}</p>
					</div>
				)}

				{/* Direct render for web search providers */}
				{isDirectRenderSource && (
					<ScrollArea className="h-[calc(100vh-10rem)]">
						<div className="px-6 py-4">
							{/* External Link */}
							{url && (
								<div className="mb-8">
									<Button
										size="default"
										variant="outline"
										onClick={(e) => handleUrlClick(e, url)}
										className="w-full py-3"
									>
										<ExternalLink className="mr-2 h-4 w-4" />
										Open in Browser
									</Button>
								</div>
							)}

							{/* Source Information */}
							<div className="mb-8 p-6 bg-muted/50 rounded-lg border">
								<h3 className="text-base font-semibold mb-4">Source Information</h3>
								<div className="text-sm text-muted-foreground mb-3 font-medium">
									{title || "Untitled"}
								</div>
								<div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
									{description || "No content available"}
								</div>
							</div>
						</div>
					</ScrollArea>
				)}

				{/* API-fetched document content */}
				{!isDirectRenderSource && document && (
					<ScrollArea className="h-[calc(100vh-10rem)]">
						<div className="px-6 py-4">
							{/* Document Metadata */}
							{document.document_metadata && Object.keys(document.document_metadata).length > 0 && (
								<div className="mb-8 p-6 bg-muted/50 rounded-lg border">
									<h3 className="text-base font-semibold mb-4">Document Information</h3>
									<dl className="grid grid-cols-1 gap-3 text-sm">
										{Object.entries(document.document_metadata).map(([key, value]) => (
											<div key={key} className="flex gap-3">
												<dt className="font-medium text-muted-foreground capitalize min-w-0 flex-shrink-0">
													{key.replace(/_/g, " ")}:
												</dt>
												<dd className="text-foreground break-words">{String(value)}</dd>
											</div>
										))}
									</dl>
								</div>
							)}

							{/* External Link */}
							{url && (
								<div className="mb-8">
									<Button
										size="default"
										variant="outline"
										onClick={(e) => handleUrlClick(e, url)}
										className="w-full py-3"
									>
										<ExternalLink className="mr-2 h-4 w-4" />
										Open in Browser
									</Button>
								</div>
							)}

							{/* Chunks */}
							<div className="space-y-6" ref={chunksContainerRef}>
								<div className="mb-4">
									{/* Header row: header and button side by side */}
									<div className="flex flex-row items-center gap-4">
										<h3 className="text-base font-semibold mb-2 md:mb-0">Document Content</h3>
										{document.content && (
											<Collapsible open={summaryOpen} onOpenChange={setSummaryOpen}>
												<CollapsibleTrigger className="flex items-center gap-2 py-2 px-3 font-medium border rounded-md bg-muted hover:bg-muted/80 transition-colors">
													<span>Summary</span>
													{summaryOpen ? (
														<ChevronUp className="h-4 w-4 transition-transform" />
													) : (
														<ChevronDown className="h-4 w-4 transition-transform" />
													)}
												</CollapsibleTrigger>
											</Collapsible>
										)}
									</div>
									{/* Expanded summary content: always full width, below the row */}
									{document.content && (
										<Collapsible open={summaryOpen} onOpenChange={setSummaryOpen}>
											<CollapsibleContent className="pt-2 w-full">
												<div className="p-6 bg-muted/50 rounded-lg border">
													<MarkdownViewer content={document.content} />
												</div>
											</CollapsibleContent>
										</Collapsible>
									)}
								</div>

								{document.chunks.map((chunk, idx) => (
									<div
										key={chunk.id}
										ref={chunk.id === chunkId ? highlightedChunkRef : null}
										className={cn(
											"p-6 rounded-lg border transition-all duration-300",
											chunk.id === chunkId
												? "bg-primary/10 border-primary shadow-md ring-1 ring-primary/20"
												: "bg-background border-border hover:bg-muted/50 hover:border-muted-foreground/20"
										)}
									>
										<div className="mb-4 flex items-center justify-between">
											<span className="text-sm font-medium text-muted-foreground">
												Chunk {idx + 1} of {document.chunks.length}
											</span>
											{chunk.id === chunkId && (
												<span className="text-sm font-medium text-primary bg-primary/10 px-3 py-1 rounded-full">
													Referenced Chunk
												</span>
											)}
										</div>
										<div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
											<MarkdownViewer content={chunk.content} className="max-w-fit" />
										</div>
									</div>
								))}
							</div>
						</div>
					</ScrollArea>
				)}
			</SheetContent>
		</Sheet>
	);
}

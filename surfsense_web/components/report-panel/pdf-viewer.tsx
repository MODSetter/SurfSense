"use client";

import { ChevronLeftIcon, ChevronRightIcon, ZoomInIcon, ZoomOutIcon } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getAuthHeaders } from "@/lib/auth-utils";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url
).toString();

interface PdfViewerProps {
	pdfUrl: string;
}

const ZOOM_STEP = 0.15;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;

export function PdfViewer({ pdfUrl }: PdfViewerProps) {
	const [numPages, setNumPages] = useState<number>(0);
	const [pageNumber, setPageNumber] = useState(1);
	const [scale, setScale] = useState(1);
	const [loadError, setLoadError] = useState<string | null>(null);
	const containerRef = useRef<HTMLDivElement>(null);
	const documentOptionsRef = useRef({ httpHeaders: getAuthHeaders() });

	const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
		setNumPages(numPages);
		setPageNumber(1);
		setLoadError(null);
	}, []);

	const onDocumentLoadError = useCallback((error: Error) => {
		setLoadError(error.message || "Failed to load PDF");
	}, []);

	const goToPrevPage = useCallback(() => {
		setPageNumber((prev) => Math.max(1, prev - 1));
	}, []);

	const goToNextPage = useCallback(() => {
		setPageNumber((prev) => Math.min(numPages, prev + 1));
	}, [numPages]);

	const zoomIn = useCallback(() => {
		setScale((prev) => Math.min(MAX_ZOOM, prev + ZOOM_STEP));
	}, []);

	const zoomOut = useCallback(() => {
		setScale((prev) => Math.max(MIN_ZOOM, prev - ZOOM_STEP));
	}, []);

	if (loadError) {
		return (
			<div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
				<p className="font-medium text-foreground">Failed to load resume preview</p>
				<p className="text-sm text-muted-foreground">{loadError}</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full">
			{/* Controls bar */}
			{numPages > 0 && (
				<div className="flex items-center justify-center gap-2 px-4 py-2 border-b bg-sidebar shrink-0">
					{numPages > 1 && (
						<>
							<Button
								variant="ghost"
								size="icon"
								onClick={goToPrevPage}
								disabled={pageNumber <= 1}
								className="size-7"
							>
								<ChevronLeftIcon className="size-4" />
							</Button>
							<span className="text-xs text-muted-foreground tabular-nums min-w-[60px] text-center">
								{pageNumber} / {numPages}
							</span>
							<Button
								variant="ghost"
								size="icon"
								onClick={goToNextPage}
								disabled={pageNumber >= numPages}
								className="size-7"
							>
								<ChevronRightIcon className="size-4" />
							</Button>
							<div className="w-px h-4 bg-border mx-1" />
						</>
					)}
					<Button variant="ghost" size="icon" onClick={zoomOut} disabled={scale <= MIN_ZOOM} className="size-7">
						<ZoomOutIcon className="size-4" />
					</Button>
					<span className="text-xs text-muted-foreground tabular-nums min-w-[40px] text-center">
						{Math.round(scale * 100)}%
					</span>
					<Button variant="ghost" size="icon" onClick={zoomIn} disabled={scale >= MAX_ZOOM} className="size-7">
						<ZoomInIcon className="size-4" />
					</Button>
				</div>
			)}

			{/* PDF content */}
		<div ref={containerRef} className="flex-1 overflow-auto flex justify-center bg-sidebar p-0">
			<Document
				file={pdfUrl}
				onLoadSuccess={onDocumentLoadSuccess}
				onLoadError={onDocumentLoadError}
				options={documentOptionsRef.current}
			loading={
				<div className="flex items-center justify-center h-64 text-sidebar-foreground">
					<Spinner size="md" />
				</div>
			}
				>
					<Page
						pageNumber={pageNumber}
						scale={scale}
						renderTextLayer
						renderAnnotationLayer
						className="shadow-lg"
						error={
							<div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
								Failed to render page {pageNumber}
							</div>
						}
					/>
				</Document>
			</div>
		</div>
	);
}

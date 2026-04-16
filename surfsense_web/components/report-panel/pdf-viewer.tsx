"use client";

import { ZoomInIcon, ZoomOutIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getAuthHeaders } from "@/lib/auth-utils";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url
).toString();

interface PdfViewerProps {
	pdfUrl: string;
	isPublic?: boolean;
}

const ZOOM_STEP = 0.15;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const PAGE_GAP = 12;

export function PdfViewer({ pdfUrl, isPublic = false }: PdfViewerProps) {
	const [numPages, setNumPages] = useState(0);
	const [scale, setScale] = useState(1);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [currentPage, setCurrentPage] = useState(1);

	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const pagesContainerRef = useRef<HTMLDivElement>(null);
	const pdfDocRef = useRef<PDFDocumentProxy | null>(null);
	const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
	const renderTasksRef = useRef<Map<number, RenderTask>>(new Map());
	const renderedScalesRef = useRef<Map<number, number>>(new Map());

	const renderPage = useCallback(async (pageNum: number, currentScale: number) => {
		const pdf = pdfDocRef.current;
		const canvas = canvasRefs.current.get(pageNum);
		if (!pdf || !canvas) return;

		if (renderedScalesRef.current.get(pageNum) === currentScale) return;

		const existing = renderTasksRef.current.get(pageNum);
		if (existing) {
			existing.cancel();
			renderTasksRef.current.delete(pageNum);
		}

		try {
			const page = await pdf.getPage(pageNum);
			const viewport = page.getViewport({ scale: currentScale });
			const dpr = window.devicePixelRatio || 1;

			canvas.width = Math.floor(viewport.width * dpr);
			canvas.height = Math.floor(viewport.height * dpr);
			canvas.style.width = `${Math.floor(viewport.width)}px`;
			canvas.style.height = `${Math.floor(viewport.height)}px`;

			const renderTask = page.render({
				canvas,
				viewport,
				transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
			});

			renderTasksRef.current.set(pageNum, renderTask);

			await renderTask.promise;
			renderTasksRef.current.delete(pageNum);
			renderedScalesRef.current.set(pageNum, currentScale);
		} catch (err: unknown) {
			if (err instanceof Error && err.message?.includes("cancelled")) return;
			console.error(`Failed to render page ${pageNum}:`, err);
		}
	}, []);

	useEffect(() => {
		let cancelled = false;

		const loadDocument = async () => {
			setLoading(true);
			setLoadError(null);
			setNumPages(0);
			setCurrentPage(1);

			try {
				const loadingTask = pdfjsLib.getDocument({
					url: pdfUrl,
					httpHeaders: getAuthHeaders(),
				});

				const pdf = await loadingTask.promise;
				if (cancelled) {
					pdf.destroy();
					return;
				}

				pdfDocRef.current = pdf;
				setNumPages(pdf.numPages);
				setLoading(false);
			} catch (err: unknown) {
				if (cancelled) return;
				const message = err instanceof Error ? err.message : "Failed to load PDF";
				setLoadError(message);
				setLoading(false);
			}
		};

		loadDocument();

		return () => {
			cancelled = true;
			for (const task of renderTasksRef.current.values()) {
				task.cancel();
			}
			renderTasksRef.current.clear();
			renderedScalesRef.current.clear();
			pdfDocRef.current?.destroy();
			pdfDocRef.current = null;
		};
	}, [pdfUrl]);

	useEffect(() => {
		if (!pdfDocRef.current || numPages === 0) return;

		renderedScalesRef.current.clear();

		for (let i = 1; i <= numPages; i++) {
			renderPage(i, scale);
		}
	}, [scale, numPages, renderPage]);

	useEffect(() => {
		const container = scrollContainerRef.current;
		if (!container || numPages <= 1) return;

		const handleScroll = () => {
			const canvases = canvasRefs.current;
			const containerTop = container.scrollTop;
			const containerMid = containerTop + container.clientHeight / 2;

			let closest = 1;
			let closestDist = Number.POSITIVE_INFINITY;

			for (let i = 1; i <= numPages; i++) {
				const canvas = canvases.get(i);
				if (!canvas) continue;
				const rect = canvas.getBoundingClientRect();
				const containerRect = container.getBoundingClientRect();
				const canvasMid = rect.top - containerRect.top + containerTop + rect.height / 2;
				const dist = Math.abs(canvasMid - containerMid);
				if (dist < closestDist) {
					closestDist = dist;
					closest = i;
				}
			}

			setCurrentPage(closest);
		};

		container.addEventListener("scroll", handleScroll, { passive: true });
		return () => container.removeEventListener("scroll", handleScroll);
	}, [numPages]);

	const setCanvasRef = useCallback((pageNum: number, el: HTMLCanvasElement | null) => {
		if (el) {
			canvasRefs.current.set(pageNum, el);
		} else {
			canvasRefs.current.delete(pageNum);
		}
	}, []);

	const zoomIn = useCallback(() => {
		setScale((prev) => Math.min(MAX_ZOOM, +(prev + ZOOM_STEP).toFixed(2)));
	}, []);

	const zoomOut = useCallback(() => {
		setScale((prev) => Math.max(MIN_ZOOM, +(prev - ZOOM_STEP).toFixed(2)));
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
			{numPages > 0 && (
				<div className={`flex items-center justify-center gap-2 px-4 py-2 border-b shrink-0 ${isPublic ? "bg-main-panel" : "bg-sidebar"}`}>
					{numPages > 1 && (
						<>
							<span className="text-xs text-muted-foreground tabular-nums min-w-[60px] text-center">
								{currentPage} / {numPages}
							</span>
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

			<div
				ref={scrollContainerRef}
				className={`relative flex-1 overflow-auto ${isPublic ? "bg-main-panel" : "bg-sidebar"}`}
			>
				{loading ? (
					<div className={`absolute inset-0 flex items-center justify-center ${isPublic ? "text-foreground" : "text-sidebar-foreground"}`}>
						<Spinner size="md" />
					</div>
				) : (
					<div
						ref={pagesContainerRef}
						className="flex flex-col items-center py-4"
						style={{ gap: `${PAGE_GAP}px` }}
					>
						{Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
							<canvas
								key={pageNum}
								ref={(el) => setCanvasRef(pageNum, el)}
								className="shadow-lg"
							/>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

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

interface PageDimensions {
	width: number;
	height: number;
}

const ZOOM_STEP = 0.15;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const PAGE_GAP = 12;
const SCROLL_DEBOUNCE_MS = 30;
const BUFFER_PAGES = 1;

export function PdfViewer({ pdfUrl, isPublic = false }: PdfViewerProps) {
	const [numPages, setNumPages] = useState(0);
	const [scale, setScale] = useState(1);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);

	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const pdfDocRef = useRef<PDFDocumentProxy | null>(null);
	const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
	const renderTasksRef = useRef<Map<number, RenderTask>>(new Map());
	const renderedScalesRef = useRef<Map<number, number>>(new Map());
	const pageDimsRef = useRef<PageDimensions[]>([]);
	const visiblePagesRef = useRef<Set<number>>(new Set());
	const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const getScaledHeight = useCallback(
		(pageIndex: number) => {
			const dims = pageDimsRef.current[pageIndex];
			return dims ? Math.floor(dims.height * scale) : 0;
		},
		[scale],
	);

	const getVisibleRange = useCallback(() => {
		const container = scrollContainerRef.current;
		if (!container || pageDimsRef.current.length === 0) return { first: 1, last: 1 };

		const scrollTop = container.scrollTop;
		const viewportHeight = container.clientHeight;
		const scrollBottom = scrollTop + viewportHeight;

		let cumTop = 16;
		let first = 1;
		let last = pageDimsRef.current.length;

		for (let i = 0; i < pageDimsRef.current.length; i++) {
			const pageHeight = getScaledHeight(i);
			const pageBottom = cumTop + pageHeight;

			if (pageBottom >= scrollTop && first === 1) {
				first = i + 1;
			}
			if (cumTop > scrollBottom) {
				last = i;
				break;
			}

			cumTop = pageBottom + PAGE_GAP;
		}

		first = Math.max(1, first - BUFFER_PAGES);
		last = Math.min(pageDimsRef.current.length, last + BUFFER_PAGES);

		return { first, last };
	}, [getScaledHeight]);

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
			page.cleanup();
		} catch (err: unknown) {
			if (err instanceof Error && err.message?.includes("cancelled")) return;
			console.error(`Failed to render page ${pageNum}:`, err);
		}
	}, []);

	const cleanupPage = useCallback((pageNum: number) => {
		const existing = renderTasksRef.current.get(pageNum);
		if (existing) {
			existing.cancel();
			renderTasksRef.current.delete(pageNum);
		}

		const canvas = canvasRefs.current.get(pageNum);
		if (canvas) {
			const ctx = canvas.getContext("2d");
			if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
			canvas.width = 0;
			canvas.height = 0;
		}

		renderedScalesRef.current.delete(pageNum);
	}, []);

	const renderVisiblePages = useCallback(() => {
		if (!pdfDocRef.current || pageDimsRef.current.length === 0) return;

		const { first, last } = getVisibleRange();
		const newVisible = new Set<number>();

		for (let i = first; i <= last; i++) {
			newVisible.add(i);
			renderPage(i, scale);
		}

		for (const pageNum of visiblePagesRef.current) {
			if (!newVisible.has(pageNum)) {
				cleanupPage(pageNum);
			}
		}

		visiblePagesRef.current = newVisible;
	}, [getVisibleRange, renderPage, cleanupPage, scale]);

	useEffect(() => {
		let cancelled = false;

		const loadDocument = async () => {
			setLoading(true);
			setLoadError(null);
			setNumPages(0);
			pageDimsRef.current = [];

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

				const dims: PageDimensions[] = [];
				for (let i = 1; i <= pdf.numPages; i++) {
					const page = await pdf.getPage(i);
					const viewport = page.getViewport({ scale: 1 });
					dims.push({ width: viewport.width, height: viewport.height });
					page.cleanup();
				}

				if (cancelled) {
					pdf.destroy();
					return;
				}

				pdfDocRef.current = pdf;
				pageDimsRef.current = dims;
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
			visiblePagesRef.current.clear();
			pdfDocRef.current?.destroy();
			pdfDocRef.current = null;
		};
	}, [pdfUrl]);

	useEffect(() => {
		if (numPages === 0) return;

		renderedScalesRef.current.clear();
		visiblePagesRef.current.clear();

		const frame = requestAnimationFrame(() => {
			renderVisiblePages();
		});

		return () => cancelAnimationFrame(frame);
	}, [numPages, renderVisiblePages]);

	useEffect(() => {
		const container = scrollContainerRef.current;
		if (!container || numPages === 0) return;

		const handleScroll = () => {
			if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current);
			scrollTimerRef.current = setTimeout(() => {
				renderVisiblePages();
			}, SCROLL_DEBOUNCE_MS);
		};

		container.addEventListener("scroll", handleScroll, { passive: true });
		return () => {
			container.removeEventListener("scroll", handleScroll);
			if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current);
		};
	}, [numPages, renderVisiblePages]);

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
				<p className="font-medium text-foreground">Failed to load PDF</p>
				<p className="text-sm text-muted-foreground">{loadError}</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full">
			{numPages > 0 && (
				<div className={`flex items-center justify-center gap-2 px-4 py-2 border-b shrink-0 ${isPublic ? "bg-main-panel" : "bg-sidebar"}`}>
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
					<div className="flex flex-col items-center py-4" style={{ gap: `${PAGE_GAP}px` }}>
						{pageDimsRef.current.map((dims, i) => {
							const pageNum = i + 1;
							const scaledWidth = Math.floor(dims.width * scale);
							const scaledHeight = Math.floor(dims.height * scale);
							return (
								<div
									key={pageNum}
									className="relative shrink-0"
									style={{ width: scaledWidth, height: scaledHeight }}
								>
									<canvas
										ref={(el) => setCanvasRef(pageNum, el)}
										className="shadow-lg absolute inset-0"
									/>
									{numPages > 1 && (
										<span className="absolute bottom-2 right-3 text-[10px] tabular-nums text-white/80 bg-black/50 px-1.5 py-0.5 rounded pointer-events-none">
											Page {pageNum}/{numPages}
										</span>
									)}
								</div>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}

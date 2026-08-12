"use client";

import { ZoomInIcon, ZoomOutIcon } from "lucide-react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFViewer as PDFViewerCore } from "pdfjs-dist/web/pdf_viewer.mjs";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authenticatedFetch } from "@/lib/auth-fetch";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url
).toString();

interface PdfViewerProps {
	pdfUrl: string;
	isPublic?: boolean;
	/** Extra actions rendered on the right side of the zoom toolbar (e.g. download, version switcher) */
	toolbarActions?: ReactNode;
	/** Optional panel-header target for zoom controls. Passing null reserves it while it mounts. */
	zoomControlsContainer?: HTMLElement | null;
}

type EmbeddedPdfViewer = Omit<PDFViewerCore, "setDocument"> & {
	setDocument(pdfDocument: PDFDocumentProxy | null): void;
};

type PDFViewerOptionsWithSignal = ConstructorParameters<typeof PDFViewerCore>[0] & {
	abortSignal: AbortSignal;
};

interface TouchManagerInstance {
	destroy(): void;
}

interface TouchManagerConstructor {
	new (options: {
		container: HTMLElement;
		isPinchingDisabled?: () => boolean;
		onPinchStart?: () => void;
		onPinching?: (origin: number[], previousDistance: number, distance: number) => void;
		onPinchEnd?: () => void;
		signal: AbortSignal;
	}): TouchManagerInstance;
}

interface PageRenderedEvent {
	isDetailView: boolean;
}

interface PinchPreview {
	baseScale: number;
	scaleFactor: number;
	startClientX: number;
	startClientY: number;
	clientX: number;
	clientY: number;
}

// PDFViewer clamps committed scales to these same limits internally.
const MIN_PDF_SCALE = 0.1;
const MAX_PDF_SCALE = 25;
const ZOOM_RENDER_DELAY_MS = 500;
const MOBILE_MAX_CANVAS_PIXELS = 5 * 1024 * 1024;
const DESKTOP_MAX_CANVAS_PIXELS = 16 * 1024 * 1024;
const DISABLED_LAYER_MODE = 0;

function getTouchMidpoint(touches: TouchList): [number, number] | null {
	const first = touches.item(0);
	const second = touches.item(1);
	if (!first || !second) return null;
	return [(first.clientX + second.clientX) / 2, (first.clientY + second.clientY) / 2];
}

export function PdfViewer({
	pdfUrl,
	isPublic = false,
	toolbarActions,
	zoomControlsContainer,
}: PdfViewerProps) {
	const [numPages, setNumPages] = useState(0);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const viewerHostRef = useRef<HTMLDivElement>(null);
	const viewerElementRef = useRef<HTMLDivElement>(null);
	const pdfViewerRef = useRef<EmbeddedPdfViewer | null>(null);

	useEffect(() => {
		const container = viewerHostRef.current;
		const viewerElement = viewerElementRef.current;
		if (!container || !viewerElement) return;

		const controller = new AbortController();
		let disposed = false;
		let loadingTask: PDFDocumentLoadingTask | null = null;
		let pdfDocument: PDFDocumentProxy | null = null;
		let pdfViewer: EmbeddedPdfViewer | null = null;
		let touchManager: TouchManagerInstance | null = null;
		let resizeObserver: ResizeObserver | null = null;
		let resizeFrame: number | null = null;
		let pinchFrame: number | null = null;
		let pinchPreview: PinchPreview | null = null;
		let latestTouchMidpoint: [number, number] | null = null;
		let eventBus: InstanceType<typeof import("pdfjs-dist/web/pdf_viewer.mjs")["EventBus"]> | null =
			null;
		let handlePagesInit: (() => void) | null = null;
		let handlePageRendered: ((event: PageRenderedEvent) => void) | null = null;

		setLoading(true);
		setLoadError(null);
		setNumPages(0);

		const clearPinchPreview = () => {
			if (pinchFrame !== null) {
				cancelAnimationFrame(pinchFrame);
				pinchFrame = null;
			}
			pinchPreview = null;
			latestTouchMidpoint = null;
			viewerElement.style.removeProperty("transform");
			viewerElement.style.removeProperty("transform-origin");
			viewerElement.style.removeProperty("will-change");
		};

		const initialize = async () => {
			try {
				// The viewer component build expects the PDF.js display API on globalThis.
				(
					globalThis as typeof globalThis & {
						pdfjsLib: typeof pdfjsLib;
					}
				).pdfjsLib = pdfjsLib;

				const viewerModulePromise = import("pdfjs-dist/web/pdf_viewer.mjs");
				const responsePromise = authenticatedFetch(pdfUrl, {
					skipAuthRedirect: true,
					signal: controller.signal,
				});
				const [viewerModule, response] = await Promise.all([viewerModulePromise, responsePromise]);

				if (!response.ok) {
					throw new Error(`Server returned ${response.status} while retrieving the PDF`);
				}

				const data = await response.arrayBuffer();
				if (disposed) return;

				const isMobile = window.matchMedia("(max-width: 1023px)").matches;
				eventBus = new viewerModule.EventBus();
				const linkService = new viewerModule.PDFLinkService({ eventBus });
				pdfViewer = new viewerModule.PDFViewer({
					container,
					viewer: viewerElement,
					eventBus,
					linkService,
					textLayerMode: DISABLED_LAYER_MODE,
					annotationMode: DISABLED_LAYER_MODE,
					maxCanvasPixels: isMobile ? MOBILE_MAX_CANVAS_PIXELS : DESKTOP_MAX_CANVAS_PIXELS,
					maxCanvasDim: isMobile ? 8192 : 16384,
					enableDetailCanvas: true,
					enableOptimizedPartialRendering: true,
					imagesRightClickMinSize: -1,
					supportsPinchToZoom: false,
					minDurationToUpdateCanvas: ZOOM_RENDER_DELAY_MS,
					abortSignal: controller.signal,
				} as PDFViewerOptionsWithSignal) as EmbeddedPdfViewer;
				pdfViewerRef.current = pdfViewer;
				linkService.setViewer(pdfViewer);

				handlePagesInit = () => {
					if (disposed || !pdfViewer || !pdfDocument) return;
					viewerElement.classList.toggle("multiple-pages", pdfDocument.numPages > 1);
					viewerElement.style.setProperty("--pdf-pages-count", `"${pdfDocument.numPages}"`);
					pdfViewer.currentScaleValue = "page-width";
					setNumPages(pdfDocument.numPages);
				};
				handlePageRendered = ({ isDetailView }: PageRenderedEvent) => {
					if (!disposed && !isDetailView) setLoading(false);
				};
				eventBus.on("pagesinit", handlePagesInit);
				eventBus.on("pagerendered", handlePageRendered);

				loadingTask = pdfjsLib.getDocument({ data });
				pdfDocument = await loadingTask.promise;
				if (disposed) {
					await pdfDocument.destroy();
					return;
				}

				linkService.setDocument(pdfDocument);
				pdfViewer.setDocument(pdfDocument);

				const recordTouchMidpoint = (event: TouchEvent) => {
					latestTouchMidpoint = getTouchMidpoint(event.touches);
				};
				container.addEventListener("touchstart", recordTouchMidpoint, {
					capture: true,
					passive: true,
					signal: controller.signal,
				});
				container.addEventListener("touchmove", recordTouchMidpoint, {
					capture: true,
					passive: true,
					signal: controller.signal,
				});

				const TouchManager = (
					pdfjsLib as typeof pdfjsLib & {
						TouchManager: TouchManagerConstructor;
					}
				).TouchManager;
				touchManager = new TouchManager({
					container,
					isPinchingDisabled: () => !pdfViewer || pdfViewer.pagesCount === 0,
					onPinchStart: () => {
						if (!pdfViewer || !latestTouchMidpoint) return;
						const [clientX, clientY] = latestTouchMidpoint;
						const viewerRect = viewerElement.getBoundingClientRect();
						pinchPreview = {
							baseScale: pdfViewer.currentScale,
							scaleFactor: 1,
							startClientX: clientX,
							startClientY: clientY,
							clientX,
							clientY,
						};
						viewerElement.style.transformOrigin = `${clientX - viewerRect.left}px ${
							clientY - viewerRect.top
						}px`;
						viewerElement.style.willChange = "transform";
					},
					onPinching: (_origin, previousDistance, distance) => {
						if (!pinchPreview || !latestTouchMidpoint || previousDistance <= 0) return;
						const targetScale = Math.max(
							MIN_PDF_SCALE,
							Math.min(
								MAX_PDF_SCALE,
								pinchPreview.baseScale * pinchPreview.scaleFactor * (distance / previousDistance)
							)
						);
						pinchPreview.scaleFactor = targetScale / pinchPreview.baseScale;
						pinchPreview.clientX = latestTouchMidpoint[0];
						pinchPreview.clientY = latestTouchMidpoint[1];

						if (pinchFrame !== null) return;
						pinchFrame = requestAnimationFrame(() => {
							pinchFrame = null;
							if (!pinchPreview) return;
							const translateX = pinchPreview.clientX - pinchPreview.startClientX;
							const translateY = pinchPreview.clientY - pinchPreview.startClientY;
							viewerElement.style.transform = `translate3d(${translateX}px, ${translateY}px, 0) scale(${pinchPreview.scaleFactor})`;
						});
					},
					onPinchEnd: () => {
						const preview = pinchPreview;
						if (!pdfViewer || !preview) {
							clearPinchPreview();
							return;
						}

						const translateX = preview.clientX - preview.startClientX;
						const translateY = preview.clientY - preview.startClientY;
						if (preview.scaleFactor !== 1) {
							const containerRect = container.getBoundingClientRect();
							pdfViewer.updateScale({
								drawingDelay: ZOOM_RENDER_DELAY_MS,
								scaleFactor: preview.scaleFactor,
								origin: [
									container.offsetLeft + preview.startClientX - containerRect.left,
									container.offsetTop + preview.startClientY - containerRect.top,
								],
							});
						}
						container.scrollLeft -= translateX;
						container.scrollTop -= translateY;
						clearPinchPreview();
					},
					signal: controller.signal,
				});

				resizeObserver = new ResizeObserver(() => {
					if (!pdfViewer || pdfViewer.currentScaleValue !== "page-width") return;
					if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
					resizeFrame = requestAnimationFrame(() => {
						resizeFrame = null;
						if (pdfViewer?.currentScaleValue === "page-width") {
							pdfViewer.currentScaleValue = "page-width";
						}
					});
				});
				resizeObserver.observe(container);
			} catch (error: unknown) {
				if (disposed) return;
				setLoadError(error instanceof Error ? error.message : "Failed to load PDF");
				setLoading(false);
			}
		};

		void initialize();

		return () => {
			disposed = true;
			controller.abort();
			if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
			resizeObserver?.disconnect();
			touchManager?.destroy();
			clearPinchPreview();
			if (eventBus && handlePagesInit) eventBus.off("pagesinit", handlePagesInit);
			if (eventBus && handlePageRendered) eventBus.off("pagerendered", handlePageRendered);
			pdfViewer?.setDocument(null);
			pdfViewerRef.current = null;
			viewerElement.classList.remove("multiple-pages");
			viewerElement.style.removeProperty("--pdf-pages-count");
			if (pdfDocument) {
				void pdfDocument.destroy();
			} else {
				void loadingTask?.destroy();
			}
		};
	}, [pdfUrl]);

	const zoomIn = useCallback(() => {
		pdfViewerRef.current?.increaseScale({ drawingDelay: ZOOM_RENDER_DELAY_MS });
	}, []);

	const zoomOut = useCallback(() => {
		pdfViewerRef.current?.decreaseScale({ drawingDelay: ZOOM_RENDER_DELAY_MS });
	}, []);

	const zoomControls = (
		<div className="hidden items-center gap-1 lg:flex">
			<Button
				variant="ghost"
				size="icon"
				onClick={zoomOut}
				disabled={loading}
				className="size-6 shrink-0 rounded-full text-muted-foreground"
			>
				<ZoomOutIcon className="size-4" />
				<span className="sr-only">Zoom out</span>
			</Button>
			<Button
				variant="ghost"
				size="icon"
				onClick={zoomIn}
				disabled={loading}
				className="size-6 shrink-0 rounded-full text-muted-foreground"
			>
				<ZoomInIcon className="size-4" />
				<span className="sr-only">Zoom in</span>
			</Button>
		</div>
	);

	if (loadError) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
				<p className="font-medium text-foreground">Failed to load PDF</p>
				<p className="text-sm text-muted-foreground">{loadError}</p>
			</div>
		);
	}

	return (
		<div className="flex h-full flex-col">
			{numPages > 0 && zoomControlsContainer
				? createPortal(zoomControls, zoomControlsContainer)
				: null}
			{numPages > 0 && zoomControlsContainer === undefined ? (
				<div
					className={`flex shrink-0 select-none items-center border-b px-4 py-2 ${isPublic ? "bg-main-panel" : "bg-sidebar"}`}
				>
					<div className="flex-1" aria-hidden="true" />
					{zoomControls}
					<div className="flex flex-1 items-center justify-end gap-1">{toolbarActions}</div>
				</div>
			) : null}

			<div className="relative min-h-0 flex-1">
				<div
					ref={viewerHostRef}
					data-vaul-no-drag=""
					className="absolute inset-0 overflow-auto bg-white"
				>
					<div ref={viewerElementRef} className="pdfViewer surfsense-pdf-viewer" />
				</div>
				{loading ? (
					<div
						className={`pointer-events-none absolute inset-0 flex items-center justify-center ${isPublic ? "text-foreground" : "text-sidebar-foreground"}`}
					>
						<Spinner size="md" />
					</div>
				) : null}
			</div>
		</div>
	);
}

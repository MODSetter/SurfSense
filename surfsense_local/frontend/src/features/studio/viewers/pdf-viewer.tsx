import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist"
import type { PDFViewer as PDFViewerCore } from "pdfjs-dist/web/pdf_viewer.mjs"
import "pdfjs-dist/web/pdf_viewer.css"
import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Button } from "@/components/ui/button"
import { ZoomInIcon, ZoomOutIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, type ArtifactDetail } from "../api"

// Ported from surfsense_web's components/shared/pdf-viewer.tsx, trimmed to
// what this desktop app needs: no pinch-to-zoom touch gestures (Electron has
// no touchscreen story here). Zoom controls portal into the shared panel
// header (actionsContainer) instead of surfsense_web's own toolbar row.
//
// pdfjs-dist itself is dynamically imported (not at module scope): its core
// module runs a DOMMatrix feature check on import, which crashes in the
// jsdom test environment the moment anything imports the viewer registry —
// even a test with no PDF in sight. Loading it lazily, only once a PdfViewer
// actually mounts, keeps that side effect out of every other test's way.
let pdfjsLibPromise: Promise<typeof import("pdfjs-dist")> | null = null
function loadPdfjsLib() {
  pdfjsLibPromise ??= import("pdfjs-dist").then((pdfjsLib) => {
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString()
    return pdfjsLib
  })
  return pdfjsLibPromise
}

type EmbeddedPdfViewer = Omit<PDFViewerCore, "setDocument"> & {
  setDocument(pdfDocument: PDFDocumentProxy | null): void
}

interface PageRenderedEvent {
  isDetailView: boolean
}

export function PdfViewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const [numPages, setNumPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerElementRef = useRef<HTMLDivElement>(null)
  const pdfViewerRef = useRef<EmbeddedPdfViewer | null>(null)

  useEffect(() => {
    void retryKey
    const container = containerRef.current
    const viewerElement = viewerElementRef.current
    if (!container || !viewerElement || !primary) return

    const controller = new AbortController()
    let disposed = false
    let loadingTask: PDFDocumentLoadingTask | null = null
    let pdfDocument: PDFDocumentProxy | null = null
    let pdfViewer: EmbeddedPdfViewer | null = null
    let resizeObserver: ResizeObserver | null = null
    let resizeFrame: number | null = null
    let eventBus: InstanceType<
      (typeof import("pdfjs-dist/web/pdf_viewer.mjs"))["EventBus"]
    > | null = null
    let handlePagesInit: (() => void) | null = null
    let handlePageRendered: ((event: PageRenderedEvent) => void) | null = null

    setLoading(true)
    setLoadError(null)
    setNumPages(0)

    void (async () => {
      try {
        const pdfjsLibPromise = loadPdfjsLib()
        const viewerModulePromise = import("pdfjs-dist/web/pdf_viewer.mjs")
        const responsePromise = fetch(fileUrl(artifact.id, "primary"), {
          signal: controller.signal,
        })
        const [pdfjsLib, viewerModule, response] = await Promise.all([
          pdfjsLibPromise,
          viewerModulePromise,
          responsePromise,
        ])

        if (!response.ok) {
          throw new Error(`Server returned ${response.status} while retrieving the PDF`)
        }

        const data = await response.arrayBuffer()
        if (disposed) return

        eventBus = new viewerModule.EventBus()
        const linkService = new viewerModule.PDFLinkService({ eventBus })
        pdfViewer = new viewerModule.PDFViewer({
          container,
          viewer: viewerElement,
          eventBus,
          linkService,
          textLayerMode: 0,
          annotationMode: 0,
        }) as EmbeddedPdfViewer
        pdfViewerRef.current = pdfViewer
        linkService.setViewer(pdfViewer)

        handlePagesInit = () => {
          if (disposed || !pdfViewer || !pdfDocument) return
          pdfViewer.currentScaleValue = "page-width"
          container.scrollTop = 0
          setNumPages(pdfDocument.numPages)
        }
        handlePageRendered = ({ isDetailView }) => {
          if (!disposed && !isDetailView) setLoading(false)
        }
        eventBus.on("pagesinit", handlePagesInit)
        eventBus.on("pagerendered", handlePageRendered)

        loadingTask = pdfjsLib.getDocument({ data })
        pdfDocument = await loadingTask.promise
        if (disposed) {
          await pdfDocument.destroy()
          return
        }

        linkService.setDocument(pdfDocument)
        pdfViewer.setDocument(pdfDocument)

        resizeObserver = new ResizeObserver(() => {
          if (pdfViewer?.currentScaleValue !== "page-width") return
          if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
          resizeFrame = requestAnimationFrame(() => {
            resizeFrame = null
            if (pdfViewer?.currentScaleValue === "page-width") {
              pdfViewer.currentScaleValue = "page-width"
            }
          })
        })
        resizeObserver.observe(container)
      } catch (error: unknown) {
        if (disposed) return
        setLoadError(error instanceof Error ? error.message : "Failed to load PDF")
        setLoading(false)
      }
    })()

    return () => {
      disposed = true
      controller.abort()
      if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
      resizeObserver?.disconnect()
      if (eventBus && handlePagesInit) eventBus.off("pagesinit", handlePagesInit)
      if (eventBus && handlePageRendered) eventBus.off("pagerendered", handlePageRendered)
      pdfViewer?.setDocument(null)
      pdfViewerRef.current = null
      if (pdfDocument) {
        void pdfDocument.destroy()
      } else {
        void loadingTask?.destroy()
      }
    }
  }, [artifact.id, primary, retryKey])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // ctrlKey is also how browsers report a trackpad pinch gesture (not
    // just an actual held-down Ctrl key), so this covers both at once —
    // PDFViewer has no built-in handling for either, unlike the reference
    // PDF.js viewer app, which this embeddable component doesn't include.
    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return
      event.preventDefault()
      pdfViewerRef.current?.updateScale({
        steps: event.deltaY < 0 ? 1 : -1,
        origin: [event.clientX, event.clientY],
        drawingDelay: 500,
      })
    }

    container.addEventListener("wheel", handleWheel, { passive: false })
    return () => container.removeEventListener("wheel", handleWheel)
  }, [])

  const zoomIn = useCallback(() => {
    pdfViewerRef.current?.increaseScale({ drawingDelay: 500 })
  }, [])

  const zoomOut = useCallback(() => {
    pdfViewerRef.current?.decreaseScale({ drawingDelay: 500 })
  }, [])

  if (!primary) return null

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm font-medium">Failed to load PDF</p>
        <p className="text-xs text-muted-foreground">{loadError}</p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setRetryKey((key) => key + 1)}
        >
          Try again
        </Button>
      </div>
    )
  }

  const zoomControls = (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Zoom out"
        onClick={zoomOut}
      >
        <ZoomOutIcon />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Zoom in"
        onClick={zoomIn}
      >
        <ZoomInIcon />
      </Button>
    </>
  )

  return (
    <div className="flex h-full flex-col bg-white text-neutral-950">
      {numPages > 0 && actionsContainer
        ? createPortal(zoomControls, actionsContainer)
        : null}

      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="absolute inset-0 overflow-auto">
          <div ref={viewerElementRef} className="pdfViewer" />
        </div>
        {loading ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-muted-foreground">
            <Spinner className="size-6" />
          </div>
        ) : null}
      </div>
    </div>
  )
}

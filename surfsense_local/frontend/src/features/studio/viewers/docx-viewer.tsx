import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Button } from "@/components/ui/button"
import { FileIcon, ZoomInIcon, ZoomOutIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, type ArtifactDetail } from "../api"

/** Reject before docx-preview allocates — keep below the server file limit. */
const MAX_VIEWER_BYTES = 15 * 1024 * 1024

const MIN_ZOOM = 0.25
const MAX_ZOOM = 3
const ZOOM_STEP = 1.1

export function DocxViewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const containerRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(() => primary != null)
  const [error, setError] = useState<unknown>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [hasContent, setHasContent] = useState(false)

  useEffect(() => {
    void retryKey
    const container = containerRef.current
    const body = bodyRef.current
    if (!container || !body || !primary) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setHasContent(false)
    body.replaceChildren()

    void (async () => {
      try {
        if (primary.size_bytes > MAX_VIEWER_BYTES) {
          throw new Error(
            `Document is too large to preview (${primary.size_bytes} bytes)`
          )
        }
        const response = await fetch(fileUrl(artifact.id, "primary"))
        if (!response.ok) {
          throw new Error(`Could not load document (${response.status})`)
        }
        const buffer = await response.arrayBuffer()
        // docx-preview has no top-level import cost worth paying eagerly —
        // load it the same way the other heavy viewers (xlsx, pdf) do.
        const { renderAsync } = await import("docx-preview")
        if (cancelled) return
        // docx-preview always renders the page at its physical size (e.g.
        // ~816px for 8.5x11in) — it has no fit-to-width or zoom option of
        // its own, so both are hand-rolled here via the `zoom` CSS
        // property. `zoom` (not `transform: scale`) reflows layout at the
        // new size, so the scroll area actually matches what's visible;
        // it's non-standard outside Chromium, which is fine since this is
        // an Electron-only app.
        await renderAsync(buffer, body, body, {
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
        })
        if (cancelled) return

        // docx-preview's own injected styles set `.docx-wrapper`'s
        // background to gray (the padding around each white page) — an
        // inline style here beats that class rule's specificity.
        const wrapper = body.querySelector<HTMLElement>(".docx-wrapper")
        if (wrapper) wrapper.style.background = "white"

        const page = body.querySelector<HTMLElement>(".docx")
        const pageWidth = page?.offsetWidth
        if (pageWidth) {
          const fit = container.clientWidth / pageWidth
          setZoom(Math.min(1, Math.max(MIN_ZOOM, fit)))
        }
        setHasContent(true)
      } catch (cause) {
        if (!cancelled) setError(cause)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [artifact.id, primary, retryKey])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return
      event.preventDefault()
      setZoom((current) =>
        Math.min(
          MAX_ZOOM,
          Math.max(
            MIN_ZOOM,
            current * (event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP)
          )
        )
      )
    }

    container.addEventListener("wheel", handleWheel, { passive: false })
    return () => container.removeEventListener("wheel", handleWheel)
  }, [])

  const zoomIn = useCallback(() => {
    setZoom((current) => Math.min(MAX_ZOOM, current * ZOOM_STEP))
  }, [])

  const zoomOut = useCallback(() => {
    setZoom((current) => Math.max(MIN_ZOOM, current / ZOOM_STEP))
  }, [])

  if (!primary) return null

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
    <div ref={containerRef} className="relative h-full overflow-auto bg-white">
      {hasContent && actionsContainer
        ? createPortal(zoomControls, actionsContainer)
        : null}
      <div ref={bodyRef} style={{ zoom }} />
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Spinner className="size-6" />
        </div>
      ) : null}
      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white px-5 py-4 text-center">
          <FileIcon className="size-8 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">Couldn't open this document</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {error instanceof Error
                ? error.message
                : "This document can't be previewed here. Download it to open it."}
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setRetryKey((key) => key + 1)}
          >
            Try again
          </Button>
        </div>
      ) : null}
    </div>
  )
}

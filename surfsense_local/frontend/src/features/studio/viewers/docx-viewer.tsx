import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Button } from "@/components/ui/button"
import { FileIcon, ZoomInIcon, ZoomOutIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { fileUrl, type ArtifactDetail } from "../api"

/** Reject before docx-preview allocates — keep below the server file limit. */
const MAX_VIEWER_BYTES = 15 * 1024 * 1024

const MIN_ZOOM = 0.25
const MAX_ZOOM = 3
const ZOOM_STEP = 1.1

// The frame's own rules: it reaches nothing outside the file. A Word file's
// styles are written into CSS as they come, so a font name can close its rule
// and add one that loads a web image; this stops the load.
const PAGES_POLICY =
  "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"

/**
 * The frame's document, readied for a Word file's pages. The frame keeps the
 * file's CSS out of the app's window and runs no script; its policy comes
 * first so it covers every style the file brings. Its base is its own
 * address, so a link to a place in the file scrolls there instead of loading
 * the app's address into the frame.
 */
function readyPages(frame: HTMLIFrameElement): Document | null {
  const pages = frame.contentDocument
  if (!pages || pages.head.querySelector("meta[http-equiv]")) return pages
  const policy = pages.createElement("meta")
  policy.httpEquiv = "Content-Security-Policy"
  policy.content = PAGES_POLICY
  const base = pages.createElement("base")
  base.href = "about:blank"
  pages.head.prepend(policy, base)
  pages.body.style.margin = "0"
  pages.body.style.background = "white"
  return pages
}

/**
 * A Word file's links come as written, so one can be a javascript: URL. Keep
 * links to places in the file and drop the rest: the app opens no web page a
 * document names.
 */
function disarmLinks(body: HTMLElement): void {
  for (const link of body.querySelectorAll<HTMLAnchorElement>("a[href]")) {
    if (!link.getAttribute("href")?.startsWith("#")) {
      link.removeAttribute("href")
    }
  }
}

export function DocxViewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const frameRef = useRef<HTMLIFrameElement>(null)
  const [loading, setLoading] = useState(() => primary != null)
  const [error, setError] = useState<unknown>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [hasContent, setHasContent] = useState(false)

  useEffect(() => {
    void retryKey
    const frame = frameRef.current
    const pages = frame && readyPages(frame)
    if (!frame || !pages || !primary) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setHasContent(false)
    pages.body.replaceChildren()

    void (async () => {
      try {
        if (primary.size_bytes > MAX_VIEWER_BYTES) {
          throw new Error(
            intl.formatMessage(
              {
                id: "studio_docx_viewer_oversize_error",
                defaultMessage:
                  "Document is too large to preview ({size, number, ::unit/megabyte .#})",
              },
              {
                size: primary.size_bytes / 1e6,
              }
            )
          )
        }
        const response = await fetch(fileUrl(artifact.id, "primary"))
        if (!response.ok) {
          throw new Error(
            intl.formatMessage(
              {
                id: "studio_docx_viewer_load_error",
                defaultMessage: "Could not load document ({status})",
              },
              {
                status: String(response.status),
              }
            )
          )
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
        // Each run lays out apart and goes in only if still current: a run
        // cancelled mid-render still finishes, and must not replace a later
        // version's pages. No altChunks: docx-preview puts their HTML in an
        // unsandboxed iframe, where a script the file carries would run. Data
        // URLs, the only images and fonts the frame's policy lets in.
        const rendered = pages.createElement("div")
        await renderAsync(buffer, rendered, rendered, {
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          renderAltChunks: false,
          useBase64URL: true,
        })
        if (cancelled) return
        disarmLinks(rendered)
        pages.body.replaceChildren(rendered)

        // docx-preview's own injected styles set `.docx-wrapper`'s
        // background to gray (the padding around each white page) — an
        // inline style here beats that class rule's specificity.
        const wrapper = rendered.querySelector<HTMLElement>(".docx-wrapper")
        if (wrapper) wrapper.style.background = "white"

        const page = rendered.querySelector<HTMLElement>(".docx")
        const pageWidth = page?.offsetWidth
        if (pageWidth) {
          const fit = frame.clientWidth / pageWidth
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
    const body = frameRef.current?.contentDocument?.body
    body?.style.setProperty("zoom", String(zoom))
  }, [zoom])

  // The pages fill the frame, so Ctrl+wheel lands in its document.
  useEffect(() => {
    const pages = frameRef.current?.contentDocument
    if (!pages) return

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

    pages.addEventListener("wheel", handleWheel, { passive: false })
    return () => pages.removeEventListener("wheel", handleWheel)
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
        aria-label={intl.formatMessage({
          id: "studio_docx_viewer_zoom_out_aria",
          defaultMessage: "Zoom out",
        })}
        onClick={zoomOut}
      >
        <ZoomOutIcon />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={intl.formatMessage({
          id: "studio_docx_viewer_zoom_in_aria",
          defaultMessage: "Zoom in",
        })}
        onClick={zoomIn}
      >
        <ZoomInIcon />
      </Button>
    </>
  )

  return (
    <div className="relative h-full bg-white">
      {hasContent && actionsContainer
        ? createPortal(zoomControls, actionsContainer)
        : null}
      <iframe
        ref={frameRef}
        title={artifact.title}
        sandbox="allow-same-origin"
        className="block h-full w-full border-0 bg-white"
      />
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Spinner className="size-6" />
        </div>
      ) : null}
      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white px-5 py-4 text-center">
          <FileIcon className="size-8 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">
              {intl.formatMessage({
                id: "studio_docx_viewer_error_title",
                defaultMessage: "Couldn’t open this document",
              })}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {error instanceof Error
                ? error.message
                : intl.formatMessage({
                    id: "studio_docx_viewer_error_body",
                    defaultMessage:
                      "This document can’t be previewed here. Download it to open it.",
                  })}
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setRetryKey((key) => key + 1)}
          >
            {intl.formatMessage({
              id: "studio_docx_viewer_retry_button",
              defaultMessage: "Try again",
            })}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

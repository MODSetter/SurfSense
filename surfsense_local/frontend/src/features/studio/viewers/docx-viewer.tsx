import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Button } from "@/components/ui/button"
import { FileIcon, ZoomInIcon, ZoomOutIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { openWordDocument } from "@/features/word-document/open-word-document"
import { intl } from "@/i18n/intl"
import { fileUrl, type ArtifactDetail } from "../api"

/** Reject before the renderer allocates — keep below the server file limit. */
const MAX_VIEWER_BYTES = 15 * 1024 * 1024

const MIN_ZOOM = 0.25
const MAX_ZOOM = 3

type PagesViewer = Pick<
  import("@silurus/ooxml/docx").DocxScrollViewer,
  "zoomIn" | "zoomOut" | "destroy"
>

export function DocxViewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const hostRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<PagesViewer | null>(null)
  const [loading, setLoading] = useState(() => primary != null)
  const [error, setError] = useState<unknown>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [hasContent, setHasContent] = useState(false)

  useEffect(() => {
    void retryKey
    const host = hostRef.current
    if (!host || !primary) return

    let cancelled = false
    let close = () => {}
    setLoading(true)
    setError(null)
    setHasContent(false)

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
        const response = await fetch(
          fileUrl(artifact.id, "primary", artifact.generation)
        )
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
        const file = await response.arrayBuffer()
        const document = await openWordDocument(file)
        if (cancelled) {
          document.destroy()
          return
        }
        const { DocxScrollViewer } = await import("@silurus/ooxml/docx")
        if (cancelled) {
          document.destroy()
          return
        }
        // Pages draw to canvases, so nothing the file carries becomes HTML or
        // runs. Its web links stay inert: the app opens no page a document names.
        const viewer: PagesViewer & { scrollToPage(page: number): void } =
          DocxScrollViewer.fromDocument(host, document, {
            comments: true,
            enableTextSelection: true,
            zoomMin: MIN_ZOOM,
            zoomMax: MAX_ZOOM,
            onHyperlinkClick: (target) => {
              if (target.kind !== "internal") return
              const page = document.getBookmarkPage(target.ref)
              if (page !== undefined) viewer.scrollToPage(page)
            },
          })
        viewerRef.current = viewer
        close = () => {
          viewerRef.current = null
          viewer.destroy()
          document.destroy()
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
      close()
    }
  }, [artifact.id, artifact.generation, primary, retryKey])

  const zoomIn = useCallback(() => void viewerRef.current?.zoomIn(), [])
  const zoomOut = useCallback(() => void viewerRef.current?.zoomOut(), [])

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
      <div
        ref={hostRef}
        role="document"
        aria-label={artifact.title}
        className="h-full w-full overflow-hidden bg-white"
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

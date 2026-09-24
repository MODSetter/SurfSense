import type { PptxViewer as PptxViewerCore } from "@aiden0z/pptx-renderer"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { fileUrl, type ArtifactDetail } from "../api"

// Dynamically imported, same reasoning as pdf-viewer's pdfjs-dist load: it's
// a large DOM-touching renderer, no reason to pay for it (or risk jsdom
// issues in tests) until a pptx artifact actually mounts.
let pptxRendererPromise: Promise<
  typeof import("@aiden0z/pptx-renderer")
> | null = null
function loadPptxRenderer() {
  pptxRendererPromise ??= import("@aiden0z/pptx-renderer")
  return pptxRendererPromise
}

export function PptxViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    void retryKey
    const scrollContainer = scrollRef.current
    const content = contentRef.current
    if (!scrollContainer || !content || !primary) return

    const controller = new AbortController()
    let disposed = false
    let viewer: PptxViewerCore | null = null

    setLoading(true)
    setLoadError(null)
    content.replaceChildren()

    void (async () => {
      try {
        const [{ PptxViewer: Renderer, RECOMMENDED_ZIP_LIMITS }, response] =
          await Promise.all([
            loadPptxRenderer(),
            fetch(fileUrl(artifact.id, "primary"), {
              signal: controller.signal,
            }),
          ])

        if (!response.ok) {
          throw new Error(
            intl.formatMessage(
              { id: "studio_pptx_viewer_load_error" },
              {
                status: String(response.status),
              }
            )
          )
        }

        const data = await response.arrayBuffer()
        if (disposed) return

        viewer = await Renderer.open(data, content, {
          zipLimits: RECOMMENDED_ZIP_LIMITS,
          scrollContainer,
          renderMode: "list",
          listOptions: { windowed: true },
        })
        if (disposed) {
          viewer.destroy()
          return
        }
        setLoading(false)
      } catch (error: unknown) {
        if (disposed) return
        setLoadError(
          error instanceof Error
            ? error.message
            : intl.formatMessage({ id: "studio_pptx_viewer_unknown_error" })
        )
        setLoading(false)
      }
    })()

    return () => {
      disposed = true
      controller.abort()
      viewer?.destroy()
    }
  }, [artifact.id, primary, retryKey])

  if (!primary) return null

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm font-medium">
          {intl.formatMessage({ id: "studio_pptx_viewer_error_title" })}
        </p>
        <p className="text-xs text-muted-foreground">{loadError}</p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setRetryKey((key) => key + 1)}
        >
          {intl.formatMessage({ id: "studio_pptx_viewer_retry_button" })}
        </Button>
      </div>
    )
  }

  return (
    <div className="relative h-full bg-neutral-100 text-neutral-950">
      <div ref={scrollRef} className="absolute inset-0 overflow-auto">
        <div ref={contentRef} className="mx-auto max-w-4xl py-6" />
      </div>
      {loading ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Spinner className="size-6" />
        </div>
      ) : null}
    </div>
  )
}

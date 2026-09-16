import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { FileIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, type ArtifactDetail } from "../api"

/** Reject before docx-preview allocates — keep below the server file limit. */
const MAX_VIEWER_BYTES = 15 * 1024 * 1024

export function DocxViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const bodyRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(() => primary != null)
  const [error, setError] = useState<unknown>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    void retryKey
    const body = bodyRef.current
    if (!body || !primary) return

    let cancelled = false
    setLoading(true)
    setError(null)
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
        await renderAsync(buffer, body, body, {
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
        })
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

  if (!primary) return null

  return (
    <div className="relative h-full overflow-auto bg-neutral-100">
      <div ref={bodyRef} />
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Spinner className="size-6" />
        </div>
      ) : null}
      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-neutral-100 px-5 py-4 text-center">
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

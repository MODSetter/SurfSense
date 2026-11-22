import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { FileIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { fileUrl, type ArtifactDetail } from "../api"
import { VIEWER_PADDING } from "./viewer-layout"

/** Reject before the renderer allocates: a compressed workbook can inflate far
 *  past its size on disk. */
const MAX_VIEWER_BYTES = 15 * 1024 * 1024

class WorkbookError extends Error {
  readonly code: "oversize" | "fetch"

  constructor(code: "oversize" | "fetch", message: string) {
    super(message)
    this.code = code
  }
}

function fallbackMessage(error: unknown): string {
  if (error instanceof WorkbookError && error.code === "oversize") {
    return intl.formatMessage({
      id: "studio_xlsx_viewer_oversize_error",
      defaultMessage:
        "This workbook is too large to preview here. Download it to open it.",
    })
  }
  if (error instanceof WorkbookError) {
    return intl.formatMessage({
      id: "studio_xlsx_viewer_load_error",
      defaultMessage:
        "This spreadsheet can’t be previewed here. Download it to open it.",
    })
  }
  return intl.formatMessage({
    id: "studio_xlsx_viewer_unreadable_error",
    defaultMessage:
      "This workbook could not be opened. Download it to open it.",
  })
}

export function XlsxViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const hostRef = useRef<HTMLDivElement>(null)
  const [loading, setLoading] = useState(() => primary != null)
  const [error, setError] = useState<unknown>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    void retryKey
    const host = hostRef.current
    if (!host || !primary) return

    let cancelled = false
    let close = () => {}
    setLoading(true)
    setError(null)

    void (async () => {
      try {
        if (primary.size_bytes > MAX_VIEWER_BYTES) {
          throw new WorkbookError("oversize", "Workbook is too large")
        }
        const response = await fetch(
          fileUrl(artifact.id, "primary", artifact.generation)
        )
        if (!response.ok) {
          throw new WorkbookError(
            "fetch",
            `Could not load workbook (${response.status})`
          )
        }
        const file = await response.arrayBuffer()
        const [{ XlsxViewer: Renderer }, { default: wasmUrl }] =
          await Promise.all([
            import("@silurus/ooxml/xlsx"),
            // Inlined for the reason open-word-document.ts gives.
            import("../../../../node_modules/@silurus/ooxml/dist/xlsx_parser_bg.wasm?data-url"),
          ])
        if (cancelled) return
        // Sheets draw to a canvas. Links stay inert: the app opens no page a
        // document names. Web fonts stay off: a file never reaches the network.
        const viewer = new Renderer(host, {
          wasmUrl,
          useGoogleFonts: false,
          comments: true,
          enableHyperlinks: false,
        })
        close = () => viewer.destroy()
        await viewer.load(file)
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

  if (!primary) return null

  return (
    <div className="relative h-full overflow-hidden border bg-white">
      <div ref={hostRef} className="h-full w-full" />
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Spinner className="size-6" />
        </div>
      ) : null}
      {error ? (
        <div
          className={`absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background text-center ${VIEWER_PADDING}`}
        >
          <FileIcon className="size-8 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">
              {intl.formatMessage({
                id: "studio_xlsx_viewer_error_title",
                defaultMessage: "Couldn’t open this spreadsheet",
              })}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {fallbackMessage(error)}
            </p>
          </div>
          {!(error instanceof WorkbookError && error.code === "oversize") ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setRetryKey((key) => key + 1)}
            >
              {intl.formatMessage({
                id: "studio_xlsx_viewer_retry_button",
                defaultMessage: "Try again",
              })}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { FileIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { fileUrl, type ArtifactDetail } from "../api"
import { VIEWER_PADDING } from "./viewer-layout"

export function HtmlViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")

  const {
    data: html,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["artifact-html", artifact.id],
    queryFn: async () => {
      if (!primary) throw new Error("This artifact has no file to preview")
      // Content-Disposition on this route is "attachment" for text/html (see
      // the API's _INLINE_UNSAFE), which only affects navigation — fetch()
      // ignores it and returns the body normally, so we render it via
      // srcDoc into a sandboxed iframe instead of pointing src at the URL.
      const response = await fetch(fileUrl(artifact.id, "primary"))
      if (!response.ok) {
        throw new Error(`Could not load page (${response.status})`)
      }
      return response.text()
    },
    enabled: primary != null,
  })

  if (!primary) return null

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner className="size-6" />
      </div>
    )
  }

  if (error || html == null) {
    return (
      <div
        className={`flex h-full flex-col items-center justify-center gap-3 text-center ${VIEWER_PADDING}`}
      >
        <FileIcon className="size-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">
            {intl.formatMessage({ id: "studio_html_viewer_error_title" })}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {intl.formatMessage({ id: "studio_html_viewer_error_body" })}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => void refetch()}
        >
          {intl.formatMessage({ id: "studio_html_viewer_retry_button" })}
        </Button>
      </div>
    )
  }

  return (
    <iframe
      title={artifact.title}
      srcDoc={html}
      sandbox="allow-scripts allow-popups"
      className="h-full w-full border-0 bg-white"
    />
  )
}

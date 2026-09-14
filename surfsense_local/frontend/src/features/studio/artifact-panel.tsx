import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import { DownloadIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, readArtifact, type ArtifactDetail } from "./api"

function Preview({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  if (!primary) return null

  const src = fileUrl(artifact.id, primary.role)
  if (primary.mime_type.startsWith("audio/")) {
    // biome-ignore lint/a11y/useMediaCaption: The generated transcript is rendered directly below the player.
    return <audio className="w-full" controls src={src} />
  }
  if (primary.mime_type.startsWith("image/")) {
    return (
      <img
        className="mx-auto max-w-full outline outline-[oklch(0_0_0/0.1)] dark:outline-[oklch(1_0_0/0.1)]"
        alt={artifact.title}
        src={src}
      />
    )
  }
  return null
}

export function ArtifactPanel({
  artifactId,
  onClose,
}: {
  artifactId: number
  onClose: () => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact-panel", artifactId],
    queryFn: ({ signal }) => readArtifact(artifactId, signal),
  })

  return (
    <DetailPanel
      title={data?.title ?? (isLoading ? "Loading…" : "Artifact")}
      ariaLabel="Artifact"
      closeLabel="Close artifact"
      onClose={onClose}
      flush
      actions={
        data?.files.length
          ? data.files.map((file) => (
              <Button
                key={file.role}
                variant="default"
                size="sm"
                className="h-6 px-1.5 text-[11px]"
                asChild
              >
                <a href={fileUrl(data.id, file.role)} download>
                  <DownloadIcon data-icon="inline-start" />
                  {file.role === "primary" ? "Download" : file.role}
                </a>
              </Button>
            ))
          : null
      }
    >
      {isLoading ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          <Spinner />
        </div>
      ) : null}
      {error ? (
        <div className="flex h-full items-center justify-center px-5 text-center">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Failed to load artifact"}
          </p>
        </div>
      ) : null}
      {!isLoading && !error && data ? (
        <div className="h-full overflow-y-auto px-5 py-4">
          <div className="space-y-4">
            <Preview artifact={data} />
            <p className="text-sm leading-6 whitespace-pre-wrap">
              {data.content || "This artifact has no text body."}
            </p>
          </div>
        </div>
      ) : null}
    </DetailPanel>
  )
}

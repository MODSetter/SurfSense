import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import { DownloadIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, readArtifact, type ArtifactDetail } from "./api"
import { getArtifactViewer } from "./viewers/registry"

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
      {/* The one viewable stage every artifact format renders into: same
          size and position below the shared header, regardless of format. */}
      <div className="h-full overflow-y-auto px-5 py-4">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <Spinner />
          </div>
        ) : null}
        {error ? (
          <div className="flex h-full items-center justify-center text-center">
            <p className="text-sm text-destructive">
              {error instanceof Error
                ? error.message
                : "Failed to load artifact"}
            </p>
          </div>
        ) : null}
        {!isLoading && !error && data ? <Viewer artifact={data} /> : null}
      </div>
    </DetailPanel>
  )
}

function Viewer({ artifact }: { artifact: ArtifactDetail }) {
  const ArtifactViewer = getArtifactViewer(artifact.format)
  return (
    <div className="h-full">
      <ArtifactViewer artifact={artifact} />
    </div>
  )
}

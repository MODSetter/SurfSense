import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
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
                  {file.role === "primary" ? "Download" : file.role}
                </a>
              </Button>
            ))
          : null
      }
    >
      {/* The one viewable stage every artifact format renders into: same
          size and position below the shared header, regardless of format.
          No padding here — a viewer that wants breathing room (like
          DocumentViewer) adds its own, so a canvas viewer (mindmap, xlsx)
          can sit flush against the panel edges. */}
      <div className="h-full overflow-y-auto">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <Spinner />
          </div>
        ) : null}
        {error ? (
          <div className="flex h-full items-center justify-center px-5 text-center">
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
  // getArtifactViewer looks up a stable reference from the module-level
  // ARTIFACT_VIEWERS map (see viewers/registry.tsx) — it never constructs a
  // new component type, so this is safe despite the lint rule's heuristic.
  const ArtifactViewer = getArtifactViewer(artifact.format)
  return (
    <div className="h-full">
      {/* eslint-disable-next-line react-hooks/static-components */}
      <ArtifactViewer artifact={artifact} />
    </div>
  )
}

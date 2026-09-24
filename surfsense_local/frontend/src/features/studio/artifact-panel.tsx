import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import { Download01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import {
  fileUrl,
  readArtifact,
  type ArtifactDetail,
  type ArtifactFile,
} from "./api"
import { getArtifactViewer } from "./viewers/registry"

const DOWNLOAD_LABELS: Record<ArtifactFile["role"], () => string> = {
  primary: () =>
    intl.formatMessage({ id: "studio_artifact_panel_download_aria" }),
  preview: () =>
    intl.formatMessage({ id: "studio_artifact_panel_download_preview_aria" }),
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
  const [actionsContainer, setActionsContainer] =
    useState<HTMLDivElement | null>(null)

  return (
    <DetailPanel
      title={
        data?.title ??
        (isLoading
          ? intl.formatMessage({ id: "studio_artifact_panel_loading_status" })
          : intl.formatMessage({ id: "studio_artifact_panel_title" }))
      }
      titleClassName="select-none"
      ariaLabel={intl.formatMessage({ id: "studio_artifact_panel_aria" })}
      closeLabel={intl.formatMessage({
        id: "studio_artifact_panel_close_aria",
      })}
      onClose={onClose}
      flush
      actions={
        <>
          {/* Where a viewer's own controls (mindmap's fit, pdf's zoom)
              portal in — see ArtifactViewerProps.actionsContainer. */}
          <div ref={setActionsContainer} className="flex items-center gap-1" />
          {/* A flashcard deck's or quiz's only file is its raw JSON —
              nothing a user should download. */}
          {data?.files.length &&
          data.format !== "flashcards" &&
          data.format !== "quiz"
            ? data.files.map((file) => (
                <Button
                  key={file.role}
                  variant="secondary"
                  size="icon-sm"
                  asChild
                >
                  <a
                    href={fileUrl(data.id, file.role)}
                    download
                    aria-label={DOWNLOAD_LABELS[file.role]()}
                  >
                    <Download01Icon />
                  </a>
                </Button>
              ))
            : null}
        </>
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
                : intl.formatMessage({
                    id: "studio_artifact_panel_load_error",
                  })}
            </p>
          </div>
        ) : null}
        {!isLoading && !error && data ? (
          <Viewer artifact={data} actionsContainer={actionsContainer} />
        ) : null}
      </div>
    </DetailPanel>
  )
}

function Viewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  // getArtifactViewer looks up a stable reference from the module-level
  // ARTIFACT_VIEWERS map (see viewers/registry.tsx) — it never constructs a
  // new component type, so this is safe despite the lint rule's heuristic.
  const ArtifactViewer = getArtifactViewer(artifact.format)
  return (
    <div className="h-full">
      {/* eslint-disable-next-line react-hooks/static-components */}
      <ArtifactViewer artifact={artifact} actionsContainer={actionsContainer} />
    </div>
  )
}

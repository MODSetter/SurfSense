import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"

import { buttonVariants } from "@/components/ui/button"
import { DetailPanel } from "@/components/ui/detail-panel"
import { Download01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import {
  downloadUrl,
  readArtifact,
  type Artifact,
  type ArtifactDetail,
  type ArtifactFile,
  type RevisionDecision,
} from "./api"
import {
  newestReady,
  versionsOf,
  type VersionedArtifact,
} from "./artifact-versions"
import { canRefine } from "./can-refine"
import { RefineBox } from "./refine-box"
import { RevisedCopyBar } from "./revised-copy-bar"
import { RevisedCopyDownloads } from "./revised-copy-downloads"
import { VersionSwitcher } from "./version-switcher"
import { getArtifactViewer } from "./viewers/registry"

const DOWNLOAD_LABELS: Record<ArtifactFile["role"], () => string> = {
  primary: () =>
    intl.formatMessage({
      id: "studio_artifact_panel_download_aria",
      defaultMessage: "Download",
    }),
  preview: () =>
    intl.formatMessage({
      id: "studio_artifact_panel_download_preview_aria",
      defaultMessage: "Download preview",
    }),
}

/**
 * Opens a newer version of the shown document once it is ready, as the agent
 * makes one. Only a version that appears while the panel is open counts, so
 * opening an older one on purpose stays put. The highest version seen never
 * drops, so the newest one being run again is not a new one.
 */
function useFollowNewestVersion(
  versions: VersionedArtifact[],
  onOpenVersion: (artifactId: number) => void
) {
  const rootId = versions[0]?.version.root_id ?? null
  const newest = newestReady(versions)
  const seen = useRef<{ rootId: number; highest: number } | null>(null)
  useEffect(() => {
    const number = newest?.version.number ?? 0
    if (rootId === null || seen.current?.rootId !== rootId) {
      seen.current = rootId === null ? null : { rootId, highest: number }
      return
    }
    if (newest && number > seen.current.highest) {
      seen.current = { rootId, highest: number }
      onOpenVersion(newest.id)
    }
  }, [rootId, newest, onOpenVersion])
}

export function ArtifactPanel({
  artifactId,
  artifacts,
  onOpenVersion,
  onRefine,
  onDecideAll = async () => {},
  onClose,
}: {
  artifactId: number
  /** The workspace's artifacts, where the shown one's versions are found. */
  artifacts: Artifact[]
  onOpenVersion: (artifactId: number) => void
  /** Rejects with the reason the next version was refused. */
  onRefine: (artifactId: number, instruction: string) => Promise<void>
  /** Accepts or rejects all of a revised copy's changes as its next version;
   *  rejects with the reason it was refused. */
  onDecideAll?: (
    artifactId: number,
    decision: RevisionDecision
  ) => Promise<void>
  onClose: () => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact-panel", artifactId],
    queryFn: ({ signal }) => readArtifact(artifactId, signal),
  })
  const versions = versionsOf(artifacts, artifactId)
  useFollowNewestVersion(versions, onOpenVersion)
  // The list follows each run's status; the detail is read once.
  const shown = artifacts.find((artifact) => artifact.id === artifactId) ?? data
  const versionRunning = versions.some(
    (version) => version.status === "pending" || version.status === "processing"
  )
  const [actionsContainer, setActionsContainer] =
    useState<HTMLDivElement | null>(null)
  const revision = data?.revision ?? null
  // A decision starts from the newest ready version, so only it offers one.
  const newestShown = (newestReady(versions)?.id ?? artifactId) === artifactId

  return (
    <DetailPanel
      title={
        data?.title ??
        (isLoading
          ? intl.formatMessage({
              id: "studio_artifact_panel_loading_status",
              defaultMessage: "Loading…",
            })
          : intl.formatMessage({
              id: "studio_artifact_panel_title",
              defaultMessage: "Artifact",
            }))
      }
      titleClassName="select-none"
      ariaLabel={intl.formatMessage({
        id: "studio_artifact_panel_aria",
        defaultMessage: "Artifact",
      })}
      closeLabel={intl.formatMessage({
        id: "studio_artifact_panel_close_aria",
        defaultMessage: "Close artifact",
      })}
      onClose={onClose}
      flush
      actions={
        <>
          <VersionSwitcher
            versions={versions}
            openId={artifactId}
            onOpen={onOpenVersion}
          />
          {/* Where a viewer's own controls (mindmap's fit, pdf's zoom)
              portal in — see ArtifactViewerProps.actionsContainer. */}
          <div ref={setActionsContainer} className="flex items-center gap-1" />
          {/* A flashcard deck's or quiz's only file is its raw JSON —
              nothing a user should download. */}
          {data && revision ? (
            <RevisedCopyDownloads artifactId={data.id} revision={revision} />
          ) : data?.files.length &&
            data.format !== "flashcards" &&
            data.format !== "quiz" ? (
            data.files.map((file) => (
              // A plain link: Base UI's Button would give it role="button".
              <a
                key={file.role}
                href={downloadUrl(data.id, file.role)}
                download
                aria-label={DOWNLOAD_LABELS[file.role]()}
                className={buttonVariants({
                  variant: "secondary",
                  size: "icon-sm",
                })}
              >
                <Download01Icon />
              </a>
            ))
          ) : null}
        </>
      }
    >
      <div className="flex h-full flex-col">
        {!isLoading && !error && data && revision ? (
          <RevisedCopyBar
            key={artifactId}
            artifactId={artifactId}
            revision={revision}
            versionRunning={versionRunning}
            newest={newestShown}
            onDecideAll={onDecideAll}
          />
        ) : null}
        {/* The one viewable stage every artifact format renders into: same
            size and position below the shared header, regardless of format.
            No padding here — a viewer that wants breathing room (like
            DocumentViewer) adds its own, so a canvas viewer (mindmap, xlsx)
            can sit flush against the panel edges. */}
        <div className="min-h-0 flex-1 overflow-y-auto">
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
                      defaultMessage: "Failed to load artifact",
                    })}
              </p>
            </div>
          ) : null}
          {!isLoading && !error && data ? (
            <Viewer artifact={data} actionsContainer={actionsContainer} />
          ) : null}
        </div>
        {!isLoading && !error && shown && canRefine(shown) ? (
          <RefineBox
            key={artifactId}
            artifactId={artifactId}
            versionRunning={versionRunning}
            onRefine={onRefine}
          />
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

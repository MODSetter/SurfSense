import { useEffect, useRef, useState } from "react"
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { useWorkspaceChanges } from "@/features/workspaces/use-workspace-changes"
import { intl } from "@/i18n/intl"

import {
  cancelArtifact,
  createJob,
  deleteArtifact,
  listArtifacts,
  listFormats,
  regenerateArtifact,
  type Artifact,
  type StudioFormat,
  type StudioJobCreate,
} from "./api"
import { studioKeys } from "./query-keys"
import { translatedStudioError } from "./studio-error-text"

// The worker's notices are best-effort: one lost while a job runs would leave
// its row stale, so the list is still re-read now and then until none does.
const LOST_NOTICE_POLL_MS = 10_000

export function messageFrom(error: unknown) {
  const translated = translatedStudioError(error)
  if (translated !== null) return translated
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "studio_request_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

function isRunning(artifact: Artifact) {
  return artifact.status === "pending" || artifact.status === "processing"
}

const NO_ARTIFACTS: Artifact[] = []
const NO_FORMATS: StudioFormat[] = []

/** A toast for each job a new read of the list shows finished. */
function announceFinished(before: Artifact[], after: Artifact[]) {
  for (const artifact of after) {
    const was = before.find((candidate) => candidate.id === artifact.id)
    if (!was || !isRunning(was)) continue
    if (artifact.status === "ready") {
      toast.success(
        intl.formatMessage(
          {
            id: "studio_artifact_ready_toast",
            defaultMessage: "{name} is ready",
          },
          { name: artifact.title }
        )
      )
    } else if (artifact.status === "failed") {
      // The raw error (often a multi-line HTTP exception) belongs in
      // the row's own Ctrl/Cmd-hover tooltip, not a toast.
      errorToast(
        intl.formatMessage(
          {
            id: "studio_artifact_failed_toast",
            defaultMessage: "{name} failed",
          },
          { name: artifact.title }
        ),
        {
          description: intl.formatMessage({
            id: "studio_artifact_failed_toast_body",
            defaultMessage:
              "This artifact couldn’t be generated. Retry it from the artifacts tab.",
          }),
        }
      )
    }
  }
}

/**
 * @param selectionToken Anything that changes when the models a format needs
 * change. The server decides which formats are available from what is
 * selected, and this hook holds that answer; without a dependency naming what
 * it was derived from, choosing a model leaves every tile disabled until the
 * page is reloaded. The value is never read, only compared.
 */
export function useStudio(workspaceId: number, selectionToken = "") {
  const queryClient = useQueryClient()
  const [isCreating, setIsCreating] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [dismissedLoadError, setDismissedLoadError] = useState<unknown>(null)

  const formatsQuery = useQuery({
    queryKey: studioKeys.formats(workspaceId, selectionToken),
    queryFn: ({ signal }) => listFormats(workspaceId, signal),
    // The tiles keep the last answer while a new selection is asked about.
    placeholderData: keepPreviousData,
  })
  const artifactsQuery = useQuery({
    queryKey: studioKeys.artifacts(workspaceId),
    queryFn: ({ signal }) => listArtifacts(workspaceId, signal),
    refetchInterval: (query) =>
      query.state.data?.some(isRunning) ? LOST_NOTICE_POLL_MS : false,
  })
  const artifacts = artifactsQuery.data ?? NO_ARTIFACTS

  // What the list held before this read, to tell which jobs it ended.
  const seen = useRef<Artifact[] | undefined>(undefined)
  useEffect(() => {
    const before = seen.current
    seen.current = artifactsQuery.data
    if (before && artifactsQuery.data) {
      announceFinished(before, artifactsQuery.data)
    }
  }, [artifactsQuery.data])

  // One event refreshes the list and everything read for an open artifact.
  useWorkspaceChanges(workspaceId, "artifacts", () => {
    const list = studioKeys.artifacts(workspaceId)
    // Cancelled first: a read still in flight with no answer yet would
    // otherwise be reused, and its older answer would land last.
    void queryClient
      .cancelQueries({ queryKey: list })
      .then(() => queryClient.invalidateQueries({ queryKey: list }))
    void queryClient.invalidateQueries({
      queryKey: studioKeys.openArtifacts(),
    })
  })

  // Only a list never read is an error to show: a failed reread keeps the
  // last answer, and the next event or the backstop reads again.
  const loadError =
    (artifactsQuery.data === undefined && artifactsQuery.error) ||
    (formatsQuery.data === undefined && formatsQuery.error) ||
    null
  const error =
    actionError ??
    (loadError && loadError !== dismissedLoadError
      ? messageFrom(loadError)
      : null)

  // A read that began before the action would carry the list from before it,
  // so it is cancelled before the action's result goes in.
  const setList = async (update: (current: Artifact[]) => Artifact[]) => {
    const list = studioKeys.artifacts(workspaceId)
    await queryClient.cancelQueries({ queryKey: list })
    queryClient.setQueryData<Artifact[]>(list, (current = []) =>
      update(current)
    )
  }
  const replace = (updated: Artifact) =>
    setList((current) =>
      current.map((artifact) =>
        artifact.id === updated.id ? updated : artifact
      )
    )

  const create = async (job: StudioJobCreate) => {
    setIsCreating(true)
    setActionError(null)
    try {
      const artifact = await createJob(workspaceId, job)
      await setList((current) => [artifact, ...current])
      return true
    } catch (cause) {
      setActionError(messageFrom(cause))
      return false
    } finally {
      setIsCreating(false)
    }
  }

  // Puts the artifact back to "pending"; the workspace's events follow it
  // the same way they do a freshly created one.
  const regenerate = async (artifactId: number) => {
    setActionError(null)
    try {
      await replace(await regenerateArtifact(artifactId))
    } catch (cause) {
      setActionError(messageFrom(cause))
    }
  }

  const cancel = async (artifactId: number) => {
    setActionError(null)
    try {
      await replace(await cancelArtifact(artifactId))
    } catch (cause) {
      setActionError(messageFrom(cause))
    }
  }

  const remove = async (artifactId: number) => {
    setActionError(null)
    try {
      await deleteArtifact(artifactId)
      await setList((current) => current.filter((a) => a.id !== artifactId))
    } catch (cause) {
      setActionError(messageFrom(cause))
    }
  }

  return {
    formats: formatsQuery.data ?? NO_FORMATS,
    artifacts,
    isLoading: formatsQuery.isPending || artifactsQuery.isPending,
    isCreating,
    error,
    create,
    regenerate,
    cancel,
    remove,
    clearError: () => {
      setActionError(null)
      setDismissedLoadError(loadError)
    },
  }
}

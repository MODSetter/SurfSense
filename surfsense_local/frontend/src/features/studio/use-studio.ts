import { useEffect, useRef, useState } from "react"
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
import { canRetry } from "./can-retry"

// The worker's notices are best-effort: one lost while a job runs would leave
// its row stale, so the list is still re-read now and then until none does.
const LOST_NOTICE_POLL_MS = 10_000

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

export function messageFrom(error: unknown) {
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

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timeout)
      reject(new DOMException("Aborted", "AbortError"))
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort)
      resolve()
    }, ms)
    signal.addEventListener("abort", onAbort, { once: true })
  })
}

/**
 * One read of the artifact list, or `null` once a newer read has started:
 * the first load, the event reload and the backstop each ask on their own, and
 * an older answer landing last would put a finished job back to running.
 */
async function readNewest(
  reads: { current: number },
  workspaceId: number,
  signal: AbortSignal
) {
  const read = ++reads.current
  const next = await listArtifacts(workspaceId, signal)
  return read === reads.current ? next : null
}

/**
 * @param selectionToken Anything that changes when the models a format needs
 * change. The server decides which formats are available from what is
 * selected, and this hook holds that answer; without a dependency naming what
 * it was derived from, choosing a model leaves every tile disabled until the
 * page is reloaded. The value is never read, only compared.
 */
export function useStudio(workspaceId: number, selectionToken = "") {
  const [formats, setFormats] = useState<StudioFormat[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollController = useRef<AbortController | null>(null)
  const changeController = useRef<AbortController | null>(null)
  const listReads = useRef(0)
  const hasRunning = artifacts.some(isRunning)
  // What the last read of the list held, to tell which jobs a new read ended.
  const artifactsRef = useRef(artifacts)
  useEffect(() => {
    artifactsRef.current = artifacts
  }, [artifacts])

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      listFormats(workspaceId, controller.signal),
      readNewest(listReads, workspaceId, controller.signal),
    ])
      .then(([nextFormats, nextArtifacts]) => {
        if (controller.signal.aborted) {
          return
        }
        setFormats(nextFormats)
        if (nextArtifacts) {
          setArtifacts(nextArtifacts)
        }
        setError(null)
        setIsLoading(false)
      })
      .catch((cause: unknown) => {
        if (!isAbort(cause) && !controller.signal.aborted) {
          setError(messageFrom(cause))
          setIsLoading(false)
        }
      })
    return () => {
      controller.abort()
      changeController.current?.abort()
    }
  }, [workspaceId, selectionToken])

  const showReread = (next: Artifact[]) => {
    for (const artifact of next) {
      const before = artifactsRef.current.find(
        (candidate) => candidate.id === artifact.id
      )
      if (!before || !isRunning(before)) continue
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
      } else if (
        artifact.status === "failed" &&
        // A script's own failure goes back to the agent that wrote it, and a
        // retry would only run the same script again: no toast to retry.
        canRetry(artifact)
      ) {
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
    // Now, not after the render: a second read landing first would otherwise
    // compare against the same running rows and toast them again.
    artifactsRef.current = next
    setArtifacts(next)
  }

  useWorkspaceChanges(workspaceId, "artifacts", () => {
    changeController.current?.abort()
    const controller = new AbortController()
    changeController.current = controller
    void readNewest(listReads, workspaceId, controller.signal)
      .then((next) => {
        if (next && changeController.current === controller) {
          showReread(next)
        }
      })
      .catch(() => {
        // The next change, or the re-read while a job runs, reloads.
      })
  })

  // The backstop for a lost notice, and only while a job runs.
  useEffect(() => {
    if (!hasRunning) {
      return
    }
    const controller = new AbortController()
    pollController.current?.abort()
    pollController.current = controller

    void (async () => {
      try {
        while (!controller.signal.aborted) {
          await wait(LOST_NOTICE_POLL_MS, controller.signal)
          const next = await readNewest(
            listReads,
            workspaceId,
            controller.signal
          )
          if (pollController.current !== controller) {
            return
          }
          if (!next) {
            continue
          }
          showReread(next)
          if (!next.some(isRunning)) {
            return
          }
        }
      } catch (cause) {
        if (!isAbort(cause) && pollController.current === controller) {
          setError(messageFrom(cause))
        }
      }
    })()

    return () => controller.abort()
  }, [hasRunning, workspaceId])

  const create = async (job: StudioJobCreate) => {
    setIsCreating(true)
    setError(null)
    try {
      const artifact = await createJob(workspaceId, job)
      setArtifacts((current) => [artifact, ...current])
      return true
    } catch (cause) {
      setError(messageFrom(cause))
      return false
    } finally {
      setIsCreating(false)
    }
  }

  // Puts the artifact back to "pending" in state; the workspace's events
  // follow it the same way they do a freshly created one.
  const regenerate = async (artifactId: number) => {
    setError(null)
    try {
      const updated = await regenerateArtifact(artifactId)
      setArtifacts((current) =>
        current.map((artifact) =>
          artifact.id === artifactId ? updated : artifact
        )
      )
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  const cancel = async (artifactId: number) => {
    setError(null)
    try {
      const updated = await cancelArtifact(artifactId)
      setArtifacts((current) =>
        current.map((artifact) =>
          artifact.id === artifactId ? updated : artifact
        )
      )
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  const remove = async (artifactId: number) => {
    setError(null)
    try {
      await deleteArtifact(artifactId)
      setArtifacts((current) => current.filter((a) => a.id !== artifactId))
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  return {
    formats,
    artifacts,
    isLoading,
    isCreating,
    error,
    create,
    regenerate,
    cancel,
    remove,
    clearError: () => setError(null),
  }
}

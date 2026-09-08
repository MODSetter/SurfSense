import { useEffect, useRef, useState } from "react"

import {
  createJob,
  deleteArtifact,
  listArtifacts,
  listFormats,
  readArtifact,
  type Artifact,
  type ArtifactDetail,
  type StudioFormat,
  type StudioJobCreate,
} from "./api"

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
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

export function useStudio(workspaceId: number, open: boolean) {
  const [formats, setFormats] = useState<StudioFormat[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selected, setSelected] = useState<ArtifactDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollController = useRef<AbortController | null>(null)
  const hasRunning = artifacts.some(isRunning)

  // Loaded only while the dialog is open, and reloaded each time it reopens.
  useEffect(() => {
    if (!open) {
      return
    }
    const controller = new AbortController()
    // isLoading defaults to true, so the first open shows a skeleton; reopening
    // keeps the last data on screen and refreshes it (stale-while-revalidate).
    void Promise.all([
      listFormats(workspaceId, controller.signal),
      listArtifacts(workspaceId, controller.signal),
    ])
      .then(([nextFormats, nextArtifacts]) => {
        if (controller.signal.aborted) {
          return
        }
        setFormats(nextFormats)
        setArtifacts(nextArtifacts)
        setError(null)
        setIsLoading(false)
      })
      .catch((cause: unknown) => {
        if (!isAbort(cause) && !controller.signal.aborted) {
          setError(messageFrom(cause))
          setIsLoading(false)
        }
      })
    return () => controller.abort()
  }, [workspaceId, open])

  // While a job runs, poll the list until it settles — the same freshness path
  // the sources panel uses.
  useEffect(() => {
    if (!open || !hasRunning) {
      return
    }
    const controller = new AbortController()
    pollController.current?.abort()
    pollController.current = controller

    void (async () => {
      try {
        while (!controller.signal.aborted) {
          await wait(1500, controller.signal)
          const next = await listArtifacts(workspaceId, controller.signal)
          if (pollController.current !== controller) {
            return
          }
          setArtifacts(next)
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
  }, [open, hasRunning, workspaceId])

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

  const open_ = async (artifactId: number) => {
    setError(null)
    try {
      setSelected(await readArtifact(artifactId))
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  const remove = async (artifactId: number) => {
    setError(null)
    try {
      await deleteArtifact(artifactId)
      setArtifacts((current) => current.filter((a) => a.id !== artifactId))
      setSelected((current) => (current?.id === artifactId ? null : current))
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  return {
    formats,
    artifacts,
    selected,
    isLoading,
    isCreating,
    error,
    create,
    openArtifact: open_,
    closeArtifact: () => setSelected(null),
    remove,
    clearError: () => setError(null),
  }
}

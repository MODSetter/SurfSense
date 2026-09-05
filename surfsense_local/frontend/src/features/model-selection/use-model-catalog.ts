import { useCallback, useEffect, useRef, useState } from "react"

import { getProviderCatalog, pullModel, type CatalogEntry } from "./api"
import type { PullProgress } from "./pull-stream"

export type CatalogRow = CatalogEntry & { provider: string }

export type PullState =
  | { status: "idle" }
  | {
      status: "pulling"
      percent: number | null
      label: string
      detail: string | null
    }
  | { status: "error"; message: string }
  | { status: "done" }

const gb = (bytes: number) => (bytes / 1e9).toFixed(1)

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

type CatalogState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rows: CatalogRow[] }

const rowKey = (row: { provider: string; name: string }) =>
  `${row.provider}\0${row.name}`

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

export function useModelCatalog(providers: string[], onPulled: () => void) {
  const [state, setState] = useState<CatalogState>({ status: "loading" })
  const [pulls, setPulls] = useState<Record<string, PullState>>({})
  const controllers = useRef(new Map<string, AbortController>())
  const providerKey = providers.join(",")

  useEffect(() => {
    const names = providerKey ? providerKey.split(",") : []
    const controller = new AbortController()

    // Promise.all([]) resolves to no rows, so state is only set asynchronously.
    Promise.all(
      names.map(async (provider) => {
        const entries = await getProviderCatalog(provider, controller.signal)
        return entries.map((entry) => ({ ...entry, provider }))
      })
    )
      .then((groups) => {
        if (!controller.signal.aborted) {
          setState({ status: "ready", rows: groups.flat() })
        }
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) {
          setState({ status: "error", message: messageFrom(error) })
        }
      })

    return () => controller.abort()
  }, [providerKey])

  useEffect(() => {
    const inFlight = controllers.current
    return () => {
      for (const controller of inFlight.values()) {
        controller.abort()
      }
      inFlight.clear()
    }
  }, [])

  const pull = useCallback(
    (row: CatalogRow) => {
      const key = rowKey(row)
      controllers.current.get(key)?.abort()
      const controller = new AbortController()
      controllers.current.set(key, controller)
      setPulls((current) => ({
        ...current,
        [key]: {
          status: "pulling",
          percent: null,
          label: "Starting",
          detail: null,
        },
      }))

      // Ollama pulls a model as several layers, each starting at 0 bytes. Sum
      // them by layer so the reported percent climbs once, never resetting.
      const layers = new Map<string, { completed: number; total: number }>()
      const view = (progress: PullProgress): PullState => {
        if (progress.total > 0) {
          layers.set(progress.status, {
            completed: progress.completed,
            total: progress.total,
          })
        }
        let done = 0
        let size = 0
        for (const layer of layers.values()) {
          done += layer.completed
          size += layer.total
        }
        return {
          status: "pulling",
          percent:
            size > 0 ? Math.min(100, Math.round((done / size) * 100)) : null,
          label:
            progress.total > 0 ? "Downloading" : titleCase(progress.status),
          detail: size > 0 ? `${gb(done)} / ${gb(size)} GB` : null,
        }
      }

      void pullModel(
        row.provider,
        row.name,
        (progress) =>
          setPulls((current) => ({ ...current, [key]: view(progress) })),
        controller.signal
      )
        .then(() => {
          controllers.current.delete(key)
          setPulls((current) => ({ ...current, [key]: { status: "done" } }))
          setState((current) =>
            current.status === "ready"
              ? {
                  status: "ready",
                  rows: current.rows.map((entry) =>
                    rowKey(entry) === key
                      ? { ...entry, installed: true }
                      : entry
                  ),
                }
              : current
          )
          onPulled()
        })
        .catch((error: unknown) => {
          controllers.current.delete(key)
          if (!isAbort(error)) {
            setPulls((current) => ({
              ...current,
              [key]: { status: "error", message: messageFrom(error) },
            }))
          }
        })
    },
    [onPulled]
  )

  return { state, pulls, pull, rowKey }
}

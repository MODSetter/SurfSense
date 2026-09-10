import { useEffect, useState } from "react"

import { DotIcon } from "@/components/ui/icons"
import { Skeleton } from "@/components/ui/skeleton"

import {
  type Connection,
  getConnections,
  getSelection,
  type ModelSelection,
} from "./api"

// `null` connections mean the list is still loading or failed to load, which is
// not the same as a connection that no longer exists.
function sourceOf(selection: ModelSelection, connections: Connection[] | null) {
  if (selection.provider === "ollama") return "Local"
  if (connections === null) return null
  return (
    connections.find((connection) => connection.id === selection.connection_id)
      ?.label ?? "Unknown connection"
  )
}

function Role({
  label,
  selection,
  connections,
  loading,
  fallback,
}: {
  label: string
  selection: ModelSelection | null
  connections: Connection[] | null
  loading?: boolean
  fallback: string
}) {
  const source = selection === null ? null : sourceOf(selection, connections)

  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className="flex min-w-0 items-center gap-1"
        aria-busy={loading || undefined}
      >
        {loading ? (
          <Skeleton className="h-5 w-20" />
        ) : selection === null ? (
          <span className="text-muted-foreground">{fallback}</span>
        ) : (
          <>
            <span className="truncate">{selection.name}</span>
            {source === null ? null : (
              <>
                <DotIcon
                  aria-hidden="true"
                  className="size-3 shrink-0 text-muted-foreground"
                />
                <span className="shrink-0 text-muted-foreground">{source}</span>
              </>
            )}
          </>
        )}
      </dd>
    </>
  )
}

type ImageState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; image: ModelSelection | null; connections: Connection[] }

// Chat and image are one global row each, so they belong above the provider
// tabs rather than on every connection card.
export function SelectedRoles({
  generation,
  generationLoading,
}: {
  generation: ModelSelection | null
  generationLoading: boolean
}) {
  const [state, setState] = useState<ImageState>({ status: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      getSelection("image_generation", controller.signal),
      getConnections(controller.signal),
    ])
      .then(([image, connections]) => {
        if (!controller.signal.aborted) {
          setState({ status: "ready", image, connections })
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "error" })
      })
    return () => controller.abort()
  }, [])

  const connections = state.status === "ready" ? state.connections : null

  return (
    <section
      data-slot="selected-roles"
      className="rounded-lg bg-muted/50 p-3"
      aria-label="Models in use"
    >
      <dl className="grid gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[3.5rem_minmax(0,1fr)]">
        <Role
          label="Chat:"
          selection={generation}
          connections={connections}
          loading={generationLoading}
          fallback="Not assigned"
        />
        <Role
          label="Image:"
          selection={state.status === "ready" ? state.image : null}
          connections={connections}
          loading={state.status === "loading"}
          fallback={state.status === "error" ? "Unavailable" : "Not assigned"}
        />
      </dl>
    </section>
  )
}

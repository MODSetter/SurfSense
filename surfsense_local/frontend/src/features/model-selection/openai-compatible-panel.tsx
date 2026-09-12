import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"

import {
  getConnections,
  getSelection,
  type Connection,
  type ModelSelection,
} from "./api"
import { ConnectionCard } from "./connection-card"
import { ConnectionForm } from "./connection-form"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not load connections"
}

export function OpenAICompatiblePanel({
  disabled,
  onGenerationSelected,
  onGenerationUnavailable,
  onChanged,
}: {
  disabled: boolean
  onGenerationSelected: (selection: ModelSelection) => void
  onGenerationUnavailable?: () => void
  onChanged: () => void
}) {
  const [connections, setConnections] = useState<Connection[] | null>(null)
  const [generation, setGeneration] = useState<ModelSelection | null>(null)
  const [image, setImage] = useState<ModelSelection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Connection | "new" | null>(null)

  const load = () => {
    const controller = new AbortController()
    void Promise.all([
      getConnections(controller.signal),
      getSelection("generation", controller.signal),
      getSelection("image_generation", controller.signal),
    ])
      .then(([nextConnections, nextGeneration, nextImage]) => {
        setConnections(nextConnections)
        setGeneration(nextGeneration)
        setImage(nextImage)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
    return () => controller.abort()
  }

  useEffect(load, [])

  const changed = () => {
    load()
    onChanged()
  }

  if (connections === null && !error) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Loading connections…
      </p>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">OpenAI-compatible connections</h2>
          <p className="text-sm text-muted-foreground">
            Add separate chat and image endpoints, or use one gateway for both.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={disabled}
          onClick={() => setEditing("new")}
        >
          <PlusIcon /> Add connection
        </Button>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <ScrollShadow className="min-h-0 flex-1">
        <div className="space-y-3 pt-px pr-3 pb-3 pl-px">
          {connections?.length ? (
            connections.map((connection) => (
              <ConnectionCard
                key={connection.id}
                connection={connection}
                generationSelection={generation}
                imageSelection={image}
                disabled={disabled}
                onEdit={() => setEditing(connection)}
                onChanged={changed}
                onGenerationUnavailable={onGenerationUnavailable}
                onGenerationSelected={(selection) => {
                  setGeneration(selection)
                  onGenerationSelected(selection)
                }}
              />
            ))
          ) : (
            <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              No remote connections yet.
            </p>
          )}
        </div>
      </ScrollShadow>
      {editing ? (
        <ConnectionForm
          key={editing === "new" ? "new" : editing.id}
          open
          connection={editing === "new" ? undefined : editing}
          onOpenChange={(open) => !open && setEditing(null)}
          onSaved={changed}
        />
      ) : null}
    </div>
  )
}

import { useId, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { ChevronRightIcon, DotIcon, SearchIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

import { SLOT_NAMES, type ModelType } from "../../model-type"
import type { ModelSelection } from "../../selection/api"
import { useSelection } from "../../selection/use-selection"
import type { Connection } from "../connections/api"
import { DisconnectButton } from "../connections/disconnect-button"
import type { ConnectionModel } from "./api"
import { TryModelDialog } from "./try-model-dialog"
import { useConnectionModels } from "./use-connection-models"

const TYPE_LABELS: Record<ModelType, string> = {
  text_gen: "Text generation",
  image_gen: "Image generation",
  image_edit: "Image editing",
  video_gen: "Video generation",
  audio_gen: "Audio generation",
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not list models"
}

/** One server, and the models on it that can fill this section's slot. */
export function ServerModels({
  connection,
  modelType,
  disabled,
  defaultOpen = false,
  onEdit,
  onSelected,
  onChatCleared,
}: {
  connection: Connection
  modelType: ModelType
  disabled: boolean
  defaultOpen?: boolean
  onEdit: () => void
  onSelected?: (selection: ModelSelection) => void
  onChatCleared?: () => void
}) {
  const headingId = useId()
  const listId = useId()
  const manualId = useId()
  const [open, setOpen] = useState(defaultOpen)
  const [search, setSearch] = useState("")
  const [manualName, setManualName] = useState("")
  const [trying, setTrying] = useState<{
    model: ConnectionModel
    unlisted: boolean
  } | null>(null)
  const models = useConnectionModels(connection.id, open)
  const selection = useSelection(modelType)
  const slot = SLOT_NAMES[modelType]

  const inUse = (name: string) =>
    selection.data?.connection_id === connection.id &&
    selection.data.name === name
  const query = search.trim().toLocaleLowerCase()
  const candidates = (models.data ?? []).filter(
    (model) =>
      model.selectable_for.includes(modelType) &&
      model.name.toLocaleLowerCase().includes(query)
  )

  const tryManual = () => {
    const name = manualName.trim()
    if (!name) return
    setTrying({
      unlisted: true,
      model: {
        connection_id: connection.id,
        connection_label: connection.label,
        name,
        types: [],
        capability_source: "unknown",
        // Typed by hand, so nothing vouches for it; the backend checks it when
        // it is assigned.
        selectable_for: [modelType],
      },
    })
  }

  const current =
    selection.data?.connection_id === connection.id ? selection.data.name : null

  return (
    <section className="flex flex-col gap-2" aria-labelledby={headingId}>
      <div className="flex items-center justify-between gap-3">
        <h3
          id={headingId}
          className="flex min-w-0 items-center gap-1 text-xs font-medium text-muted-foreground"
        >
          <span className="shrink-0">{connection.label}</span>
          <DotIcon aria-hidden="true" className="size-3 shrink-0" />
          <span className="truncate font-normal">{connection.base_url}</span>
        </h3>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={disabled}
            aria-label={`Edit ${connection.label}`}
            onClick={onEdit}
          >
            Edit
          </Button>
          <DisconnectButton
            connection={connection}
            disabled={disabled}
            onChatCleared={onChatCleared}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        {current && !open ? (
          // Its row is inside the closed list, so the model in use is said here.
          <div className="flex items-center justify-between gap-3 border-b px-3 py-2.5">
            <span className="truncate text-sm font-medium">{current}</span>
            <Button type="button" size="sm" variant="outline" disabled>
              In use
            </Button>
          </div>
        ) : null}
        <button
          type="button"
          aria-expanded={open}
          aria-controls={listId}
          disabled={disabled}
          className="flex w-full items-center gap-1.5 px-3 py-2.5 text-left text-sm text-muted-foreground transition-colors hover:bg-muted/30 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset disabled:pointer-events-none disabled:opacity-50"
          onClick={() => setOpen((value) => !value)}
        >
          <ChevronRightIcon
            aria-hidden="true"
            className={cn(
              "size-4 transition-transform motion-reduce:transition-none",
              open && "rotate-90"
            )}
          />
          {open ? `Hide ${slot} models` : `Show ${slot} models`}
        </button>

        {open ? (
          <div id={listId} className="flex flex-col gap-3 border-t px-3 py-3">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                autoFocus
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={`Search ${slot} models`}
                aria-label={`Search models from ${connection.label}`}
                className="pl-9"
              />
            </div>

            {models.isPending ? (
              <p
                className="flex items-center gap-2 py-4 text-sm text-muted-foreground"
                role="status"
                aria-label="Loading models"
              >
                <Spinner /> Loading models…
              </p>
            ) : models.isError ? (
              <div className="flex flex-col items-start gap-2 py-2 text-sm">
                <p className="text-destructive" role="alert">
                  {messageFrom(models.error)}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void models.refetch()}
                >
                  Retry
                </Button>
              </div>
            ) : candidates.length ? (
              <ScrollShadow
                className="overflow-hidden rounded-lg border"
                viewportClassName="max-h-80"
              >
                <ul
                  className="divide-y"
                  aria-label={`${slot} models on ${connection.label}`}
                >
                  {candidates.map((model) => (
                    <li
                      key={model.name}
                      className="flex items-center justify-between gap-3 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {model.name}
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {model.capability_source === "unknown" ? (
                            <Badge variant="outline">Capability unknown</Badge>
                          ) : (
                            model.types.map((type) => (
                              <Badge key={type} variant="secondary">
                                {TYPE_LABELS[type]}
                              </Badge>
                            ))
                          )}
                        </div>
                      </div>
                      {inUse(model.name) ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled
                        >
                          In use
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          disabled={disabled}
                          aria-label={`Use ${model.name}`}
                          onClick={() => setTrying({ model, unlisted: false })}
                        >
                          Use
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </ScrollShadow>
            ) : (
              <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                {models.data?.length
                  ? `No ${slot} models match. Try another search, or type an exact ID below.`
                  : "This server listed no models. Type an exact ID below."}
              </p>
            )}

            <Field>
              <FieldLabel htmlFor={manualId}>Exact model ID</FieldLabel>
              <div className="flex gap-2">
                <Input
                  id={manualId}
                  value={manualName}
                  onChange={(event) => setManualName(event.target.value)}
                  placeholder="provider/model-id"
                  disabled={disabled}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={disabled || !manualName.trim()}
                  onClick={tryManual}
                >
                  Use for {slot}
                </Button>
              </div>
              <FieldDescription>
                For a model this server does not list.
              </FieldDescription>
            </Field>
          </div>
        ) : null}
      </div>

      {trying ? (
        <TryModelDialog
          modelType={modelType}
          model={trying.model}
          unlisted={trying.unlisted}
          onClose={() => setTrying(null)}
          onSelected={onSelected}
        />
      ) : null}
    </section>
  )
}

import { useId, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import {
  ChevronRightIcon,
  DotIcon,
  SearchIcon,
  XIcon,
} from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import type { ModelType } from "../../model-type"
import type { ModelSelection } from "../../selection/api"
import { useSelection } from "../../selection/use-selection"
import type { Connection } from "../connections/api"
import { DisconnectButton } from "../connections/disconnect-button"
import type { ConnectionModel } from "./api"
import { TryModelDialog } from "./try-model-dialog"
import { useConnectionModels } from "./use-connection-models"

const TYPE_LABELS: Record<ModelType, () => string> = {
  text_gen: () =>
    intl.formatMessage({
      id: "models_server_models_type_text_gen_label",
      defaultMessage: "Text generation",
    }),
  image_gen: () =>
    intl.formatMessage({
      id: "models_server_models_type_image_gen_label",
      defaultMessage: "Image generation",
    }),
  image_edit: () =>
    intl.formatMessage({
      id: "models_server_models_type_image_edit_label",
      defaultMessage: "Image editing",
    }),
  video_gen: () =>
    intl.formatMessage({
      id: "models_server_models_type_video_gen_label",
      defaultMessage: "Video generation",
    }),
  audio_gen: () =>
    intl.formatMessage({
      id: "models_server_models_type_audio_gen_label",
      defaultMessage: "Audio generation",
    }),
}

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_server_models_list_error",
        defaultMessage: "Could not list models",
      })
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
  /** Opens on its models when it first appears: a server just added. */
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
  const searchRef = useRef<HTMLInputElement>(null)
  const [manualName, setManualName] = useState("")
  const [trying, setTrying] = useState<{
    model: ConnectionModel
    unlisted: boolean
  } | null>(null)
  const models = useConnectionModels(connection.id, open)
  const selection = useSelection(modelType)

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
            aria-label={intl.formatMessage(
              {
                id: "models_server_models_edit_aria",
                defaultMessage: "Edit {server}",
              },
              {
                server: connection.label,
              }
            )}
            onClick={onEdit}
          >
            {intl.formatMessage({
              id: "models_server_models_edit_button",
              defaultMessage: "Edit",
            })}
          </Button>
          <DisconnectButton
            connection={connection}
            disabled={disabled}
            onChatCleared={onChatCleared}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        {current ? (
          // Kept while the list is open too, so opening it only adds below.
          <div className="flex items-center justify-between gap-3 border-b px-3 py-2.5">
            <span className="truncate text-sm font-medium">{current}</span>
            <Button type="button" size="sm" variant="outline" disabled>
              {intl.formatMessage({
                id: "models_server_models_current_in_use_button",
                defaultMessage: "In use",
              })}
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
          {open
            ? intl.formatMessage(
                {
                  id: "models_server_models_hide_button",
                  defaultMessage:
                    "{slot, select, text_gen {Hide chat models} image_gen {Hide image models} image_edit {Hide image editing models} video_gen {Hide video models} audio_gen {Hide audio models} other {Hide models}}",
                },
                { slot: modelType }
              )
            : intl.formatMessage(
                {
                  id: "models_server_models_show_button",
                  defaultMessage:
                    "{slot, select, text_gen {Show chat models} image_gen {Show image models} image_edit {Show image editing models} video_gen {Show video models} audio_gen {Show audio models} other {Show models}}",
                },
                { slot: modelType }
              )}
        </button>

        {open ? (
          <div id={listId} className="flex flex-col gap-3 border-t px-3 py-3">
            <InputGroup>
              <InputGroupAddon>
                <SearchIcon />
              </InputGroupAddon>
              <InputGroupInput
                ref={searchRef}
                autoFocus
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={intl.formatMessage(
                  {
                    id: "models_server_models_search_placeholder",
                    defaultMessage:
                      "{slot, select, text_gen {Search chat models} image_gen {Search image models} image_edit {Search image editing models} video_gen {Search video models} audio_gen {Search audio models} other {Search models}}",
                  },
                  {
                    slot: modelType,
                  }
                )}
                aria-label={intl.formatMessage(
                  {
                    id: "models_server_models_search_aria",
                    defaultMessage: "Search models from {server}",
                  },
                  {
                    server: connection.label,
                  }
                )}
              />
              {search ? (
                <InputGroupAddon align="inline-end">
                  <InputGroupButton
                    size="icon-xs"
                    aria-label={intl.formatMessage({
                      id: "models_server_models_search_clear_aria",
                      defaultMessage: "Clear search",
                    })}
                    onClick={() => {
                      setSearch("")
                      searchRef.current?.focus()
                    }}
                  >
                    <XIcon />
                  </InputGroupButton>
                </InputGroupAddon>
              ) : null}
            </InputGroup>

            {models.isPending ? (
              <p
                className="flex items-center gap-2 py-4 text-sm text-muted-foreground"
                role="status"
                aria-label={intl.formatMessage({
                  id: "models_server_models_loading_aria",
                  defaultMessage: "Loading models",
                })}
              >
                <Spinner />{" "}
                {intl.formatMessage({
                  id: "models_server_models_loading_status",
                  defaultMessage: "Loading models…",
                })}
              </p>
            ) : models.isError ? (
              <div className="flex items-center justify-between gap-3 py-2 text-sm">
                <p
                  className="min-w-0 text-pretty text-destructive"
                  role="alert"
                >
                  {messageFrom(models.error)}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  onClick={() => void models.refetch()}
                >
                  {intl.formatMessage({
                    id: "models_server_models_retry_button",
                    defaultMessage: "Retry",
                  })}
                </Button>
              </div>
            ) : candidates.length ? (
              <ScrollFade
                className="overflow-hidden rounded-lg border"
                viewportClassName="max-h-80"
              >
                <ul
                  className="divide-y"
                  aria-label={intl.formatMessage(
                    {
                      id: "models_server_models_list_aria",
                      defaultMessage:
                        "{slot, select, text_gen {chat models on {server}} image_gen {image models on {server}} image_edit {image editing models on {server}} video_gen {video models on {server}} audio_gen {audio models on {server}} other {models on {server}}}",
                    },
                    {
                      slot: modelType,
                      server: connection.label,
                    }
                  )}
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
                            <Badge variant="outline">
                              {intl.formatMessage({
                                id: "models_server_models_capability_unknown_label",
                                defaultMessage: "Capability unknown",
                              })}
                            </Badge>
                          ) : (
                            model.types.map((type) => (
                              <Badge key={type} variant="secondary">
                                {TYPE_LABELS[type]()}
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
                          {intl.formatMessage({
                            id: "models_server_models_list_in_use_button",
                            defaultMessage: "In use",
                          })}
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          disabled={disabled}
                          aria-label={intl.formatMessage(
                            {
                              id: "models_server_models_use_aria",
                              defaultMessage: "Use {model}",
                            },
                            {
                              model: model.name,
                            }
                          )}
                          onClick={() => setTrying({ model, unlisted: false })}
                        >
                          {intl.formatMessage({
                            id: "models_server_models_use_button",
                            defaultMessage: "Use",
                          })}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </ScrollFade>
            ) : (
              <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                {models.data?.length
                  ? intl.formatMessage(
                      {
                        id: "models_server_models_no_match_empty",
                        defaultMessage:
                          "{slot, select, text_gen {No chat models match. Type an exact ID below.} image_gen {No image models match. Type an exact ID below.} image_edit {No image editing models match. Type an exact ID below.} video_gen {No video models match. Type an exact ID below.} audio_gen {No audio models match. Type an exact ID below.} other {No models match. Type an exact ID below.}}",
                      },
                      {
                        slot: modelType,
                      }
                    )
                  : intl.formatMessage({
                      id: "models_server_models_none_listed_empty",
                      defaultMessage:
                        "This server listed no models. Type an exact ID below.",
                    })}
              </p>
            )}

            <Field>
              <FieldLabel htmlFor={manualId}>
                {intl.formatMessage({
                  id: "models_server_models_manual_id_label",
                  defaultMessage: "Exact model ID",
                })}
              </FieldLabel>
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
                  {intl.formatMessage(
                    {
                      id: "models_server_models_manual_use_button",
                      defaultMessage:
                        "{slot, select, text_gen {Use for chat} image_gen {Use for image} image_edit {Use for image editing} video_gen {Use for video} audio_gen {Use for audio} other {Use}}",
                    },
                    {
                      slot: modelType,
                    }
                  )}
                </Button>
              </div>
              <FieldDescription>
                {intl.formatMessage({
                  id: "models_server_models_manual_id_body",
                  defaultMessage: "For a model this server does not list.",
                })}
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

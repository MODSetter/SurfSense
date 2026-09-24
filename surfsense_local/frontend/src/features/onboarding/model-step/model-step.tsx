import { Fragment, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ArrowLeftIcon, ComputerIcon, DotIcon } from "@/components/ui/icons"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import type { LocalBuild, LocalRow } from "@/features/models/local/chat/api"
import { ConnectionDialog } from "@/features/models/remote/connections/connection-dialog"
import { useConnections } from "@/features/models/remote/connections/use-connections"
import { useSelect } from "@/features/models/selection/use-selection"
import { DeleteModelDialog } from "@/features/models/your-models/delete-model-dialog"
import type { YourModelRow } from "@/features/models/your-models/your-model-row"
import { intl } from "@/i18n/intl"

import { OfflineState } from "../offline-state"
import { HuggingFaceSearch } from "./hugging-face-search"
import { leadBuild, localChoices } from "./local-choices"
import { LocalModelList } from "./local-model-list"
import { ModelReady } from "./model-ready"
import { ServerOption } from "./server-option"
import { ServerPath } from "./server-path"
import { LOCAL_PROVIDER, type OnboardingSlot } from "./slot"
import { onboardingInstalls } from "./use-onboarding-install"
import { slotDeletes } from "./use-slot-delete"
import { slotModels } from "./use-slot-models"

const COPY: Record<
  OnboardingSlot,
  {
    title: () => string
    description: () => string
    noLocal: () => string
    /** Hugging Face search, for llama.cpp's GGUF models only. */
    searchable: boolean
  }
> = {
  text_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_title",
        defaultMessage: "Choose a text generation model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_body",
        defaultMessage:
          "Answers you in chat. Run one on this computer so your chats stay private, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_chat_step_no_local_empty",
        defaultMessage:
          "No tested model can run on this computer. Use a server instead.",
      }),
    searchable: true,
  },
  image_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_image_step_title",
        defaultMessage: "Choose an image generation model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_image_step_body",
        defaultMessage:
          "Creates images for you. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_image_step_no_local_empty",
        defaultMessage:
          "Image models cannot run on this computer. Use a server instead.",
      }),
    // sd.cpp has no search: its models are the few the catalog ships.
    searchable: false,
  },
  audio_gen: {
    title: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_title",
        defaultMessage: "Choose an audio model",
      }),
    description: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_body",
        defaultMessage:
          "Creates podcasts for you. Run one on this computer, or use one from a server.",
      }),
    noLocal: () =>
      intl.formatMessage({
        id: "onboarding_audio_step_no_local_empty",
        defaultMessage:
          "Audio models cannot run on this computer. Use a server instead.",
      }),
    // Nor has audio.cpp.
    searchable: false,
  },
}

/**
 * One onboarding step for one slot. Every local model is listed at once, the
 * recommended one first, with a server one line below: nothing is hidden
 * behind a click. The step is done once the slot has a model.
 */
export function ModelStep({
  modelType,
  nextLabel,
  finishing = false,
  error = null,
  onBack,
  onNext,
  onSkip,
}: {
  modelType: OnboardingSlot
  nextLabel: string
  finishing?: boolean
  error?: string | null
  /** Absent on the first step: the welcome is not somewhere to go back to. */
  onBack?: () => void
  onNext: () => void
  /** Present only where the slot is optional. */
  onSkip?: () => void
}) {
  const copy = COPY[modelType]
  const models = slotModels[modelType]()
  const useInstall = onboardingInstalls[modelType]
  const { installState, install, cancelInstall } = useInstall()
  const select = useSelect(modelType)
  const remove = slotDeletes[modelType]()
  const connections = useConnections()
  const [onServer, setOnServer] = useState(false)
  // With nothing connected yet there is no server page to show: Connect
  // opens the dialog here, and a server saved from it opens on its models.
  const [connecting, setConnecting] = useState(false)
  const [openServerId, setOpenServerId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<{
    removeId: string
    row: YourModelRow
  } | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const installing = installState.status === "installing"
  const busy = installing || select.isPending || remove.isPending || finishing
  const choices = localChoices(models.rows)

  // Neither a download nor Use moves the page: progress and "In use" show on
  // the row that asked for them.
  const download = (row: LocalRow) => {
    const build = leadBuild(row)
    if (build) downloadBuild(build, row.name)
  }

  // A searched build installs through the same call: the id is opaque.
  const downloadBuild = (build: LocalBuild, label: string) => {
    if (busy) return
    void install(build.catalog_id, label)
  }

  const use = (row: LocalRow) => {
    const build = leadBuild(row)
    if (!build?.installed_as || busy) return
    void select
      .mutateAsync({
        target: {
          provider: LOCAL_PROVIDER[modelType],
          connection_id: null,
          name: build.installed_as,
        },
      })
      .catch(() => undefined)
  }

  const askDelete = (row: LocalRow) => {
    const build = leadBuild(row)
    if (!build?.installed_as) return
    setDeleteError(null)
    setDeleting({
      removeId: build.installed_as,
      row: {
        key: build.installed_as,
        name: row.name,
        selected: build.selected,
        badges: [],
        note: null,
        target: null,
        removeId: build.installed_as,
      },
    })
  }

  const confirmDelete = () => {
    if (!deleting) return
    setDeleteError(null)
    remove
      .mutateAsync(deleting.removeId)
      .then(() => setDeleting(null))
      .catch((cause: unknown) =>
        setDeleteError(
          cause instanceof Error
            ? cause.message
            : intl.formatMessage({
                id: "onboarding_model_step_delete_error",
                defaultMessage: "Could not delete the model",
              })
        )
      )
  }

  const body = () => {
    if (models.error) return <OfflineState message={models.error.message} />
    if (models.isPending) return null
    if (onServer) {
      return (
        // Choosing a model stays here, as in Settings: its group marks it
        // "In use", and the footer says which.
        <ServerPath modelType={modelType} openServerId={openServerId} />
      )
    }
    return (
      <div className="flex flex-col gap-5">
        <section
          className="flex flex-col gap-3"
          aria-label={intl.formatMessage({
            id: "onboarding_model_step_local_aria",
            defaultMessage: "On this computer",
          })}
        >
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              <ComputerIcon
                aria-hidden="true"
                className="size-4 text-muted-foreground"
              />
              {intl.formatMessage({
                id: "onboarding_model_step_local_title",
                defaultMessage: "On this computer",
              })}
            </h3>
            {models.hardware ? (
              <p className="flex items-center text-xs text-muted-foreground">
                {models.hardware.map((part, index) => (
                  <Fragment key={part}>
                    {index > 0 ? (
                      <DotIcon aria-hidden="true" className="size-3 shrink-0" />
                    ) : null}
                    <span>{part}</span>
                  </Fragment>
                ))}
              </p>
            ) : null}
          </div>
          {choices.length ? (
            <LocalModelList
              rows={choices}
              installState={installState}
              disabled={busy}
              onDownload={download}
              onUse={use}
              onCancel={cancelInstall}
              onDelete={askDelete}
            />
          ) : (
            <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
              {copy.noLocal()}
            </p>
          )}
          {copy.searchable ? (
            <HuggingFaceSearch
              installState={installState}
              disabled={busy}
              onInstall={downloadBuild}
              onCancel={cancelInstall}
            />
          ) : null}
        </section>

        <Separator />

        <ServerOption
          connections={connections.data ?? []}
          onOpen={() =>
            connections.data?.length ? setOnServer(true) : setConnecting(true)
          }
        />
      </div>
    )
  }

  return (
    <Card className="h-full min-h-0 w-full gap-0 [--card-spacing:--spacing(6)]">
      <CardHeader className="mb-(--card-spacing)">
        <CardTitle>
          <h1 className="font-heading text-xl text-balance">{copy.title()}</h1>
        </CardTitle>
        <CardDescription className="max-w-lg text-pretty">
          {copy.description()}
        </CardDescription>
        {onSkip ? (
          <CardAction>
            <Badge variant="secondary">
              {intl.formatMessage({
                id: "onboarding_model_step_optional_label",
                defaultMessage: "Optional",
              })}
            </Badge>
          </CardAction>
        ) : null}
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 px-0">
        {onServer ? (
          <div className="px-(--card-spacing)">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="-ml-2 text-muted-foreground"
              onClick={() => setOnServer(false)}
            >
              <ArrowLeftIcon data-icon="inline-start" />
              {intl.formatMessage({
                id: "onboarding_model_step_back_to_models_button",
                defaultMessage: "Back to models",
              })}
            </Button>
          </div>
        ) : null}
        <ScrollShadow
          className="min-h-0 flex-1"
          viewportClassName="px-(--card-spacing) pb-1"
        >
          {body()}
        </ScrollShadow>
        {select.isError ? (
          <p className="px-(--card-spacing) text-sm text-destructive">
            {select.error.message}
          </p>
        ) : null}
        {error ? (
          <p
            className="px-(--card-spacing) text-sm text-destructive"
            aria-live="polite"
          >
            {error}
          </p>
        ) : null}
      </CardContent>

      <CardFooter className="justify-between gap-3 border-t py-4">
        {onBack ? (
          <Button type="button" variant="ghost" onClick={onBack}>
            {intl.formatMessage({
              id: "onboarding_model_step_back_button",
              defaultMessage: "Back",
            })}
          </Button>
        ) : null}
        <div className="ml-auto flex min-w-0 items-center gap-2">
          {/* Beside the button it unlocks: why Continue is now enabled. */}
          {models.inUse && !models.error ? (
            <div className="mr-2 min-w-0">
              <ModelReady inUse={models.inUse} />
            </div>
          ) : null}
          {onSkip ? (
            <Button
              type="button"
              variant="outline"
              disabled={finishing}
              onClick={onSkip}
            >
              {intl.formatMessage({
                id: "onboarding_model_step_skip_button",
                defaultMessage: "Skip",
              })}
            </Button>
          ) : null}
          <Button
            type="button"
            disabled={!models.inUse || busy}
            onClick={onNext}
          >
            {finishing ? <Spinner data-icon="inline-start" /> : null}
            {nextLabel}
          </Button>
        </div>
      </CardFooter>
      <ConnectionDialog
        open={connecting}
        onOpenChange={setConnecting}
        onCreated={(connection) => {
          setOpenServerId(connection.id)
          setOnServer(true)
        }}
      />
      <DeleteModelDialog
        row={deleting?.row ?? null}
        pending={remove.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </Card>
  )
}

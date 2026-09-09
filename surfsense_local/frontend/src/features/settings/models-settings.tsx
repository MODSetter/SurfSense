import { useState } from "react"

import { CircleAlertIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { modelKey, type ModelSelection } from "@/features/model-selection/api"
import { ModelSelectionContent } from "@/features/model-selection/model-selection-content"
import { useModelSelection } from "@/features/model-selection/use-model-selection"

import { SettingsSection } from "./settings-section"

const DESCRIPTION =
  "Download local models or choose the model SurfSense uses for new messages."

export function ModelsSettings({
  onModelUnavailable,
  onSelected,
}: {
  onModelUnavailable: () => void
  onSelected: (selection: ModelSelection) => void
}) {
  const [activeProvider, setActiveProvider] = useState("local")
  const { state, draftKey, saveState, select, refresh, save } =
    useModelSelection()

  if (state.status === "loading") {
    return (
      <SettingsSection title="Models" description={DESCRIPTION}>
        <div
          className="flex flex-col gap-3"
          role="status"
          aria-label="Loading model settings"
        >
          <Skeleton className="h-7 w-36" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </SettingsSection>
    )
  }

  if (state.status === "api-unavailable") {
    return (
      <SettingsSection title="Models" description={DESCRIPTION}>
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>Could not load model settings</AlertTitle>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      </SettingsSection>
    )
  }

  const persistedKey =
    state.selection === null ? null : modelKey(state.selection)
  const hasChanges = draftKey !== null && draftKey !== persistedKey
  const draftProvider =
    draftKey === null
      ? null
      : state.models.find((model) => modelKey(model) === draftKey)?.provider
  const needsConfirmation =
    activeProvider === draftProvider &&
    state.providers.some(
      (provider) => provider.name === draftProvider && provider.requires_key
    )
  const isSaving = saveState.status === "saving"

  const saveSelection = async () => {
    const selection = await save()
    if (selection) {
      onSelected(selection)
    }
  }

  return (
    <SettingsSection
      title="Models"
      description={DESCRIPTION}
      footer={
        hasChanges && needsConfirmation ? (
          <Button disabled={isSaving} onClick={() => void saveSelection()}>
            {isSaving ? <Spinner data-icon="inline-start" /> : null}
            {isSaving ? "Saving..." : "Use selected model"}
          </Button>
        ) : undefined
      }
    >
      <ModelSelectionContent
        allowDelete
        state={state}
        draftKey={draftKey}
        disabled={isSaving}
        installedFirst
        onSelect={select}
        onCatalogSelected={(selection) => {
          onSelected(selection)
          void refresh({ silent: true })
        }}
        onModelUnavailable={onModelUnavailable}
        onModelsChanged={() => void refresh({ silent: true })}
        onActiveProviderChange={setActiveProvider}
        refresh={refresh}
      />
      <span className="sr-only" aria-live="polite">
        {state.selection ? "" : "No chat model is selected."}
      </span>

      {saveState.status === "error" ? (
        <p className="mt-3 text-sm text-destructive">{saveState.message}</p>
      ) : null}
    </SettingsSection>
  )
}

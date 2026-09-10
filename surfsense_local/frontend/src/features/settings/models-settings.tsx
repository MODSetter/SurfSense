import { CircleAlertIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
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
  const { state, draftKey, saveState, select, refresh, save } =
    useModelSelection()

  if (state.status === "api-unavailable") {
    return (
      <SettingsSection
        title="Models"
        description={DESCRIPTION}
        scrollable={false}
      >
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>Could not load model settings</AlertTitle>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      </SettingsSection>
    )
  }

  const readyState = state.status === "ready" ? state : null
  const persistedKey =
    readyState?.selection == null ? null : modelKey(readyState.selection)
  const hasChanges = draftKey !== null && draftKey !== persistedKey
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
      scrollable={false}
      footer={
        hasChanges ? (
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
        refresh={refresh}
      />
      <span className="sr-only" aria-live="polite">
        {readyState === null || readyState.selection
          ? ""
          : "No chat model is selected."}
      </span>

      {saveState.status === "error" ? (
        <p className="mt-3 text-sm text-destructive">{saveState.message}</p>
      ) : null}
    </SettingsSection>
  )
}

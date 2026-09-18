import { CircleAlertIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { modelKey, type ModelSelection } from "@/features/model-selection/api"
import { ModelSelectionContent } from "@/features/model-selection/model-selection-content"
import { useModelSelection } from "@/features/model-selection/use-model-selection"

import { SettingsSection } from "./settings-section"

const DESCRIPTION =
  "Add models locally or via an OpenAI compatible endpoint."

export function ModelsSettings({
  onModelUnavailable,
  onSelected,
}: {
  onModelUnavailable: () => void
  onSelected: (selection: ModelSelection) => void
}) {
  const { state, refresh } = useModelSelection()

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

  return (
    <SettingsSection title="Models" description={DESCRIPTION} scrollable="all">
      <ModelSelectionContent
        allowDelete
        scrollable={false}
        state={state}
        draftKey={
          readyState?.selection == null ? null : modelKey(readyState.selection)
        }
        disabled={false}
        onSelect={() => undefined}
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
    </SettingsSection>
  )
}

import { CircleAlertIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ModelCatalogPage } from "@/features/model-catalog/model-catalog-page"
import { modelKey, type ModelSelection } from "@/features/model-selection/api"
import { ProviderTab } from "@/features/model-selection/provider-tab"
import { useModelSelection } from "@/features/model-selection/use-model-selection"

import { SettingsSection } from "./settings-section"

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

const DESCRIPTION =
  "Download local models or choose the model SurfSense uses for new messages."

export function ModelsSettings({
  onSelected,
}: {
  onSelected: (selection: ModelSelection) => void
}) {
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
  const remoteProviders = state.providers.filter(
    (provider) => provider.requires_key
  )
  const defaultTab = remoteProviders.some(
    (provider) => provider.name === state.selection?.provider
  )
    ? state.selection?.provider
    : "local"
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
        hasChanges ? (
          <Button disabled={isSaving} onClick={() => void saveSelection()}>
            {isSaving ? <Spinner data-icon="inline-start" /> : null}
            {isSaving ? "Saving..." : "Use selected model"}
          </Button>
        ) : undefined
      }
    >
      {state.selection ? (
        <p className="mb-4 text-xs text-muted-foreground">
          Currently using{" "}
          <span className="font-medium text-foreground">
            {state.selection.name}
          </span>
        </p>
      ) : null}

      <Tabs defaultValue={defaultTab} className="gap-5">
        <TabsList>
          <TabsTrigger value="local">Local</TabsTrigger>
          {remoteProviders.map((provider) => (
            <TabsTrigger key={provider.name} value={provider.name}>
              {titleCase(provider.name)}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="local">
          <ModelCatalogPage
            installedFirst
            onSelected={(selection) => {
              onSelected(selection)
              void refresh({ silent: true })
            }}
          />
        </TabsContent>

        {remoteProviders.map((provider) => (
          <TabsContent key={provider.name} value={provider.name}>
            <ProviderTab
              provider={provider}
              models={state.models.filter(
                (model) => model.provider === provider.name
              )}
              draftKey={draftKey}
              persistedKey={persistedKey}
              onSelect={select}
              disabled={isSaving}
              refresh={refresh}
            />
          </TabsContent>
        ))}
      </Tabs>

      {saveState.status === "error" ? (
        <p className="mt-3 text-sm text-destructive">{saveState.message}</p>
      ) : null}
    </SettingsSection>
  )
}

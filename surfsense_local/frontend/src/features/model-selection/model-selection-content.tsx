import { useEffect } from "react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ModelCatalogPage } from "@/features/model-catalog/model-catalog-page"

import { modelKey, type ModelSelection } from "./api"
import { ProviderTab } from "./provider-tab"
import type { ModelSelectionState } from "./use-model-selection"

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

export function ModelSelectionContent({
  allowDelete = false,
  state,
  draftKey,
  disabled,
  installedFirst = false,
  onSelect,
  onCatalogSelected,
  onModelUnavailable,
  onModelsChanged,
  onActiveProviderChange,
  refresh,
}: {
  state: Extract<ModelSelectionState, { status: "ready" }>
  draftKey: string | null
  disabled: boolean
  installedFirst?: boolean
  allowDelete?: boolean
  onSelect: (key: string) => void
  onCatalogSelected?: (selection: ModelSelection) => void
  onModelUnavailable?: () => void
  onModelsChanged?: () => void
  onActiveProviderChange?: (provider: string) => void
  refresh: (options?: { silent?: boolean }) => Promise<void>
}) {
  const persistedKey =
    state.selection === null ? null : modelKey(state.selection)
  const remoteProviders = state.providers.filter(
    (provider) => provider.requires_key
  )
  const defaultTab = remoteProviders.some(
    (provider) => provider.name === state.selection?.provider
  )
    ? state.selection?.provider
    : "local"

  useEffect(() => {
    onActiveProviderChange?.(defaultTab)
  }, [defaultTab, onActiveProviderChange])

  const localCatalog = (
    <ModelCatalogPage
      allowDelete={allowDelete}
      installedFirst={installedFirst}
      onModelUnavailable={onModelUnavailable}
      onModelsChanged={onModelsChanged}
      onSelected={onCatalogSelected}
    />
  )

  if (remoteProviders.length === 0) {
    return localCatalog
  }

  return (
    <Tabs
      className="min-h-0 gap-5"
      defaultValue={defaultTab}
      onValueChange={onActiveProviderChange}
    >
      <TabsList>
        <TabsTrigger value="local">Local</TabsTrigger>
        {remoteProviders.map((provider) => (
          <TabsTrigger key={provider.name} value={provider.name}>
            {titleCase(provider.name)}
          </TabsTrigger>
        ))}
      </TabsList>

      <TabsContent value="local">{localCatalog}</TabsContent>

      {remoteProviders.map((provider) => (
        <TabsContent key={provider.name} value={provider.name}>
          <ProviderTab
            provider={provider}
            models={state.models.filter(
              (model) => model.provider === provider.name
            )}
            draftKey={draftKey}
            persistedKey={persistedKey}
            onSelect={onSelect}
            disabled={disabled}
            refresh={refresh}
          />
        </TabsContent>
      ))}
    </Tabs>
  )
}

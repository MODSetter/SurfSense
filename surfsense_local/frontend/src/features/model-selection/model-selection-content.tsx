import { useEffect, useRef, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CircleAlertIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ModelCatalogPage } from "@/features/model-catalog/model-catalog-page"

import { modelKey, type ModelSelection } from "./api"
import { ProviderTab } from "./provider-tab"
import type { ModelSelectionState } from "./use-model-selection"

const OPENROUTER = "openrouter"

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
  state: Extract<ModelSelectionState, { status: "loading" | "ready" }>
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
  const readyState = state.status === "ready" ? state : null
  const [activeTab, setActiveTab] = useState("local")
  const userChangedTab = useRef(false)
  const initializedTab = useRef(false)
  const persistedKey =
    readyState?.selection == null ? null : modelKey(readyState.selection)
  const openRouterProvider = readyState?.providers.find(
    (provider) => provider.name === OPENROUTER
  )
  const selectedTab =
    readyState?.selection?.provider === OPENROUTER ? OPENROUTER : "local"

  useEffect(() => {
    if (readyState === null || initializedTab.current) {
      return
    }
    initializedTab.current = true
    if (!userChangedTab.current) {
      setActiveTab(selectedTab)
    }
  }, [readyState, selectedTab])

  useEffect(() => {
    onActiveProviderChange?.(activeTab)
  }, [activeTab, onActiveProviderChange])

  const localCatalog = (
    <ModelCatalogPage
      allowDelete={allowDelete}
      disabled={disabled || readyState === null}
      installedFirst={installedFirst}
      onModelUnavailable={onModelUnavailable}
      onModelsChanged={onModelsChanged}
      onSelected={onCatalogSelected}
    />
  )

  return (
    <Tabs
      className="min-h-0 gap-5"
      value={activeTab}
      onValueChange={(provider) => {
        userChangedTab.current = true
        setActiveTab(provider)
      }}
    >
      <TabsList>
        <TabsTrigger value="local">Local</TabsTrigger>
        <TabsTrigger value={OPENROUTER}>OpenRouter</TabsTrigger>
      </TabsList>

      <TabsContent value="local">{localCatalog}</TabsContent>

      <TabsContent value={OPENROUTER}>
        {openRouterProvider ? (
          <ProviderTab
            provider={openRouterProvider}
            models={(readyState?.models ?? []).filter(
              (model) => model.provider === OPENROUTER
            )}
            draftKey={draftKey}
            persistedKey={persistedKey}
            onSelect={onSelect}
            disabled={disabled}
            modelsLoading={
              readyState?.loadingProviders.includes(OPENROUTER) ?? true
            }
            refresh={refresh}
          />
        ) : readyState === null ? (
          <div
            className="flex items-center gap-2 text-sm text-muted-foreground"
            role="status"
          >
            <Spinner />
            Loading OpenRouter...
          </div>
        ) : (
          <Alert variant="destructive">
            <CircleAlertIcon />
            <AlertTitle>OpenRouter unavailable</AlertTitle>
            <AlertDescription>
              The local backend did not return the OpenRouter provider.
            </AlertDescription>
          </Alert>
        )}
      </TabsContent>
    </Tabs>
  )
}

import { useEffect, useRef, useState } from "react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ModelCatalogPage } from "@/features/model-catalog/model-catalog-page"

import type { ModelSelection } from "./api"
import { OpenAICompatiblePanel } from "./openai-compatible-panel"
import type { ModelSelectionState } from "./use-model-selection"

const REMOTE = "openai_compatible"

export function ModelSelectionContent({
  allowDelete = false,
  state,
  disabled,
  installedFirst = false,
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
  const selectedTab =
    readyState?.selection?.provider === REMOTE ? REMOTE : "local"

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
      className="h-full min-h-0 gap-5"
      value={activeTab}
      onValueChange={(provider) => {
        userChangedTab.current = true
        setActiveTab(provider)
      }}
    >
      <TabsList className="mx-55 w-auto">
        <TabsTrigger value="local">Local</TabsTrigger>
        <TabsTrigger value={REMOTE}>OpenAI-compatible</TabsTrigger>
      </TabsList>

      <TabsContent value="local" className="min-h-0 overflow-hidden">
        {localCatalog}
      </TabsContent>

      <TabsContent value={REMOTE} className="min-h-0 overflow-hidden">
        <OpenAICompatiblePanel
          disabled={disabled}
          onGenerationSelected={(selection) => onCatalogSelected?.(selection)}
          onGenerationUnavailable={onModelUnavailable}
          onChanged={() => void refresh({ silent: true })}
        />
      </TabsContent>
    </Tabs>
  )
}

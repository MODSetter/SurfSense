import type { Provider, SelectableModel } from "./api"
import { ModelList } from "./model-list"
import { OpenRouterPanel } from "./providers/openrouter/panel"

export function ProviderTab({
  provider,
  models,
  draftKey,
  persistedKey,
  onSelect,
  disabled,
  modelsLoading = false,
  refresh,
}: {
  provider: Provider
  models: SelectableModel[]
  draftKey: string | null
  persistedKey: string | null
  onSelect: (key: string) => void
  disabled: boolean
  modelsLoading?: boolean
  refresh: (options?: { silent?: boolean }) => Promise<void>
}) {
  if (provider.requires_key) {
    return (
      <OpenRouterPanel
        provider={provider}
        models={models}
        draftKey={draftKey}
        persistedKey={persistedKey}
        onSelect={onSelect}
        disabled={disabled}
        modelsLoading={modelsLoading}
        onChanged={() => refresh({ silent: true })}
      />
    )
  }
  return (
    <ModelList
      models={models}
      draftKey={draftKey}
      persistedKey={persistedKey}
      onSelect={onSelect}
      disabled={disabled}
    />
  )
}

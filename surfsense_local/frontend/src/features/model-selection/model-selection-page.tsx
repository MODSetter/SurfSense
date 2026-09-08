import {
  BrainCircuitIcon,
  CheckIcon,
  CircleAlertIcon,
  RefreshCwIcon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ModelCatalogPage } from "@/features/model-catalog/model-catalog-page"

import {
  modelKey,
  type ModelSelection,
  type Provider,
  type SelectableModel,
} from "./api"
import { ModelList } from "./model-list"
import { OpenRouterPanel } from "./providers/openrouter/panel"
import { useModelSelection } from "./use-model-selection"

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

function LoadingModels() {
  return (
    <div
      className="flex flex-col gap-2"
      role="status"
      aria-label="Loading installed models"
    >
      {[0, 1, 2].map((item) => (
        <Skeleton key={item} className="h-16 w-full rounded-lg" />
      ))}
    </div>
  )
}

function OfflineState({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertTitle>Local backend unavailable</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        <p>
          Start it with <code>uv run main.py</code>.
        </p>
      </AlertDescription>
    </Alert>
  )
}

function ProviderTab({
  provider,
  models,
  draftKey,
  persistedKey,
  onSelect,
  disabled,
  refresh,
}: {
  provider: Provider
  models: SelectableModel[]
  draftKey: string | null
  persistedKey: string | null
  onSelect: (key: string) => void
  disabled: boolean
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

export function ModelSelectionPage({
  onSelected,
}: {
  onSelected?: (selection: ModelSelection) => void
}) {
  const { state, draftKey, saveState, isRefreshing, select, refresh, save } =
    useModelSelection()

  const persistedKey =
    state.status === "ready" && state.selection !== null
      ? modelKey(state.selection)
      : null
  const hasChanges = draftKey !== null && draftKey !== persistedKey
  const isSaving = saveState.status === "saving"
  const providers = state.status === "ready" ? state.providers : []
  const remoteProviders = providers.filter((provider) => provider.requires_key)
  const canContinue =
    state.status === "ready" &&
    draftKey !== null &&
    (!state.staleSelection || hasChanges)
  const defaultTab =
    state.status === "ready"
      ? remoteProviders.some(
          (provider) => provider.name === state.selection?.provider
        )
        ? state.selection?.provider
        : "local"
      : undefined

  const handlePrimaryAction = async () => {
    if (
      !hasChanges &&
      state.status === "ready" &&
      state.selection !== null &&
      !state.staleSelection
    ) {
      onSelected?.(state.selection)
      return
    }
    const selection = await save()
    if (selection) {
      onSelected?.(selection)
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-muted/30 p-4 sm:p-8">
      <div className="flex w-full max-w-4xl flex-col gap-4">
        <div className="flex items-center gap-2 px-1">
          <BrainCircuitIcon aria-hidden="true" className="size-5" />
          <span className="font-heading text-sm font-medium">
            SurfSense Local
          </span>
        </div>

        <Card className="[--card-spacing:--spacing(6)]">
          <CardHeader>
            <CardTitle>
              <h1 className="text-xl text-balance">Choose your AI model</h1>
            </CardTitle>
            <CardDescription className="max-w-lg text-pretty">
              Run a local model for full privacy, or bring your own OpenRouter
              key for capable remote models.
            </CardDescription>
          </CardHeader>

          <CardContent className="flex flex-col gap-4">
            {state.status === "loading" ? <LoadingModels /> : null}

            {state.status === "api-unavailable" ? (
              <OfflineState message={state.message} />
            ) : null}

            {state.status === "ready" && state.staleSelection ? (
              <Alert>
                <CircleAlertIcon />
                <AlertTitle>
                  Your previous model is no longer available
                </AlertTitle>
                <AlertDescription className="text-foreground">
                  Refresh after reinstalling it, or explicitly choose another
                  compatible model.
                </AlertDescription>
              </Alert>
            ) : null}

            {state.status === "ready" ? (
              <Tabs defaultValue={defaultTab}>
                <TabsList>
                  <TabsTrigger value="local">
                    <span
                      aria-hidden="true"
                      className="size-1.5 rounded-full bg-green-500"
                    />
                    Local
                  </TabsTrigger>
                  {remoteProviders.map((provider) => (
                    <TabsTrigger key={provider.name} value={provider.name}>
                      <span
                        aria-hidden="true"
                        className={`size-1.5 rounded-full ${
                          provider.healthy
                            ? "bg-green-500"
                            : "bg-muted-foreground/40"
                        }`}
                      />
                      {titleCase(provider.name)}
                    </TabsTrigger>
                  ))}
                </TabsList>
                <TabsContent value="local">
                  <ModelCatalogPage onSelected={onSelected} />
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
                      disabled={isSaving || isRefreshing}
                      refresh={refresh}
                    />
                  </TabsContent>
                ))}
              </Tabs>
            ) : null}

            <div className="min-h-5 text-sm" aria-live="polite">
              {saveState.status === "saved" ? (
                <span className="flex items-center gap-1.5">
                  <CheckIcon aria-hidden="true" className="size-4" />
                  Model selection saved.
                </span>
              ) : null}
              {saveState.status === "error" ? (
                <span className="text-destructive">{saveState.message}</span>
              ) : null}
            </div>
          </CardContent>

          <CardFooter className="justify-between gap-3">
            <Button
              type="button"
              variant="outline"
              className="min-h-10"
              disabled={isRefreshing || isSaving}
              onClick={() => void refresh()}
            >
              {isRefreshing ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <RefreshCwIcon data-icon="inline-start" />
              )}
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </Button>
            <Button
              type="button"
              className="min-h-10"
              disabled={!canContinue || isSaving || isRefreshing}
              onClick={() => void handlePrimaryAction()}
            >
              {isSaving ? <Spinner data-icon="inline-start" /> : null}
              {isSaving
                ? "Saving..."
                : hasChanges
                  ? "Use this model"
                  : "Continue"}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </main>
  )
}

import {
  BrainCircuitIcon,
  CheckIcon,
  CircleAlertIcon,
  RefreshCwIcon,
  ServerOffIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import {
  Field,
  FieldContent,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

import { modelKey } from "./api"
import type { ModelSelection } from "./api"
import { ModelCatalog } from "./model-catalog"
import { useModelSelection } from "./use-model-selection"

const titleCase = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1)

function LoadingModels() {
  return (
    <div className="flex flex-col gap-2" aria-label="Loading installed models">
      {[0, 1, 2].map((item) => (
        <Skeleton key={item} className="h-16 w-full rounded-lg" />
      ))}
    </div>
  )
}

function OfflineState({
  kind,
  message,
}: {
  kind: "api" | "provider"
  message: string
}) {
  const apiIsOffline = kind === "api"
  return (
    <Alert variant="destructive">
      {apiIsOffline ? <ServerOffIcon /> : <CircleAlertIcon />}
      <AlertTitle>
        {apiIsOffline
          ? "Local backend unavailable"
          : "Model provider unavailable"}
      </AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        <p>
          {apiIsOffline ? (
            <>
              Start it with <code>uv run main.py</code>.
            </>
          ) : (
            <>
              Make sure Ollama is running with <code>ollama serve</code>.
            </>
          )}
        </p>
      </AlertDescription>
    </Alert>
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
    (state.status === "ready" || state.status === "empty") &&
    state.selection !== null
      ? modelKey(state.selection)
      : null
  const hasChanges = draftKey !== null && draftKey !== persistedKey
  const isSaving = saveState.status === "saving"
  const isConnected = state.status === "ready" || state.status === "empty"
  const healthyProviders = isConnected
    ? state.providers.filter((provider) => provider.healthy)
    : []
  const downloadableProviders = healthyProviders
    .filter((provider) => provider.can_download)
    .map((provider) => provider.name)
  const canContinue =
    state.status === "ready" &&
    draftKey !== null &&
    (!state.staleSelection || hasChanges)
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
    <main className="flex min-h-svh items-center justify-center bg-muted/30 p-4 sm:p-8">
      <div className="flex w-full max-w-2xl flex-col gap-4">
        <div className="flex items-center gap-2 px-1">
          <BrainCircuitIcon aria-hidden="true" className="size-5" />
          <span className="font-heading text-sm font-medium">
            SurfSense Local
          </span>
        </div>

        <Card className="[--card-spacing:--spacing(6)]">
          <CardHeader>
            <CardTitle>
              <h1 className="text-xl text-balance">
                Choose your local AI model
              </h1>
            </CardTitle>
            <CardDescription className="max-w-lg text-pretty">
              Pick the model that will answer questions about your documents.
              Your data and inference stay on this machine.
            </CardDescription>
            <CardAction>
              {state.status === "loading" ? (
                <Skeleton className="h-5 w-20 rounded-full" />
              ) : isConnected ? (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {healthyProviders.map((provider) => (
                    <Badge
                      key={provider.name}
                      variant="secondary"
                      className="gap-1.5"
                    >
                      <span
                        aria-hidden="true"
                        className="size-1.5 rounded-full bg-green-500"
                      />
                      {titleCase(provider.name)}
                    </Badge>
                  ))}
                </div>
              ) : (
                <Badge variant="destructive">Offline</Badge>
              )}
            </CardAction>
          </CardHeader>

          <CardContent className="flex flex-col gap-4">
            {state.status === "loading" ? <LoadingModels /> : null}

            {state.status === "api-unavailable" ? (
              <OfflineState kind="api" message={state.message} />
            ) : null}

            {state.status === "provider-unavailable" ? (
              <OfflineState kind="provider" message={state.message} />
            ) : null}

            {(state.status === "ready" || state.status === "empty") &&
            state.staleSelection ? (
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

            {state.status === "empty" ? (
              <div className="flex flex-col gap-3">
                <div>
                  <h2 className="text-sm font-medium">Download a model</h2>
                  <p className="text-sm text-pretty text-muted-foreground">
                    No compatible model is installed yet. Pick one to download —
                    it stays on this machine.
                  </p>
                </div>
                <ModelCatalog
                  providers={downloadableProviders}
                  onPulled={() => void refresh()}
                />
              </div>
            ) : null}

            {state.status === "ready" ? (
              <FieldSet>
                <FieldLegend className="sr-only">
                  Installed generation models
                </FieldLegend>
                <RadioGroup
                  value={draftKey ?? ""}
                  onValueChange={select}
                  disabled={isSaving || isRefreshing}
                  aria-label="Installed generation models"
                >
                  {state.models.map((model, index) => {
                    const key = modelKey(model)
                    const id = `model-${index}`
                    return (
                      <FieldLabel key={key} htmlFor={id}>
                        <Field orientation="horizontal">
                          <RadioGroupItem id={id} value={key} />
                          <FieldContent>
                            <div className="flex min-w-0 items-center justify-between gap-3">
                              <FieldTitle className="truncate">
                                {model.name}
                              </FieldTitle>
                              {key === persistedKey ? (
                                <Badge variant="secondary">Current</Badge>
                              ) : null}
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <Badge variant="outline">{model.provider}</Badge>
                              {model.capabilities.map((capability) => (
                                <Badge key={capability} variant="outline">
                                  {titleCase(capability)}
                                </Badge>
                              ))}
                            </div>
                          </FieldContent>
                        </Field>
                      </FieldLabel>
                    )
                  })}
                </RadioGroup>
              </FieldSet>
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
              onClick={refresh}
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

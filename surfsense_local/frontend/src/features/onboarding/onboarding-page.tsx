import { useCallback, useEffect, useRef, useState } from "react"

import { CheckIcon, CircleAlertIcon, RefreshCwIcon } from "@/components/ui/icons"
import surfSenseLogo from "@/surfsense-logo.svg"

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
import { modelKey, type ModelSelection } from "@/features/model-selection/api"
import { ModelSelectionContent } from "@/features/model-selection/model-selection-content"
import { useModelSelection } from "@/features/model-selection/use-model-selection"
import { cn } from "@/lib/utils"

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

export function OnboardingPage({
  onComplete,
}: {
  onComplete: (selection: ModelSelection) => void
}) {
  const [activeProvider, setActiveProvider] = useState("local")
  const scrollRef = useRef<HTMLDivElement>(null)
  const [scrollEdges, setScrollEdges] = useState({
    top: false,
    bottom: false,
  })
  const { state, draftKey, saveState, isRefreshing, select, refresh, save } =
    useModelSelection()
  const isReady = state.status === "ready"
  const updateScrollEdges = useCallback(() => {
    const scrollArea = scrollRef.current
    if (!scrollArea) {
      return
    }
    const top = scrollArea.scrollTop > 1
    const bottom =
      scrollArea.scrollTop + scrollArea.clientHeight <
      scrollArea.scrollHeight - 1
    setScrollEdges((current) =>
      current.top === top && current.bottom === bottom
        ? current
        : { top, bottom }
    )
  }, [])

  useEffect(() => {
    if (!isReady) {
      return
    }
    const frame = window.requestAnimationFrame(updateScrollEdges)
    const scrollArea = scrollRef.current
    if (typeof ResizeObserver === "undefined" || !scrollArea) {
      return () => window.cancelAnimationFrame(frame)
    }
    const observer = new ResizeObserver(updateScrollEdges)
    observer.observe(scrollArea)
    if (scrollArea.firstElementChild) {
      observer.observe(scrollArea.firstElementChild)
    }
    return () => {
      window.cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [isReady, updateScrollEdges])
  const persistedKey =
    state.status === "ready" && state.selection !== null
      ? modelKey(state.selection)
      : null
  const hasChanges = draftKey !== null && draftKey !== persistedKey
  const draftProvider =
    state.status === "ready" && draftKey !== null
      ? state.models.find((model) => modelKey(model) === draftKey)?.provider
      : null
  const needsConfirmation =
    state.status === "ready" &&
    activeProvider === draftProvider &&
    state.providers.some(
      (provider) => provider.name === draftProvider && provider.requires_key
    )
  const isSaving = saveState.status === "saving"
  const canContinue =
    needsConfirmation &&
    draftKey !== null &&
    (!state.staleSelection || hasChanges)

  const complete = async () => {
    if (
      !hasChanges &&
      state.status === "ready" &&
      state.selection !== null &&
      !state.staleSelection
    ) {
      onComplete(state.selection)
      return
    }
    const selection = await save()
    if (selection) {
      onComplete(selection)
    }
  }

  return (
    <main
      data-onboarding-page
      className="flex h-full min-h-0 items-center overflow-hidden bg-muted/30 p-3 select-none sm:p-6"
    >
      <div className="mx-auto flex h-full max-h-[760px] min-h-0 w-full max-w-3xl flex-col gap-3">
        <div className="flex items-center justify-center gap-2 px-1">
          <span
            aria-hidden="true"
            className="size-11 bg-foreground"
            style={{
              maskImage: `url(${surfSenseLogo})`,
              maskPosition: "center",
              maskRepeat: "no-repeat",
              maskSize: "contain",
            }}
          />
          <span className="font-heading text-2xl font-medium">SurfSense</span>
        </div>

        <Card className="max-h-[calc(100%_-_3.5rem)] min-h-0 gap-0">
          <CardHeader className="mb-(--card-spacing)">
            <CardTitle>
              <h1 className="text-lg text-balance">Choose your AI model</h1>
            </CardTitle>
            <CardDescription className="max-w-lg text-pretty">
              Run a local model for full privacy, or bring your own OpenRouter
              key for capable remote models.
            </CardDescription>
          </CardHeader>

          <CardContent className="flex min-h-0 flex-col gap-3">
            {state.status === "loading" ? <LoadingModels /> : null}
            {state.status === "api-unavailable" ? (
              <OfflineState message={state.message} />
            ) : null}
            {state.status === "ready" ? (
              <div className="relative flex min-h-0 flex-1">
                <div
                  ref={scrollRef}
                  data-slot="onboarding-models-scroll"
                  className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
                  onScroll={updateScrollEdges}
                >
                  <ModelSelectionContent
                    state={state}
                    draftKey={draftKey}
                    disabled={isSaving || isRefreshing}
                    onSelect={select}
                    onCatalogSelected={onComplete}
                    onActiveProviderChange={setActiveProvider}
                    refresh={refresh}
                  />
                </div>
                <div
                  data-slot="onboarding-models-shadow-top"
                  className={cn(
                    "pointer-events-none absolute inset-x-0 top-0 z-10 h-3 bg-gradient-to-b from-card to-transparent transition-opacity duration-100 ease-out",
                    scrollEdges.top ? "opacity-100" : "opacity-0"
                  )}
                />
                <div
                  data-slot="onboarding-models-shadow-bottom"
                  className={cn(
                    "pointer-events-none absolute inset-x-0 bottom-0 z-10 h-3 bg-gradient-to-t from-card to-transparent transition-opacity duration-100 ease-out",
                    scrollEdges.bottom ? "opacity-100" : "opacity-0"
                  )}
                />
              </div>
            ) : null}

            {saveState.status === "saved" || saveState.status === "error" ? (
              <div className="text-sm" aria-live="polite">
                {saveState.status === "saved" ? (
                  <span className="flex items-center gap-1.5">
                    <CheckIcon aria-hidden="true" className="size-4" />
                    Model selection saved.
                  </span>
                ) : (
                  <span className="text-destructive">{saveState.message}</span>
                )}
              </div>
            ) : null}
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
            {needsConfirmation ? (
              <Button
                type="button"
                className="min-h-10"
                disabled={!canContinue || isSaving || isRefreshing}
                onClick={() => void complete()}
              >
                {isSaving ? <Spinner data-icon="inline-start" /> : null}
                {isSaving
                  ? "Saving..."
                  : hasChanges
                    ? "Use this model"
                    : "Continue"}
              </Button>
            ) : null}
          </CardFooter>
        </Card>
      </div>
    </main>
  )
}

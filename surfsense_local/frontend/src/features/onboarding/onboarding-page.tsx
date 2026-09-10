import { useState } from "react"

import {
  CheckIcon,
  CircleAlertIcon,
  RefreshCwIcon,
} from "@/components/ui/icons"
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
import { Spinner } from "@/components/ui/spinner"
import { Stepper, StepperIndicator, StepperItem } from "@/components/ui/stepper"
import { modelKey, type ModelSelection } from "@/features/model-selection/api"
import { ModelSelectionContent } from "@/features/model-selection/model-selection-content"
import { useModelSelection } from "@/features/model-selection/use-model-selection"

const ONBOARDING_STEPS = [1, 2] as const

function OnboardingBrand() {
  return (
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
  )
}

function OnboardingProgress({ step }: { step: number }) {
  return (
    <Stepper
      value={step}
      aria-label={`Onboarding step ${step} of ${ONBOARDING_STEPS.length}`}
      className="mx-auto max-w-28 gap-1.5"
    >
      {ONBOARDING_STEPS.map((item) => (
        <StepperItem key={item} step={item} className="flex-1">
          <StepperIndicator
            asChild
            className="h-1 w-full rounded-full bg-border"
          >
            <span className="sr-only">Step {item}</span>
          </StepperIndicator>
        </StepperItem>
      ))}
    </Stepper>
  )
}

function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <Card className="w-full max-w-xl overflow-visible bg-transparent text-center ring-0">
      <CardHeader className="-translate-y-8">
        <CardTitle>
          <h1 className="text-xl text-balance">
            Think across everything you have collected.
          </h1>
        </CardTitle>
        <CardDescription className="mx-auto max-w-md text-pretty">
          SurfSense turns scattered documents, notes, and sources into one
          searchable workspace.
        </CardDescription>
      </CardHeader>
      <CardFooter className="justify-center border-t-0 bg-transparent">
        <Button type="button" className="min-h-10 px-6" onClick={onNext}>
          Start setting up
        </Button>
      </CardFooter>
    </Card>
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

function ModelSetupStep({
  onComplete,
}: {
  onComplete: (selection: ModelSelection) => void
}) {
  const { state, draftKey, saveState, isRefreshing, select, refresh, save } =
    useModelSelection()
  const showsModelSelection = state.status !== "api-unavailable"
  const persistedKey =
    state.status === "ready" && state.selection !== null
      ? modelKey(state.selection)
      : null
  const hasChanges = draftKey !== null && draftKey !== persistedKey
  const isSaving = saveState.status === "saving"
  const canContinue =
    state.status === "ready" &&
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
    <Card className="h-full max-h-full min-h-0 w-full gap-0">
      <CardHeader className="mb-(--card-spacing)">
        <CardTitle>
          <h1 className="text-lg text-balance">Choose your AI model</h1>
        </CardTitle>
        <CardDescription className="max-w-lg text-pretty">
          Run a local model for full privacy, or connect an OpenAI-compatible
          endpoint.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        {state.status === "api-unavailable" ? (
          <OfflineState message={state.message} />
        ) : null}
        {showsModelSelection ? (
          <div className="min-h-0 flex-1 overflow-hidden">
            <ModelSelectionContent
              state={state}
              draftKey={draftKey}
              disabled={isSaving || isRefreshing}
              installedFirst
              onSelect={select}
              onCatalogSelected={onComplete}
              refresh={refresh}
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
          disabled={state.status !== "ready" || isRefreshing || isSaving}
          onClick={() => void refresh()}
        >
          {isRefreshing ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <RefreshCwIcon data-icon="inline-start" />
          )}
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </Button>
        {state.status === "ready" && draftKey !== null ? (
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
  )
}

export function OnboardingPage({
  onComplete,
}: {
  onComplete: (selection: ModelSelection) => void
}) {
  const [step, setStep] = useState<(typeof ONBOARDING_STEPS)[number]>(1)

  return (
    <main
      data-onboarding-page
      className="flex h-full min-h-0 items-center overflow-hidden bg-muted/30 p-3 select-none sm:p-6"
    >
      <div className="mx-auto flex h-full max-h-[760px] min-h-0 w-full max-w-3xl flex-col gap-3">
        <OnboardingBrand />
        <OnboardingProgress step={step} />
        <div className="flex min-h-0 flex-1 items-center justify-center">
          {step === 1 ? (
            <WelcomeStep onNext={() => setStep(2)} />
          ) : (
            <ModelSetupStep onComplete={onComplete} />
          )}
        </div>
      </div>
    </main>
  )
}

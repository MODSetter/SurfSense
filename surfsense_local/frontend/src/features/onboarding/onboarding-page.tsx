import { useState } from "react"

import { ArrowRightIcon, CircleAlertIcon } from "@/components/ui/icons"
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
import type { ModelSelection } from "@/features/models/selection/api"
import { useSelection } from "@/features/models/selection/use-selection"

import { completeOnboarding } from "./api"
import { OnboardingDither } from "./onboarding-dither"

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

/**
 * The hero's call to action, ported from the site's `FlowButton`
 * (`surfsense_web/components/ui/flow-button.tsx`): two arrows trade places
 * while a disc of `--primary` floods the pill from its centre and the corners
 * tighten. Ported rather than shared -- the original is a Next.js `Link` --
 * and cut down to the one shape this screen needs.
 *
 * The arrows carry no colour of their own so they ride the button's
 * `currentColor` from `--primary` to `--primary-foreground` as the disc
 * arrives underneath them.
 */
function FlowButton({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative flex cursor-pointer items-center gap-1 overflow-hidden rounded-[100px] border-[1.5px] border-primary/40 bg-transparent px-8 py-3 text-sm font-semibold text-primary transition-all duration-[600ms] ease-[cubic-bezier(0.23,1,0.32,1)] hover:rounded-[12px] hover:border-transparent hover:text-primary-foreground active:scale-[0.95]"
    >
      <ArrowRightIcon className="absolute left-[-25%] z-[9] size-4 transition-all duration-[800ms] ease-[cubic-bezier(0.34,1.56,0.64,1)] group-hover:left-4" />
      <span className="relative z-[1] -translate-x-3 transition-all duration-[800ms] ease-out group-hover:translate-x-3">
        {text}
      </span>
      <span
        aria-hidden="true"
        className="absolute top-1/2 left-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary opacity-0 transition-all duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)] group-hover:size-[220px] group-hover:opacity-100"
      />
      <ArrowRightIcon className="absolute right-4 z-[9] size-4 transition-all duration-[800ms] ease-[cubic-bezier(0.34,1.56,0.64,1)] group-hover:right-[-25%]" />
    </button>
  )
}

/**
 * The site's hero, rebuilt as the first thing the app ever shows: same
 * headline, same lede, same dithered wave behind it, same pill. Where the site
 * sends a visitor off to download, this one starts the setup.
 *
 * Kept in step with `HomeHero` in
 * `surfsense_web/components/homepage/home/home-sections.tsx`. The two type
 * scales are that page's `.ss-home-display` and `.ss-home-lede` written as
 * utilities, and the accent clause is `--primary`, which is what the site's
 * `--home-accent` resolves to. In this app's light theme that token is near
 * black rather than peach, so the clause reads as plain heading text there --
 * the alternative, peach on cream, does not carry enough contrast to set text
 * in.
 */
function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="text-center">
      <h1 className="relative -top-10 text-[clamp(2.25rem,6vw,3.75rem)] leading-[1.05] font-semibold tracking-[-0.03em] text-balance">
        Air-gapped, open source{" "}
        <span className="text-primary">NotebookLM alternative</span>
      </h1>
      <p className="mx-auto mt-8 max-w-2xl text-[clamp(1rem,1.6vw,1.25rem)] leading-[1.6] text-pretty text-muted-foreground">
        A private research notebook that runs entirely on your own machine. Your
        documents, your model keys, no cloud, no account.
      </p>
      <div className="mt-10 flex justify-center">
        <FlowButton text="Start setting up" onClick={onNext} />
      </div>
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

/**
 * The model step's frame. Its content is still to be designed; it will be
 * built on the same hooks as the settings pages in `features/models`.
 */
function ModelSetupStep({
  onComplete,
}: {
  onComplete: (selection: ModelSelection) => void
}) {
  const chat = useSelection("text_gen")
  const [completing, setCompleting] = useState(false)
  const [completeError, setCompleteError] = useState<string | null>(null)
  const selection = chat.data ?? null

  const finish = async () => {
    if (selection === null) return
    setCompleting(true)
    setCompleteError(null)
    try {
      await completeOnboarding()
      onComplete(selection)
    } catch (error) {
      setCompleteError(
        error instanceof Error ? error.message : "Could not finish setup"
      )
    } finally {
      setCompleting(false)
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
        {chat.isError ? <OfflineState message={chat.error.message} /> : null}
        {completeError ? (
          <p className="text-sm text-destructive" aria-live="polite">
            {completeError}
          </p>
        ) : null}
      </CardContent>

      <CardFooter className="justify-end gap-3">
        <Button
          type="button"
          className="min-h-10"
          disabled={selection === null || completing}
          onClick={() => void finish()}
        >
          {completing ? <Spinner data-icon="inline-start" /> : null}
          Start chatting
        </Button>
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
      className="relative isolate flex h-full min-h-0 items-center overflow-hidden bg-muted/30 p-3 select-none sm:p-6"
    >
      {step === 1 ? <OnboardingDither /> : null}
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

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { ArrowRightIcon } from "@/components/ui/icons"
import surfSenseLogo from "@/surfsense-logo.svg"

import { Progress } from "@/components/ui/progress"
import type { ModelSelection } from "@/features/models/selection/api"
import { usePrivacyState } from "@/features/privacy-choices/use-privacy-state"
import { intl } from "@/i18n/intl"

import { ModelStep } from "./model-step/model-step"
import type { OnboardingStepKind } from "./model-step/kinds/step-kind"
import { OnboardingDither } from "./onboarding-dither"
import { PrivacyStep } from "./privacy-step/privacy-step"
import { useFinishOnboarding } from "./use-finish-onboarding"

/**
 * The steps, in order, and the ones the progress bar counts. The welcome is still
 * onboarding, and still gated by the same marker, but it is an introduction,
 * not a step to complete. Whichever step is last finishes onboarding.
 *
 * The embedding model comes last and is the one step that is not a slot: its
 * choice is sent with the finish that fixes it, never held across steps.
 */
const STEPS = [
  "text_gen",
  "image_gen",
  "image_edit",
  "audio_gen",
  "video_gen",
  "embedding",
] as const satisfies readonly OnboardingStepKind[]

type Step = (typeof STEPS)[number]
// The privacy choices sit between the welcome and the steps, and like the
// welcome they are not a step the progress bar counts.
type Screen = "welcome" | "privacy" | Step

/** Finishing needs a chat model, so only this step cannot be skipped. */
const REQUIRED_STEP: Step = "text_gen"

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
      <span className="translate-y-[-0.08em] brand-wordmark text-2xl">
        SurfSense
      </span>
    </div>
  )
}

function OnboardingProgress({ screen }: { screen: Step }) {
  const step = STEPS.indexOf(screen) + 1
  const label = intl.formatMessage(
    {
      id: "onboarding_progress_aria",
      defaultMessage: "Onboarding step {step, number} of {total, number}",
    },
    {
      step,
      total: STEPS.length,
    }
  )
  return (
    <Progress
      value={step}
      max={STEPS.length}
      aria-label={label}
      getAriaValueText={() => label}
      className="mx-auto w-full max-w-28 **:data-[slot=progress-indicator]:rounded-full **:data-[slot=progress-indicator]:duration-300 **:data-[slot=progress-indicator]:ease-out **:data-[slot=progress-track]:bg-border **:data-[slot=progress-indicator]:motion-reduce:transition-none"
    />
  )
}

/**
 * The hero's call to action. A disc of `--primary` grows from the trailing
 * arrow's circle to flood the whole pill on hover, revealing a second copy of
 * the label clipped to that disc so the text itself switches from
 * `--primary` to `--primary-foreground` as the fill arrives underneath it.
 */
function FlowButton({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant="bare"
      onClick={onClick}
      className="group relative inline-flex h-11 items-center overflow-hidden rounded-full border-[1.5px] border-primary/40 bg-transparent pr-11 pl-6 text-sm font-semibold text-primary [--circle-inset-y:calc((100%-var(--icon-circle))/2)] [--icon-circle:2rem] [--icon-right:0.375rem]"
    >
      <span className="relative z-1 pb-px">{text}</span>

      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-[var(--circle-inset-y)_var(--icon-right)_var(--circle-inset-y)_calc(100%-var(--icon-right)-var(--icon-circle))] z-2 rounded-full bg-primary transition-all duration-450 ease-[cubic-bezier(0.785,0.135,0.15,0.86)] group-hover:inset-0 motion-reduce:transition-none"
      />

      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-2 flex items-center pr-11 pl-6 text-primary-foreground transition-all duration-450 ease-[cubic-bezier(0.785,0.135,0.15,0.86)] [clip-path:inset(var(--circle-inset-y)_var(--icon-right)_var(--circle-inset-y)_calc(100%-var(--icon-right)-var(--icon-circle)))] group-hover:[clip-path:inset(0_0_0_0)] motion-reduce:transition-none"
      >
        <span className="relative z-1 pb-px whitespace-nowrap">{text}</span>
      </span>

      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-(--icon-right) z-3 inline-flex size-(--icon-circle) -translate-y-1/2 items-center justify-center overflow-hidden rounded-full bg-primary text-primary-foreground"
      >
        <ArrowRightIcon className="absolute top-1/2 left-1/2 size-4 origin-center translate-x-[-170%] -translate-y-1/2 scale-0 transition-transform duration-450 ease-[cubic-bezier(0.785,0.135,0.15,0.86)] group-hover:-translate-x-1/2 group-hover:scale-100 motion-reduce:transition-none" />
        <ArrowRightIcon className="absolute top-1/2 left-1/2 size-4 origin-center -translate-x-1/2 -translate-y-1/2 transition-transform duration-450 ease-[cubic-bezier(0.785,0.135,0.15,0.86)] group-hover:translate-x-[70%] group-hover:scale-0 motion-reduce:transition-none" />
      </span>
    </Button>
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
 * in. The clause is an `<accent>` tag in the message, so each language places
 * it in its own sentence.
 */
function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="text-center">
      <h1 className="relative -top-10 text-[clamp(2.25rem,6vw,3.75rem)] leading-[1.05] font-semibold tracking-[-0.03em] text-balance">
        {intl.formatMessage(
          {
            id: "onboarding_welcome_title",
            defaultMessage:
              "Air-gapped, open source <accent>NotebookLM alternative</accent>",
          },
          {
            accent: (chunks) => <span className="text-primary">{chunks}</span>,
          }
        )}
      </h1>
      <p className="mx-auto mt-8 max-w-2xl text-[clamp(1rem,1.6vw,1.25rem)] leading-[1.6] text-pretty text-muted-foreground">
        {intl.formatMessage({
          id: "onboarding_welcome_body",
          defaultMessage:
            "A private research notebook that runs entirely on your own machine. Your documents, your model keys, no cloud, no account.",
        })}
      </p>
      <div className="mt-10 flex justify-center">
        <FlowButton
          text={intl.formatMessage({
            id: "onboarding_welcome_start_button",
            defaultMessage: "Start setting up",
          })}
          onClick={onNext}
        />
      </div>
    </div>
  )
}

/** One step in the order of `STEPS`: the last one finishes, the rest move on. */
function OnboardingStep({
  step,
  onGo,
  onComplete,
}: {
  step: Step
  onGo: (step: Step) => void
  onComplete: (selection: ModelSelection) => void
}) {
  const { finish, finishing, error } = useFinishOnboarding(onComplete)
  const index = STEPS.indexOf(step)
  const previous = STEPS[index - 1]
  const next = STEPS[index + 1]
  // The last step finishes, sending its value: the embedding choice, or null.
  const advance = (value: string | null) =>
    next ? onGo(next) : void finish(value)
  return (
    <ModelStep
      modelType={step}
      last={!next}
      finishing={finishing}
      error={error}
      onBack={previous ? () => onGo(previous) : undefined}
      onNext={advance}
      onSkip={step === REQUIRED_STEP ? undefined : () => advance(null)}
    />
  )
}

export function OnboardingPage({
  onComplete,
}: {
  onComplete: (selection: ModelSelection) => void
}) {
  const [chosen, setScreen] = useState<Screen>("welcome")
  const { state: privacy } = usePrivacyState()
  // Asked once, on a new install: never outside the desktop app, or once answered.
  const privacyAnswered = privacy === null || privacy?.firstRunAsked === true
  // Left the welcome before the answer was read, and none was needed.
  const screen: Screen =
    chosen === "privacy" && privacyAnswered ? STEPS[0] : chosen

  return (
    <main
      data-onboarding-page
      className="relative isolate flex h-full min-h-0 items-center overflow-hidden bg-muted/30 p-3 select-none sm:p-6"
    >
      <OnboardingDither visible={screen === "welcome"} />
      <div className="mx-auto flex h-full max-h-190 min-h-0 w-full max-w-3xl flex-col gap-3">
        <OnboardingBrand />
        {screen === "welcome" || screen === "privacy" ? (
          // The progress bar's height, kept so the hero sits exactly where it did.
          <div aria-hidden="true" className="h-1" />
        ) : (
          <OnboardingProgress screen={screen} />
        )}
        <div className="flex min-h-0 flex-1 items-center justify-center">
          {screen === "welcome" ? (
            <WelcomeStep
              onNext={() => setScreen(privacyAnswered ? STEPS[0] : "privacy")}
            />
          ) : screen === "privacy" ? (
            // Shown once read; `screen` moves on by itself if it needs no answer.
            privacy ? (
              <PrivacyStep state={privacy} onDone={() => setScreen(STEPS[0])} />
            ) : null
          ) : (
            // Keyed so each step starts fresh rather than inheriting the last.
            <OnboardingStep
              key={screen}
              step={screen}
              onGo={setScreen}
              onComplete={onComplete}
            />
          )}
        </div>
      </div>
    </main>
  )
}

import { useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ServerOffIcon } from "@/components/ui/icons"
import {
  getGenerationSelection,
  type ModelSelection,
} from "@/features/models/selection/api"
import {
  checkAvailability,
  type Availability,
} from "@/features/models/selection/availability"
import { getOnboardingStatus } from "@/features/onboarding/api"
import { OnboardingPage } from "@/features/onboarding/onboarding-page"
import { intl } from "@/i18n/intl"

import { listWorkspaces, type Workspace } from "@/features/workspaces/api"

import {
  expectsDashboard,
  forgetDashboard,
  rememberDashboard,
} from "@/features/startup/dashboard-hint"
import {
  createStartupInput,
  type StartupInput,
} from "@/features/startup/startup-input"
import { StartupInputContext } from "@/features/startup/startup-input-context"
import { StartupRevealProvider } from "@/features/startup/startup-reveal-provider"
import { StartupScreen } from "@/features/startup/startup-screen"

import { loadDashboard, type DashboardComponent } from "./load-dashboard"

// A wait shorter than this ends before the frame is noticed: the dashboard is
// drawn at once rather than faded in, which would only make it look slower.
const REVEAL_AFTER_MS = 150

type Loading = {
  status: "loading"
  // Whether the dashboard's frame is drawn, rather than the plain background.
  frame: boolean
  since: number
}

type Fetched =
  | { status: "onboarding-required" }
  | {
      status: "ready"
      /** Loaded before the state turns ready, so it renders without suspending. */
      Dashboard: DashboardComponent
      // The saved choice, kept whatever its status: clearing it to say it
      // can't be used would leave nothing to check again once it can.
      selection: ModelSelection | null
      availability: Availability
      workspaces: Workspace[]
    }
  | { status: "error"; message: string }

type BootstrapState =
  | Loading
  | Exclude<Fetched, { status: "ready" }>
  | (Extract<Fetched, { status: "ready" }> & { reveal: boolean })

function startLoading(): Loading {
  return { status: "loading", frame: expectsDashboard(), since: Date.now() }
}

// Fades the dashboard into a frame that was on screen long enough to see.
function settle(current: BootstrapState, next: Fetched): BootstrapState {
  if (next.status !== "ready") return next
  const reveal =
    current.status === "loading" &&
    current.frame &&
    Date.now() - current.since >= REVEAL_AFTER_MS
  return { ...next, reveal }
}

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "app_bootstrap_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

async function fetchBootstrapState(): Promise<Fetched> {
  // Fetched alongside the data rather than after it: one wait, one loader.
  const dashboard = loadDashboard()
  // Handled where it is awaited; this only keeps an early exit from leaving
  // a rejection unobserved.
  void dashboard.catch(() => undefined)
  try {
    const onboarding = await getOnboardingStatus()
    if (!onboarding.completed) {
      forgetDashboard()
      return { status: "onboarding-required" }
    }
    rememberDashboard()
    const [selection, workspaces] = await Promise.all([
      getGenerationSelection(),
      listWorkspaces(),
    ])
    // Never fails startup: a model that can't be used opens the app without
    // it, and the dashboard says why.
    const availability: Availability = selection
      ? await checkAvailability(selection)
      : { status: "gone" }
    return {
      status: "ready",
      Dashboard: await dashboard,
      selection,
      availability,
      workspaces,
    }
  } catch (error) {
    return { status: "error", message: messageFrom(error) }
  }
}

export function AppBootstrap() {
  // What is typed into the frame's box, for the composer that replaces it.
  const [startupInput] = useState(createStartupInput)
  return (
    <StartupInputContext.Provider value={startupInput}>
      <BootstrapScreens startupInput={startupInput} />
    </StartupInputContext.Provider>
  )
}

function BootstrapScreens({ startupInput }: { startupInput: StartupInput }) {
  // The frame's box may be mid-composition, which a handover would cut.
  const afterComposing = (next: Fetched) =>
    startupInput.composingEnded().then(() => next)
  const [state, setState] = useState<BootstrapState>(startLoading)

  useEffect(() => {
    let active = true
    void fetchBootstrapState()
      .then((next) => startupInput.composingEnded().then(() => next))
      .then((next) => {
        if (active) setState((current) => settle(current, next))
      })
    return () => {
      active = false
    }
  }, [startupInput])

  if (state.status === "loading") {
    return <StartupScreen frame={state.frame} />
  }

  if (state.status === "onboarding-required") {
    return (
      <OnboardingPage
        onComplete={(selection) => {
          rememberDashboard()
          setState(startLoading())
          void Promise.all([listWorkspaces(), loadDashboard()])
            .then(([workspaces, Dashboard]) =>
              afterComposing({
                status: "ready",
                Dashboard,
                selection,
                availability: { status: "available" },
                workspaces,
              })
            )
            .then((next) => setState((current) => settle(current, next)))
            .catch((error: unknown) =>
              setState({ status: "error", message: messageFrom(error) })
            )
        }}
      />
    )
  }

  if (state.status === "error") {
    return (
      <main className="flex h-full items-center justify-center bg-app-shell p-8">
        <Alert variant="destructive" className="max-w-lg">
          <ServerOffIcon />
          <AlertTitle>
            {intl.formatMessage({
              id: "app_bootstrap_start_failed_title",
              defaultMessage: "SurfSense could not start",
            })}
          </AlertTitle>
          <AlertDescription>
            <p>{state.message}</p>
            <Button
              className="mt-3"
              variant="outline"
              onClick={() => {
                setState(startLoading())
                void fetchBootstrapState()
                  .then(afterComposing)
                  .then((next) => setState((current) => settle(current, next)))
              }}
            >
              {intl.formatMessage({
                id: "app_bootstrap_retry_button",
                defaultMessage: "Retry",
              })}
            </Button>
          </AlertDescription>
        </Alert>
      </main>
    )
  }

  // No Suspense: the dashboard's code is already here, so there is no second
  // loader to flash between startup and the first screen.
  const { Dashboard } = state
  return (
    <StartupRevealProvider reveal={state.reveal}>
      <Dashboard
        selection={state.selection}
        initialAvailability={state.availability}
        initialWorkspaces={state.workspaces}
        onModelUnavailable={() =>
          setState((current) =>
            current.status === "ready"
              ? { ...current, selection: null }
              : current
          )
        }
        onModelSelected={(selection) =>
          setState((current) =>
            current.status === "ready" ? { ...current, selection } : current
          )
        }
      />
    </StartupRevealProvider>
  )
}

import { useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ServerOffIcon } from "@/components/ui/icons"
import { getProviderModels } from "@/features/models/chat-candidates/api"
import { getConnectionModels } from "@/features/models/remote/models/api"
import {
  getGenerationSelection,
  type ModelSelection,
} from "@/features/models/selection/api"
import { getOnboardingStatus } from "@/features/onboarding/api"
import { OnboardingPage } from "@/features/onboarding/onboarding-page"
import { intl } from "@/i18n/intl"

import { listWorkspaces, type Workspace } from "@/features/workspaces/api"

import { loadDashboard, type DashboardComponent } from "./load-dashboard"
import { LogoFillLoader } from "./logo-fill-loader"

type BootstrapState =
  | { status: "loading" }
  | { status: "onboarding-required" }
  | {
      status: "ready"
      /** Loaded before the state turns ready, so it renders without suspending. */
      Dashboard: DashboardComponent
      selection: ModelSelection | null
      providerAvailable: boolean
      workspaces: Workspace[]
    }
  | { status: "error"; message: string }

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "app_bootstrap_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

async function fetchBootstrapState(): Promise<BootstrapState> {
  // Fetched alongside the data rather than after it: one wait, one loader.
  const dashboard = loadDashboard()
  // Handled where it is awaited; this only keeps an early exit from leaving
  // a rejection unobserved.
  void dashboard.catch(() => undefined)
  try {
    const onboarding = await getOnboardingStatus()
    if (!onboarding.completed) {
      return { status: "onboarding-required" }
    }
    const [selection, workspaces] = await Promise.all([
      getGenerationSelection(),
      listWorkspaces(),
    ])
    let currentSelection: ModelSelection | null = null
    if (selection?.provider === "openai_compatible") {
      const models =
        selection.connection_id === null
          ? []
          : await getConnectionModels(selection.connection_id)
      currentSelection = models.some((model) => model.name === selection.name)
        ? selection
        : null
    } else if (selection) {
      const models = await getProviderModels(selection.provider)
      currentSelection = models.some(
        (model) =>
          model.installed &&
          model.selectable_for.includes("text_gen") &&
          model.name === selection.name
      )
        ? selection
        : null
    }
    return {
      status: "ready",
      Dashboard: await dashboard,
      selection: currentSelection,
      providerAvailable: currentSelection !== null,
      workspaces,
    }
  } catch (error) {
    return { status: "error", message: messageFrom(error) }
  }
}

function GlobalLoader() {
  return (
    <main
      className="flex h-full items-center justify-center bg-app-shell select-none"
      role="status"
      aria-label={intl.formatMessage({
        id: "app_bootstrap_loader_aria",
        defaultMessage: "Starting SurfSense",
      })}
    >
      <LogoFillLoader />
    </main>
  )
}

export function AppBootstrap() {
  const [state, setState] = useState<BootstrapState>({ status: "loading" })

  useEffect(() => {
    let active = true
    void fetchBootstrapState().then((next) => {
      if (active) setState(next)
    })
    return () => {
      active = false
    }
  }, [])

  if (state.status === "loading") {
    return <GlobalLoader />
  }

  if (state.status === "onboarding-required") {
    return (
      <OnboardingPage
        onComplete={(selection) => {
          setState({ status: "loading" })
          void Promise.all([listWorkspaces(), loadDashboard()])
            .then(([workspaces, Dashboard]) =>
              setState({
                status: "ready",
                Dashboard,
                selection,
                providerAvailable: true,
                workspaces,
              })
            )
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
                setState({ status: "loading" })
                void fetchBootstrapState().then(setState)
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
    <Dashboard
      selection={state.selection}
      initialProviderAvailable={state.providerAvailable}
      initialWorkspaces={state.workspaces}
      onModelUnavailable={() =>
        setState((current) =>
          current.status === "ready" ? { ...current, selection: null } : current
        )
      }
      onModelSelected={(selection) =>
        setState((current) =>
          current.status === "ready" ? { ...current, selection } : current
        )
      }
    />
  )
}

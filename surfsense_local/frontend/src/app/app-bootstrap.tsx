import { lazy, Suspense, useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ServerOffIcon } from "@/components/ui/icons"
import {
  getGenerationSelection,
  getConnectionModels,
  getOnboardingStatus,
  getProviderModels,
  type ModelSelection,
} from "@/features/model-selection/api"
import { OnboardingPage } from "@/features/onboarding/onboarding-page"
import { listWorkspaces, type Workspace } from "@/features/workspaces/api"

const DashboardPage = lazy(() =>
  import("@/features/dashboard/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  }))
)

type BootstrapState =
  | { status: "loading" }
  | { status: "onboarding-required" }
  | {
      status: "ready"
      selection: ModelSelection | null
      providerAvailable: boolean
      workspaces: Workspace[]
    }
  | { status: "error"; message: string }

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

const ASCII_FRAMES = ["|", "/", "-", "\\"] as const
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

async function fetchBootstrapState(): Promise<BootstrapState> {
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
          model.capabilities.includes("completion") &&
          model.name === selection.name
      )
        ? selection
        : null
    }
    return {
      status: "ready",
      selection: currentSelection,
      providerAvailable: currentSelection !== null,
      workspaces,
    }
  } catch (error) {
    return { status: "error", message: messageFrom(error) }
  }
}

function GlobalLoader() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    if (window.matchMedia?.(REDUCED_MOTION_QUERY).matches) return

    const interval = window.setInterval(
      () => setFrame((current) => (current + 1) % ASCII_FRAMES.length),
      120
    )
    return () => window.clearInterval(interval)
  }, [])

  return (
    <main
      className="flex h-full items-center justify-center bg-app-shell select-none"
      role="status"
      aria-label="Starting SurfSense"
    >
      <span
        aria-hidden="true"
        className="font-mono text-2xl text-foreground tabular-nums"
      >
        [{ASCII_FRAMES[frame]}]
      </span>
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
          void listWorkspaces()
            .then((workspaces) =>
              setState({
                status: "ready",
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
      <main className="flex min-h-full items-center justify-center bg-muted/30 p-8">
        <Alert variant="destructive" className="max-w-lg">
          <ServerOffIcon />
          <AlertTitle>SurfSense could not start</AlertTitle>
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
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </main>
    )
  }

  return (
    <Suspense fallback={<GlobalLoader />}>
      <DashboardPage
        selection={state.selection}
        initialProviderAvailable={state.providerAvailable}
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
    </Suspense>
  )
}

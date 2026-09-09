import { lazy, Suspense, useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ServerOffIcon } from "@/components/ui/icons"
import {
  getGenerationSelection,
  type ModelSelection,
} from "@/features/model-selection/api"
import { ModelSelectionPage } from "@/features/model-selection/model-selection-page"
import { listWorkspaces, type Workspace } from "@/features/workspaces/api"

const DashboardPage = lazy(() =>
  import("@/features/dashboard/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  }))
)

type BootstrapState =
  | { status: "loading" }
  | { status: "model-required" }
  | {
      status: "ready"
      selection: ModelSelection
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
    const selection = await getGenerationSelection()
    if (!selection) {
      return { status: "model-required" }
    }
    const workspaces = await listWorkspaces()
    return { status: "ready", selection, workspaces }
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

  if (state.status === "model-required") {
    return (
      <ModelSelectionPage
        onSelected={(selection) => {
          setState({ status: "loading" })
          void listWorkspaces()
            .then((workspaces) =>
              setState({ status: "ready", selection, workspaces })
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
          <AlertTitle>SurfSense Local could not start</AlertTitle>
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
        initialWorkspaces={state.workspaces}
        onModelSelected={(selection) =>
          setState((current) =>
            current.status === "ready" ? { ...current, selection } : current
          )
        }
      />
    </Suspense>
  )
}

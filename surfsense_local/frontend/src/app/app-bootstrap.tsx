import { lazy, Suspense, useEffect, useState } from "react"
import { ServerOffIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  getGenerationSelection,
  type ModelSelection,
} from "@/features/model-selection/api"
import { ModelSelectionPage } from "@/features/model-selection/model-selection-page"
import type { Workspace } from "@/features/workspaces/api"
import { bootstrapWorkspaces } from "@/features/workspaces/bootstrap"

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

async function fetchBootstrapState(): Promise<BootstrapState> {
  try {
    const selection = await getGenerationSelection()
    if (!selection) {
      return { status: "model-required" }
    }
    const workspaces = await bootstrapWorkspaces()
    return { status: "ready", selection, workspaces }
  } catch (error) {
    return { status: "error", message: messageFrom(error) }
  }
}

function ShellSkeleton() {
  return (
    <main className="grid h-svh min-w-[1120px] grid-cols-[56px_272px_minmax(520px,1fr)_320px] overflow-hidden">
      <Skeleton className="h-full rounded-none" />
      <div className="space-y-4 border-r p-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
      <div className="space-y-4 border-r p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[65vh] w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <div className="space-y-4 p-4">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
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
    return <ShellSkeleton />
  }

  if (state.status === "model-required") {
    return (
      <ModelSelectionPage
        onSelected={(selection) => {
          setState({ status: "loading" })
          void bootstrapWorkspaces()
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
      <main className="flex min-h-svh items-center justify-center bg-muted/30 p-8">
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
    <Suspense fallback={<ShellSkeleton />}>
      <DashboardPage
        selection={state.selection}
        initialWorkspaces={state.workspaces}
        onModelRequired={() => setState({ status: "model-required" })}
      />
    </Suspense>
  )
}

import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Spinner } from "@/components/ui/spinner"
import { type ApiError, setEgressPrompt } from "@/lib/api"

import {
  describeDestination,
  destinationsQueryKey,
  setDestinationEnabled,
} from "./api"

type Pending = {
  destination: string
  host: string
  // What Allow does. A refused request enables the destination and is retried;
  // the updater talks to GitHub from Electron, so its consent is a pref there.
  allow: () => Promise<unknown>
  resolve: (allowed: boolean) => void
}

function pendingFrom(error: ApiError, resolve: Pending["resolve"]): Pending {
  const { destination, host } = error.detail
  const key = typeof destination === "string" ? destination : ""
  return {
    destination: key,
    host: typeof host === "string" ? host : "",
    allow: () => setDestinationEnabled(key, true),
    resolve,
  }
}

// Set while the dialog is mounted, for callers the API layer cannot speak for.
let ask: ((request: Omit<Pending, "resolve">) => Promise<boolean>) | null = null

/**
 * Ask about a destination no failed request can raise, because the call is not
 * the backend's to make. Resolves false when the prompt is not mounted, so a
 * caller outside the app shell simply gets no consent rather than an error.
 */
export function askEgress(request: Omit<Pending, "resolve">): Promise<boolean> {
  return ask ? ask(request) : Promise.resolve(false)
}

export function EgressPrompt() {
  const queryClient = useQueryClient()
  const [queue, setQueue] = useState<Pending[]>([])
  const [allowing, setAllowing] = useState(false)
  const current = queue[0]

  useEffect(() => {
    const enqueue = (pending: Pending) =>
      setQueue((queue) => [...queue, pending])
    setEgressPrompt(
      (error) => new Promise((resolve) => enqueue(pendingFrom(error, resolve)))
    )
    ask = (request) =>
      new Promise((resolve) => enqueue({ ...request, resolve }))
    return () => {
      setEgressPrompt(null)
      ask = null
    }
  }, [])

  const settle = (allowed: boolean) => {
    current?.resolve(allowed)
    setQueue((queue) => queue.slice(1))
  }

  const allow = async () => {
    if (!current) return
    setAllowing(true)
    try {
      await current.allow()
      void queryClient.invalidateQueries({ queryKey: destinationsQueryKey })
      settle(true)
    } catch {
      settle(false)
    } finally {
      setAllowing(false)
    }
  }

  if (!current) return null
  const copy = describeDestination(current.destination, current.host)
  return (
    <AlertDialog open onOpenChange={(open) => !open && settle(false)}>
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>{copy.title}</AlertDialogTitle>
          <AlertDialogDescription>{copy.body}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={allowing}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={allowing}
            onClick={(event) => {
              event.preventDefault()
              void allow()
            }}
          >
            {allowing ? <Spinner data-icon="inline-start" /> : null}
            Allow
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

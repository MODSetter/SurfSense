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
  resolve: (allowed: boolean) => void
}

function pendingFrom(error: ApiError, resolve: Pending["resolve"]): Pending {
  const { destination, host } = error.detail
  return {
    destination: typeof destination === "string" ? destination : "",
    host: typeof host === "string" ? host : "",
    resolve,
  }
}

export function EgressPrompt() {
  const queryClient = useQueryClient()
  const [queue, setQueue] = useState<Pending[]>([])
  const [allowing, setAllowing] = useState(false)
  const current = queue[0]

  useEffect(() => {
    setEgressPrompt(
      (error) =>
        new Promise((resolve) => {
          setQueue((queue) => [...queue, pendingFrom(error, resolve)])
        })
    )
    return () => setEgressPrompt(null)
  }, [])

  const settle = (allowed: boolean) => {
    current?.resolve(allowed)
    setQueue((queue) => queue.slice(1))
  }

  const allow = async () => {
    if (!current) return
    setAllowing(true)
    try {
      await setDestinationEnabled(current.destination, true)
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

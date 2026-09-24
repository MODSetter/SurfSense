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
import { intl } from "@/i18n/intl"
import { type ApiError, setEgressPrompt } from "@/lib/api"

import {
  describeDestination,
  destinationsQueryKey,
  setDestinationEnabled,
} from "./api"
import { setAskHandler, type Pending } from "./ask-egress"

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
    setAskHandler(
      (request) => new Promise((resolve) => enqueue({ ...request, resolve }))
    )
    return () => {
      setEgressPrompt(null)
      setAskHandler(null)
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
          <AlertDialogCancel disabled={allowing}>
            {intl.formatMessage({ id: "egress_prompt_cancel_button" })}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={allowing}
            onClick={(event) => {
              event.preventDefault()
              void allow()
            }}
          >
            {allowing ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({ id: "egress_prompt_allow_button" })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

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
import { useDialogPayload } from "@/components/ui/use-dialog-payload"
import { intl } from "@/i18n/intl"
import { type ApiError, setEgressPrompt } from "@/lib/api"

import {
  describeDestination,
  destinationsQueryKey,
  setDestinationEnabled,
} from "./api"
import { askEgress, registerAskHandler, type Pending } from "./ask-egress"

function requestFrom(error: ApiError): Omit<Pending, "resolve"> {
  const { destination, host } = error.detail
  const key = typeof destination === "string" ? destination : ""
  return {
    destination: key,
    host: typeof host === "string" ? host : "",
    allow: () => setDestinationEnabled(key, true),
  }
}

// `nested`: rendered inside another dialog, it answers every question raised
// while that dialog is open, so the prompt opens as that dialog's nested one.
export function EgressPrompt({ nested = false }: { nested?: boolean }) {
  const queryClient = useQueryClient()
  const [queue, setQueue] = useState<Pending[]>([])
  const [allowing, setAllowing] = useState(false)
  const current = queue[0]
  const shown = useDialogPayload(current ?? null).payload

  useEffect(() => {
    const enqueue = (pending: Pending) =>
      setQueue((queue) => [...queue, pending])
    const unregister = registerAskHandler(
      (request) => new Promise((resolve) => enqueue({ ...request, resolve }))
    )
    if (nested) return unregister
    // Refusals take the same route as askEgress, so the innermost prompt answers.
    setEgressPrompt((error) => askEgress(requestFrom(error)))
    return () => {
      setEgressPrompt(null)
      unregister()
    }
  }, [nested])

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

  if (!shown) return null
  const copy = describeDestination(shown.destination, shown.host)
  return (
    <AlertDialog
      open={current !== undefined}
      onOpenChange={(open) => !open && settle(false)}
    >
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>{copy.title}</AlertDialogTitle>
          <AlertDialogDescription>{copy.body}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={allowing}>
            {intl.formatMessage({
              id: "egress_prompt_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={allowing}
            onClick={(event) => {
              event.preventDefault()
              void allow()
            }}
          >
            {allowing ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "egress_prompt_allow_button",
              defaultMessage: "Allow",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

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
import {
  advanceEgressQueue,
  askEgress,
  settleEgress,
  useEgressQuestion,
  type Pending,
} from "./ask-egress"

function requestFrom(error: ApiError): Omit<Pending, "resolve"> {
  const { destination, host } = error.detail
  const key = typeof destination === "string" ? destination : ""
  return {
    destination: key,
    host: typeof host === "string" ? host : "",
    allow: () => setDestinationEnabled(key, true),
  }
}

// An app dialog (`AppDialogs`), so it opens over whatever dialog asked.
export function EgressPrompt() {
  const queryClient = useQueryClient()
  const { question, open } = useEgressQuestion()
  const [allowing, setAllowing] = useState(false)

  useEffect(() => {
    setEgressPrompt((error) => askEgress(requestFrom(error)))
    return () => setEgressPrompt(null)
  }, [])

  const allow = async () => {
    if (!question) return
    setAllowing(true)
    try {
      await question.allow()
      void queryClient.invalidateQueries({ queryKey: destinationsQueryKey })
      settleEgress(true)
    } catch {
      settleEgress(false)
    } finally {
      setAllowing(false)
    }
  }

  const copy = question
    ? describeDestination(question.destination, question.host)
    : null
  return (
    <AlertDialog
      open={open}
      onOpenChange={(open) => !open && settleEgress(false)}
      onOpenChangeComplete={(open) => !open && advanceEgressQueue()}
    >
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>{copy?.title}</AlertDialogTitle>
          <AlertDialogDescription>{copy?.body}</AlertDialogDescription>
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

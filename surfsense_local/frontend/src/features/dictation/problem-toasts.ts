import { useEffect } from "react"
import { useAui } from "@assistant-ui/react"
import { toast } from "sonner"

import { intl } from "@/i18n/intl"

import type { Dictation } from "./dictation-adapter"
import {
  isLasting,
  isNotice,
  problemAction,
  problemText,
  type ProblemAction,
} from "./strip/problem-text"
import { useDictationView } from "./use-dictation-view"

const TOAST_ID = "dictation-problem"
// Long enough to read a two-line problem and reach its button.
const ERROR_MS = 8000

function actionLabel(action: ProblemAction): string {
  switch (action) {
    case "open_settings":
      return intl.formatMessage({
        id: "dictation_toast_open_settings_button",
        defaultMessage: "Open settings",
      })
    case "retry":
      return intl.formatMessage({
        id: "dictation_toast_retry_button",
        defaultMessage: "Retry",
      })
    case "try_again":
      return intl.formatMessage({
        id: "dictation_toast_try_again_button",
        defaultMessage: "Try again",
      })
    default:
      return intl.formatMessage({
        id: "dictation_toast_set_up_button",
        defaultMessage: "Set up",
      })
  }
}

/**
 * Why voice input stopped or could not start, as a toast with its one action;
 * the composer's footer line is never replaced. A lasting problem is the mic's
 * to say instead. A phrase kept for Retry waits until it is acted on.
 */
export function useProblemToasts(
  dictation: Dictation,
  onOpenSpeechSettings?: () => void
) {
  const aui = useAui()
  const view = useDictationView(dictation)
  const problem = view.phase === "problem" ? view.problem : null
  const canRetry = view.phase === "problem" && view.canRetry

  useEffect(() => {
    if (!problem || isLasting(problem)) return
    const text = problemText(problem)
    const close = {
      id: TOAST_ID,
      // Closing the toast closes the problem, unless something else already has.
      onDismiss: () => dictation.dismiss(),
      onAutoClose: () => dictation.dismiss(),
    }
    if (isNotice(problem)) {
      toast.message(text, close)
      return () => void toast.dismiss(TOAST_ID)
    }
    const action = problemAction(problem, {
      canRetry,
      canSetUp: onOpenSpeechSettings !== undefined,
    })
    const act = () => {
      if (action === "open_settings") {
        void window.surfsense?.microphone?.openSettings()
        dictation.dismiss()
      } else if (action === "retry") {
        dictation.retry(aui.composer())
      } else if (action === "try_again") {
        dictation.start(aui.composer())
      } else if (action === "set_up") {
        dictation.dismiss()
        onOpenSpeechSettings?.()
      }
    }
    toast.error(text, {
      ...close,
      duration: action === "retry" ? Infinity : ERROR_MS,
      action:
        action === "dismiss"
          ? undefined
          : { label: actionLabel(action), onClick: act },
    })
    // The problem ended some other way, such as a new press of the mic.
    return () => void toast.dismiss(TOAST_ID)
  }, [problem, canRetry, dictation, aui, onOpenSpeechSettings])
}

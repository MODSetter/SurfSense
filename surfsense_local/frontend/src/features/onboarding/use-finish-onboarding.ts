import { useState } from "react"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import type { ModelSelection } from "@/features/models/selection/api"
import { useSelection } from "@/features/models/selection/use-selection"
import { intl } from "@/i18n/intl"

import { completeOnboarding } from "./api"

/**
 * Marks onboarding done and hands the app its chat model. Only this may call
 * the route, and only once a chat model is chosen: the image model is optional,
 * so Skip and Finish end the same way. The search model passed in is fixed
 * here, for good; null means the one SurfSense ships.
 */
export function useFinishOnboarding(
  onComplete: (selection: ModelSelection) => void
) {
  const chat = useSelection("text_gen")
  const [finishing, setFinishing] = useState(false)

  const finish = async (embeddingModel: string | null = null) => {
    const selection = chat.data
    // Toasts, never text above the footer: a hint to act, or a failure to report.
    if (!selection) {
      toast.error(
        intl.formatMessage({
          id: "onboarding_finish_no_chat_model_error",
          defaultMessage: "Choose a chat model first",
        })
      )
      return
    }
    setFinishing(true)
    try {
      await completeOnboarding(embeddingModel)
      onComplete(selection)
    } catch (cause) {
      errorToast(
        intl.formatMessage({
          id: "onboarding_finish_error",
          defaultMessage: "Could not finish setup",
        }),
        {
          reportError: `Could not finish setup: ${cause instanceof Error ? cause.message : String(cause)}`,
        }
      )
    } finally {
      setFinishing(false)
    }
  }

  return { finish, finishing }
}

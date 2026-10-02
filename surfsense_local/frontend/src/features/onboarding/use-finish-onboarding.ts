import { useState } from "react"

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
  const [error, setError] = useState<string | null>(null)

  const finish = async (embeddingModel: string | null = null) => {
    const selection = chat.data
    if (!selection) {
      setError(
        intl.formatMessage({
          id: "onboarding_finish_no_chat_model_error",
          defaultMessage: "Choose a chat model first",
        })
      )
      return
    }
    setFinishing(true)
    setError(null)
    try {
      await completeOnboarding(embeddingModel)
      onComplete(selection)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : intl.formatMessage({
              id: "onboarding_finish_error",
              defaultMessage: "Could not finish setup",
            })
      )
    } finally {
      setFinishing(false)
    }
  }

  return { finish, finishing, error }
}

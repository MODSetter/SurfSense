import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

/** What the app can say about a failed choice; anything else is left to Report issue. */
function describe(cause: unknown): string | undefined {
  if (cause instanceof ApiError && cause.code === "local_runtime_unavailable") {
    return intl.formatMessage({
      id: "models_use_runtime_unavailable_toast",
      defaultMessage:
        "The local model runtime isn’t running, so this model can’t be used yet.",
    })
  }
  return undefined
}

/**
 * A model that could not be chosen, said in a toast wherever Use was pressed:
 * onboarding and Settings alike. The API's own words, which may be a bare
 * status text, travel only to Report issue.
 */
export function toastUseFailure(cause: unknown): void {
  const title = intl.formatMessage({
    id: "models_use_failed_toast",
    defaultMessage: "Couldn’t use this model",
  })
  errorToast(title, {
    description: describe(cause),
    reportError: `${title}: ${cause instanceof Error ? cause.message : String(cause)}`,
  })
}

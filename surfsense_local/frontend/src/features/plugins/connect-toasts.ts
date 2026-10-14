import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import { refusalMessage } from "./refusal-message"

// Connecting ends in a toast either way: an account's sign-in finishes in the
// browser, so the screen alone would not say it worked.

export function connectedToast(plugin: string) {
  toast.success(
    intl.formatMessage(
      { id: "plugins_connected_toast", defaultMessage: "{plugin} connected" },
      { plugin }
    )
  )
}

/** A refused Connect, said in a toast rather than squeezed beside the button. */
export function connectFailedToast(plugin: string, error: unknown) {
  errorToast(
    intl.formatMessage(
      {
        id: "plugins_connect_failed_toast",
        defaultMessage: "Couldn’t connect {plugin}",
      },
      { plugin }
    ),
    { description: refusalMessage(error) }
  )
}

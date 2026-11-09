import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import type { Plugin } from "./api"
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

/** A server added by URL: connected when it works at once, or what Connect on its row will ask. */
export function addedToast(plugin: Plugin) {
  if (plugin.check_failure !== "sign_in") {
    connectedToast(plugin.name)
    return
  }
  toast.success(
    plugin.needs_own_app
      ? intl.formatMessage(
          {
            id: "plugins_added_needs_own_app_toast",
            defaultMessage:
              "{plugin} added. Connect it to set up an OAuth app.",
          },
          { plugin: plugin.name }
        )
      : intl.formatMessage(
          {
            id: "plugins_added_needs_sign_in_toast",
            defaultMessage: "{plugin} added. Connect it to sign in.",
          },
          { plugin: plugin.name }
        )
  )
}

/** A server kept to finish from its row, as one needing the user's own OAuth app. */
export function keptToast(plugin: string) {
  toast(
    intl.formatMessage(
      {
        id: "plugins_kept_needs_own_app_toast",
        defaultMessage: "{plugin} saved. Set up an OAuth app to connect it.",
      },
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

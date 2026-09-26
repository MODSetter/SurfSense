import type { QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import { MODELS_QUERY_KEY } from "../../models-query"
import type { InstallJob } from "./api"

/** What a finished job does to the app, once, whichever page is open. */
export function announce(client: QueryClient, job: InstallJob) {
  if (job.event.type === "complete") {
    void client.invalidateQueries({ queryKey: MODELS_QUERY_KEY })
  } else if (job.event.type === "cancelled") {
    toast.info(
      intl.formatMessage({
        id: "models_install_cancelled_toast",
        defaultMessage: "Installation cancelled. You can retry.",
      }),
      { id: "model-install-cancelled" }
    )
  } else if (job.event.type === "error") {
    errorToast(job.event.message, { id: "model-install-error" })
  }
}

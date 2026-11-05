import type { QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import {
  canOpenStorageSettings,
  openStorageSettings,
} from "@/features/storage/open-storage-settings"
import { intl } from "@/i18n/intl"

import { MODELS_QUERY_KEY } from "../../models-query"
import type { InstallJob } from "./api"
import { installMessage } from "./install-text"

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
    if (job.event.code === "not_enough_disk" && canOpenStorageSettings()) {
      toast.error(installMessage(job.event), {
        id: "model-install-error",
        action: {
          label: intl.formatMessage({
            id: "models_install_change_folder_button",
            defaultMessage: "Change models folder",
          }),
          onClick: openStorageSettings,
        },
      })
      return
    }
    errorToast(installMessage(job.event), { id: "model-install-error" })
  }
}

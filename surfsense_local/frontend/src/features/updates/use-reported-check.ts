import { useEffect, useRef } from "react"
import { toast } from "sonner"

import { intl } from "@/i18n/intl"

import { useCheckForUpdates } from "./use-check-for-updates"
import { useUpdateState } from "./use-update-state"

/**
 * A check whose result comes back as a toast, up to date or failed, for the
 * app menu and the title bar, where Settings may be closed. A found update
 * shows in the title bar instead.
 */
export function useReportedCheck() {
  const check = useCheckForUpdates()
  const state = useUpdateState()
  // A result counts only once this check is seen running, so an earlier
  // check's "up to date" never answers it.
  const phase = useRef<"none" | "requested" | "running">("none")

  useEffect(() => {
    if (state.status === "checking") {
      if (phase.current === "requested") phase.current = "running"
      return
    }
    if (phase.current !== "running") return
    phase.current = "none"
    if (state.status === "up-to-date")
      toast.success(
        intl.formatMessage({
          id: "updates_check_up_to_date_toast",
          defaultMessage: "SurfSense is up to date",
        })
      )
    else if (state.status === "error")
      toast.error(
        intl.formatMessage({
          id: "updates_check_failed_toast",
          defaultMessage: "Couldn’t check for updates",
        }),
        { description: state.message }
      )
  }, [state])

  return async () => {
    phase.current = "requested"
    const started = await check()
    if (!started && phase.current === "requested") phase.current = "none"
  }
}

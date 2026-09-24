import { intl } from "@/i18n/intl"

import type { InstallEvent } from "./api"

const bytes = (value: number) =>
  intl.formatNumber(value / 1e9, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  })

type Phase = "starting" | "verifying" | "selecting" | "complete"

const PHASE_SHORT: Record<Phase, () => string> = {
  starting: () =>
    intl.formatMessage({ id: "models_install_starting_short_status" }),
  verifying: () =>
    intl.formatMessage({ id: "models_install_verifying_short_status" }),
  selecting: () =>
    intl.formatMessage({ id: "models_install_selecting_short_status" }),
  complete: () =>
    intl.formatMessage({ id: "models_install_complete_short_status" }),
}

const PHASE_LABEL: Record<Phase, () => string> = {
  starting: () => intl.formatMessage({ id: "models_install_starting_status" }),
  verifying: () =>
    intl.formatMessage({ id: "models_install_verifying_status" }),
  selecting: () =>
    intl.formatMessage({ id: "models_install_selecting_status" }),
  complete: () => intl.formatMessage({ id: "models_install_complete_status" }),
}

export type InstallView = {
  /** One word, for somewhere with no room. A phase still under way trails an
   *  ellipsis; a finished one does not. */
  short: string
  label: string
  detail: string | null
  /** Null where nothing has a figure to report, which is not the same as zero. */
  percent: number | null
}

/**
 * What one install event looks like on screen.
 *
 * Its own file because the button and the progress bar both read it, and a
 * button still saying "Download" while the bar below it fills is the state
 * that reads as broken.
 */
export function installView(event: InstallEvent): InstallView {
  if (event.type === "downloading") {
    return {
      short: intl.formatMessage({
        id: "models_install_downloading_short_status",
      }),
      label:
        event.message ||
        intl.formatMessage({ id: "models_install_downloading_status" }),
      detail:
        event.total > 0
          ? intl.formatMessage(
              { id: "models_install_downloaded_status" },
              {
                completed: bytes(event.completed),
                total: bytes(event.total),
              }
            )
          : null,
      percent:
        event.total > 0
          ? Math.min(100, Math.round((event.completed / event.total) * 100))
          : null,
    }
  }

  if (event.type === "preparing") {
    // The runtime reports its own load progress, so this wait moves for the
    // same reason the download did instead of sitting still for half a minute.
    return {
      short: intl.formatMessage({
        id: "models_install_preparing_short_status",
      }),
      label:
        event.message ||
        intl.formatMessage({ id: "models_install_preparing_status" }),
      detail: null,
      percent:
        typeof event.progress === "number"
          ? Math.min(100, Math.round(event.progress * 100))
          : null,
    }
  }

  if (event.type === "error") {
    return {
      short: intl.formatMessage({ id: "models_install_failed_short_status" }),
      label:
        event.message ||
        intl.formatMessage({ id: "models_install_failed_status" }),
      detail: null,
      percent: null,
    }
  }

  return {
    short: PHASE_SHORT[event.type](),
    label: event.message || PHASE_LABEL[event.type](),
    detail: null,
    percent: event.type === "complete" ? 100 : null,
  }
}
